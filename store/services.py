"""Business logic shared by the web pages and the REST API."""
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from .models import CartItem, DiscountCode, Order, OrderItem, Product


class CartError(Exception):
    pass


def get_cart(user):
    items = list(CartItem.objects.filter(user=user).select_related("product", "product__category"))
    total = sum((i.subtotal for i in items), Decimal("0.00"))
    count = sum(i.quantity for i in items)
    return items, total, count


def add_to_cart(user, product, quantity=1):
    if not product.is_active:
        raise CartError("This product is no longer available.")
    item, created = CartItem.objects.get_or_create(
        user=user, product=product, defaults={"quantity": 0})
    new_qty = item.quantity + quantity
    if new_qty > product.stock:
        if created:
            item.delete()
        raise CartError(f"Only {product.stock} '{product.name}' left in stock.")
    item.quantity = new_qty
    item.save()
    return item


def set_quantity(item, quantity):
    if quantity < 1:
        item.delete()
        return None
    if quantity > item.product.stock:
        raise CartError(f"Only {item.product.stock} '{item.product.name}' left in stock.")
    item.quantity = quantity
    item.save()
    return item


def check_discount(code, user, subtotal, lock=False):
    """Return (DiscountCode, amount) for a code typed at checkout, or raise CartError with the reason."""
    code = (code or "").strip().upper()
    if not code:
        raise CartError("Enter a discount code.")
    qs = DiscountCode.objects.select_for_update() if lock else DiscountCode.objects
    discount = qs.filter(code=code).first()
    if discount is None:
        raise CartError(f"“{code}” is not a valid discount code.")
    state, _ = discount.state
    if state == "Scheduled":
        raise CartError(f"“{code}” can be used from {timezone.localtime(discount.starts_at):%d %b %Y}.")
    if state != "Active":
        raise CartError(f"“{code}” has expired." if state in ("Expired", "Used up")
                        else f"“{code}” is not available.")
    if subtotal < discount.min_order:
        raise CartError(f"“{code}” needs an order of at least ${discount.min_order:,.2f}.")
    if discount.once_per_customer and user.orders.filter(discount_code=code).exclude(
            status=Order.Status.CANCELLED).exists():
        raise CartError(f"You have already used “{code}”.")
    return discount, discount.amount_for(subtotal)


@transaction.atomic
def place_order(user, full_name, phone, address, note="", payment_method=Order.PaymentMethod.COD,
                discount_code=""):
    """Turn the user's cart into an order (cash on delivery or KHQR) and reduce stock."""
    if payment_method not in Order.PaymentMethod.values:
        raise CartError("Unknown payment method.")
    items = list(CartItem.objects.filter(user=user).select_related("product"))
    if not items:
        raise CartError("Your cart is empty.")

    # lock product rows so two customers can't buy the last item at the same time
    products = {p.pk: p for p in Product.objects.select_for_update()
                .filter(pk__in=[i.product_id for i in items])}
    for item in items:
        product = products[item.product_id]
        if not product.is_active:
            raise CartError(f"'{product.name}' is no longer available.")
        if item.quantity > product.stock:
            raise CartError(f"Only {product.stock} '{product.name}' left in stock.")

    order = Order.objects.create(user=user, full_name=full_name, phone=phone,
                                 address=address, note=note, payment_method=payment_method)
    total = Decimal("0.00")
    for item in items:
        product = products[item.product_id]
        OrderItem.objects.create(order=order, product=product, product_name=product.name,
                                 price=product.price, quantity=item.quantity)
        product.stock -= item.quantity
        product.save(update_fields=["stock"])
        total += product.price * item.quantity
    if discount_code:
        discount, amount = check_discount(discount_code, user, total, lock=True)
        DiscountCode.objects.filter(pk=discount.pk).update(used_count=models.F("used_count") + 1)
        order.discount_code, order.discount_amount = discount.code, amount
        total -= amount
    order.total = total
    order.save(update_fields=["total", "discount_code", "discount_amount"])
    CartItem.objects.filter(user=user).delete()
    return order


@transaction.atomic
def change_order_status(order, new_status):
    """Update status; cancelling an order puts its items back in stock."""
    if new_status not in Order.Status.values:
        raise ValueError("Unknown status")
    if order.status == Order.Status.CANCELLED:
        raise CartError("A cancelled order can't be changed.")
    if new_status == Order.Status.CANCELLED:
        for item in order.items.select_related("product"):
            if item.product:
                item.product.stock += item.quantity
                item.product.save(update_fields=["stock"])
        if order.payment_status == Order.PaymentStatus.PAID:
            order.payment_status = Order.PaymentStatus.REFUNDED
        if order.discount_code:  # the customer may use the code again
            DiscountCode.objects.filter(code=order.discount_code, used_count__gt=0).update(
                used_count=models.F("used_count") - 1)
    if new_status == Order.Status.SHIPPED and not order.shipped_at:
        order.shipped_at = timezone.now()
    # Cash on delivery is collected when the order is delivered.
    if new_status == Order.Status.DELIVERED and order.payment_method == Order.PaymentMethod.COD \
            and order.payment_status == Order.PaymentStatus.UNPAID:
        order.payment_status = Order.PaymentStatus.PAID
        order.paid_at = timezone.now()
        order.payment_ref = f"COD-{order.pk:05d}"
    order.status = new_status
    order.save(update_fields=["status", "payment_status", "paid_at", "payment_ref", "shipped_at"])
    return order


@transaction.atomic
def mark_paid(order, reference):
    """Admin: record a payment received outside the site (bank transfer, cash at the shop)."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.CANCELLED:
        raise CartError("A cancelled order can't be marked as paid.")
    if order.is_paid:
        raise CartError("This order is already paid.")
    order.payment_status = Order.PaymentStatus.PAID
    order.paid_at = timezone.now()
    order.payment_ref = reference.strip()[:40] or f"MANUAL-{order.pk:05d}"
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.CONFIRMED
    order.save(update_fields=["payment_status", "paid_at", "payment_ref", "status"])
    return order
