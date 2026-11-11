"""Business logic shared by the web pages and the REST API."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import CartItem, Order, OrderItem, Product


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


@transaction.atomic
def place_order(user, full_name, phone, address, note="", payment_method=Order.PaymentMethod.COD):
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
    order.total = total
    order.save(update_fields=["total"])
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
    # Cash on delivery is collected when the order is delivered.
    if new_status == Order.Status.DELIVERED and order.payment_method == Order.PaymentMethod.COD \
            and order.payment_status == Order.PaymentStatus.UNPAID:
        order.payment_status = Order.PaymentStatus.PAID
        order.paid_at = timezone.now()
        order.payment_ref = f"COD-{order.pk:05d}"
    order.status = new_status
    order.save(update_fields=["status", "payment_status", "paid_at", "payment_ref"])
    return order
