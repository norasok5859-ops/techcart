"""Admin dashboard pages (staff users only)."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import OrderStatusForm, ProductForm
from .models import Order, Product

LOW_STOCK = 5


@staff_member_required
def overview(request):
    orders = Order.objects.exclude(status=Order.Status.CANCELLED)
    stats = {
        "revenue": orders.aggregate(s=Sum("total"))["s"] or 0,
        "orders": Order.objects.count(),
        "pending": Order.objects.filter(status=Order.Status.PENDING).count(),
        "products": Product.objects.filter(is_active=True).count(),
        "low_stock": Product.objects.filter(is_active=True, stock__lte=LOW_STOCK).count(),
    }
    status_counts = dict(Order.objects.values_list("status").annotate(n=Count("id")))
    return render(request, "dashboard/overview.html", {
        "stats": stats,
        "recent_orders": Order.objects.select_related("user")[:6],
        "low_stock_products": Product.objects.filter(is_active=True, stock__lte=LOW_STOCK).order_by("stock")[:8],
        "status_counts": [(label, status_counts.get(value, 0), value)
                          for value, label in Order.Status.choices],
    })


@staff_member_required
def product_list(request):
    qs = Product.objects.select_related("category").order_by("category__name", "name")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(brand__icontains=q))
    return render(request, "dashboard/products.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")), "q": q, "low": LOW_STOCK})


@staff_member_required
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Product '{obj.name}' {'updated' if pk else 'created'}.")
        return redirect("dashboard:products")
    return render(request, "dashboard/product_form.html", {"form": form, "product": product})


@staff_member_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    try:
        product.delete()
        messages.success(request, f"Product '{name}' deleted.")
    except ProtectedError:
        messages.error(request, "This product can't be deleted.")
    return redirect("dashboard:products")


@staff_member_required
@require_POST
def product_stock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        value = int(request.POST.get("stock", ""))
        if value < 0:
            raise ValueError
    except ValueError:
        messages.error(request, "Stock must be a whole number of 0 or more.")
    else:
        product.stock = value
        product.save(update_fields=["stock"])
        messages.success(request, f"Stock for '{product.name}' set to {value}.")
    return redirect(request.POST.get("next") or "dashboard:products")


@staff_member_required
def order_list(request):
    qs = Order.objects.select_related("user").annotate(item_count=Sum("items__quantity"))
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "dashboard/orders.html", {
        "page": Paginator(qs, 20).get_page(request.GET.get("page")),
        "status": status, "statuses": Order.Status.choices})


@staff_member_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items"), pk=pk)
    form = OrderStatusForm(request.POST or None, initial={"status": order.status})
    if request.method == "POST" and form.is_valid():
        try:
            services.change_order_status(order, form.cleaned_data["status"])
            messages.success(request, f"Order {order.number} is now {order.get_status_display()}.")
        except services.CartError as e:
            messages.error(request, str(e))
        return redirect("dashboard:order_detail", pk=order.pk)
    return render(request, "dashboard/order_detail.html", {"order": order, "form": form})
