"""Customer-facing web pages."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.urls import reverse

from . import payments, pc_builder, services
from .forms import CheckoutForm
from .models import Category, Order, Product

SORT_OPTIONS = {
    "newest": ("-created_at", "Newest"),
    "price_asc": ("price", "Price: low to high"),
    "price_desc": ("-price", "Price: high to low"),
    "name": ("name", "Name A–Z"),
}


HERO_PREFERENCE = ["gaming-laptops", "laptops", "macbooks", "graphics-cards", "monitors"]


def home(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    featured = list(products.filter(is_featured=True).order_by("category__position", "-price"))

    # Each category card shows a picture of one of its products (featured first).
    categories = list(Category.objects.annotate(
        product_count=Count("products", filter=Q(products__is_active=True))).order_by("position", "name"))
    covers = {}
    for p in products.exclude(image="").exclude(image__isnull=True).order_by("-is_featured", "-price"):
        covers.setdefault(p.category_id, p)
    for c in categories:
        c.cover = covers.get(c.id)
    by_group = {g: [c for c in categories if c.group == g] for g in Category.Group.values}

    def featured_in(group, n):
        return [p for p in featured if p.category.group == group][:n]

    # Hero: lead with a featured gaming laptop, then other headline products.
    rank = {slug: i for i, slug in enumerate(HERO_PREFERENCE)}
    # Real photos first, then by category preference and price.
    hero = sorted((p for p in featured if p.image),
                  key=lambda p: (not p.photo_source, rank.get(p.category.slug, 99), -p.price))
    hero_main = hero[0] if hero else None
    hero_side = [p for p in hero if p.category_id != getattr(hero_main, "category_id", None)][:2]

    return render(request, "store/home.html", {
        "hero_main": hero_main,
        "hero_side": hero_side,
        "computer_categories": by_group["computers"],
        "component_categories": by_group["components"],
        "accessory_categories": by_group["accessories"],
        "featured_computers": featured_in("computers", 5),
        "featured_components": featured_in("components", 5),
        "featured_accessories": featured_in("accessories", 5),
        "builder_parts": [c.cover for c in by_group["components"] if c.cover][:4],
        "brands": products.exclude(brand="").values_list("brand", flat=True).distinct().order_by("brand"),
        "accessory_brands": products.filter(category__group="accessories").exclude(brand="")
                                    .values_list("brand", flat=True).distinct().order_by("brand"),
        "product_total": products.count(),
    })


def pc_builder_page(request):
    grouped = pc_builder.parts_by_slot()
    slots = [{"slot": slot, "label": label, "required": required, "icon": icon, "parts": grouped[slot]}
             for slot, label, _cat, required, icon in pc_builder.SLOTS]
    return render(request, "store/pc_builder.html", {"slots": slots})


def product_list(request, category_slug=None):
    qs = Product.objects.filter(is_active=True).select_related("category")
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        qs = qs.filter(category=category)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q) | Q(description__icontains=q))

    min_price, max_price = request.GET.get("min_price"), request.GET.get("max_price")
    try:
        if min_price:
            qs = qs.filter(price__gte=float(min_price))
        if max_price:
            qs = qs.filter(price__lte=float(max_price))
    except ValueError:
        messages.warning(request, "Price filter must be a number.")

    if request.GET.get("in_stock"):
        qs = qs.filter(stock__gt=0)

    sort = request.GET.get("sort", "newest")
    qs = qs.order_by(SORT_OPTIONS.get(sort, SORT_OPTIONS["newest"])[0])

    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "store/product_list.html", {
        "page": page, "category": category, "categories": Category.objects.all(),
        "q": q, "sort": sort, "sort_options": {k: v[1] for k, v in SORT_OPTIONS.items()},
        "min_price": min_price or "", "max_price": max_price or "",
        "in_stock": bool(request.GET.get("in_stock")), "querystring": params.urlencode(),
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug, is_active=True)
    related = (Product.objects.filter(category=product.category, is_active=True)
               .exclude(pk=product.pk)[:4])
    return render(request, "store/product_detail.html", {"product": product, "related": related})


@login_required
def cart(request):
    items, total, count = services.get_cart(request.user)
    return render(request, "store/cart.html", {"items": items, "total": total, "count": count})


@login_required
def checkout(request):
    items, total, count = services.get_cart(request.user)
    if not items:
        messages.info(request, "Your cart is empty. Add some products first.")
        return redirect("store:product_list")

    initial = {"full_name": request.user.get_full_name()}
    last = request.user.orders.first()
    if last:
        initial.update(full_name=last.full_name, phone=last.phone, address=last.address)

    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            order = services.place_order(request.user, **form.cleaned_data)
        except services.CartError as e:
            messages.error(request, str(e))
            return redirect("store:cart")
        if order.awaiting_qr_payment:
            return redirect("store:order_pay", pk=order.pk)
        messages.success(request, f"Thank you! Order {order.number} has been placed.")
        return redirect("store:order_detail", pk=order.pk)
    return render(request, "store/checkout.html",
                  {"form": form, "items": items, "total": total, "count": count})


@login_required
def order_list(request):
    orders = request.user.orders.prefetch_related("items")
    return render(request, "store/order_list.html", {"orders": orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items__product"), pk=pk, user=request.user)
    flow = [s for s in Order.Status.choices if s[0] != Order.Status.CANCELLED]
    current = [v for v, _ in flow].index(order.status) if order.status in dict(flow) else -1
    steps = [(label, i <= current) for i, (_, label) in enumerate(flow)]
    return render(request, "store/order_detail.html", {"order": order, "steps": steps})


@login_required
def order_pay(request, pk):
    """Show the KHQR code for an order; POST = customer confirms they have paid (demo)."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if not order.awaiting_qr_payment:
        return redirect("store:order_receipt" if order.is_paid else "store:order_detail", pk=order.pk)
    if request.method == "POST":
        try:
            payments.confirm_payment(order)
        except payments.PaymentError as e:
            messages.error(request, str(e))
            return redirect("store:order_detail", pk=order.pk)
        messages.success(request, f"Payment received. Thank you! Here is your receipt for order {order.number}.")
        return redirect("store:order_receipt", pk=order.pk)
    qr = payments.payment_qr(order)
    return render(request, "store/order_pay.html", {"order": order, "qr": qr,
                                                    "items": order.items.all()})


@login_required
def order_receipt(request, pk):
    qs = Order.objects.prefetch_related("items")
    order = get_object_or_404(qs, pk=pk) if request.user.is_staff else get_object_or_404(qs, pk=pk, user=request.user)
    verify_url = request.build_absolute_uri(reverse("store:order_receipt", args=[order.pk]))
    return render(request, "store/receipt.html", {
        "order": order, "receipt": payments.receipt_data(order),
        "verify_qr": payments.qr_svg(verify_url, scale=3),
    })


@login_required
@require_POST
def order_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    if order.status != Order.Status.PENDING:
        messages.error(request, "Only pending orders can be cancelled.")
    else:
        services.change_order_status(order, Order.Status.CANCELLED)
        messages.success(request, f"Order {order.number} was cancelled.")
    return redirect("store:order_detail", pk=order.pk)
