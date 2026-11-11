"""Admin dashboard pages.

Roles: every admin is a Django *staff* user. "Owners" are also superusers and can additionally manage the
admin team. Staff can manage products, categories, orders and customers.
"""
import csv
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import AdminCreateForm, AdminEditForm, CategoryForm, OrderStatusForm, ProductForm
from .models import Category, Order, OrderItem, Product

LOW_STOCK = 5
PER_PAGE = 20

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url="accounts:login")


def owner_required(view):
    """Only owners (superusers) may manage the admin team."""
    @wraps(view)
    @staff_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Only store owners can manage admin accounts.")
            return redirect("dashboard:team")
        return view(request, *args, **kwargs)
    return wrapper


def csv_response(filename, header, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("﻿")  # so Excel opens UTF-8 correctly
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


def safe_next(request, default):
    nxt = request.POST.get("next") or ""
    return nxt if nxt.startswith("/") and not nxt.startswith("//") else default


# ---------- Overview ----------

@staff_required
def overview(request):
    valid = Order.objects.exclude(status=Order.Status.CANCELLED)
    revenue = valid.aggregate(s=Sum("total"))["s"] or 0
    order_count = valid.count()
    today = timezone.localdate()
    start = today - timedelta(days=13)
    by_day = dict(valid.filter(created_at__date__gte=start)
                  .annotate(day=TruncDate("created_at", tzinfo=timezone.get_current_timezone()))
                  .values_list("day").annotate(total=Sum("total")))
    days = [(start + timedelta(days=i)) for i in range(14)]
    sales = [(d, by_day.get(d) or 0) for d in days]
    peak = max((v for _, v in sales), default=0) or 1
    chart = [{"day": d, "total": v, "pct": int(v / peak * 100)} for d, v in sales]

    stats = {
        "revenue": revenue,
        "orders": Order.objects.count(),
        "pending": Order.objects.filter(status=Order.Status.PENDING).count(),
        "avg_order": (revenue / order_count) if order_count else 0,
        "customers": User.objects.filter(is_staff=False).count(),
        "new_customers": User.objects.filter(is_staff=False, date_joined__date__gte=today - timedelta(days=30)).count(),
        "products": Product.objects.filter(is_active=True).count(),
        "low_stock": Product.objects.filter(is_active=True, stock__lte=LOW_STOCK).count(),
        "sales_14d": sum(v for _, v in sales),
    }
    top_products = (OrderItem.objects.exclude(order__status=Order.Status.CANCELLED)
                    .values("product_name", "product_id")
                    .annotate(qty=Sum("quantity"), revenue=Sum(F("price") * F("quantity")))
                    .order_by("-qty")[:5])
    status_counts = dict(Order.objects.values_list("status").annotate(n=Count("id")))
    return render(request, "dashboard/overview.html", {
        "stats": stats, "chart": chart, "top_products": top_products,
        "recent_orders": Order.objects.select_related("user")[:6],
        "low_stock_products": Product.objects.filter(is_active=True, stock__lte=LOW_STOCK).order_by("stock")[:8],
        "status_counts": [(label, status_counts.get(value, 0), value) for value, label in Order.Status.choices],
    })


# ---------- Products ----------

def filtered_products(request):
    qs = Product.objects.select_related("category").order_by("category__position", "category__name", "name")
    f = {k: request.GET.get(k, "").strip() for k in ("q", "category", "stock", "status")}
    if f["q"]:
        qs = qs.filter(Q(name__icontains=f["q"]) | Q(brand__icontains=f["q"]) | Q(sku__icontains=f["q"]))
    if f["category"].isdigit():
        qs = qs.filter(category_id=int(f["category"]))
    if f["stock"] == "out":
        qs = qs.filter(stock=0)
    elif f["stock"] == "low":
        qs = qs.filter(stock__gt=0, stock__lte=LOW_STOCK)
    elif f["stock"] == "in":
        qs = qs.filter(stock__gt=LOW_STOCK)
    if f["status"] == "active":
        qs = qs.filter(is_active=True)
    elif f["status"] == "hidden":
        qs = qs.filter(is_active=False)
    elif f["status"] == "featured":
        qs = qs.filter(is_featured=True)
    elif f["status"] == "sale":
        qs = qs.filter(compare_at_price__gt=F("price"))
    return qs, f


@staff_required
def product_list(request):
    qs, f = filtered_products(request)
    if request.GET.get("export") == "csv":
        return csv_response("techcart-products.csv",
                            ["ID", "SKU", "Name", "Brand", "Category", "Price", "Original price", "Stock",
                             "Visible", "Featured", "URL"],
                            [(p.pk, p.sku, p.name, p.brand, p.category.name, p.price, p.compare_at_price or "",
                              p.stock, "yes" if p.is_active else "no", "yes" if p.is_featured else "no",
                              request.build_absolute_uri(p.get_absolute_url())) for p in qs])
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "dashboard/products.html", {
        "page": Paginator(qs, PER_PAGE).get_page(request.GET.get("page")), "f": f, "low": LOW_STOCK,
        "categories": Category.objects.all(), "total": qs.count(), "query": query.urlencode()})


@staff_required
def product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Product “{obj.name}” {'updated' if pk else 'created'}.")
        if request.POST.get("then") == "add_another":
            return redirect("dashboard:product_create")
        return redirect("dashboard:products")
    return render(request, "dashboard/product_form.html", {"form": form, "product": product})


@staff_required
@require_POST
def product_duplicate(request, pk):
    original = get_object_or_404(Product, pk=pk)
    copy = Product.objects.get(pk=pk)
    copy.pk = None
    copy.slug = ""
    copy.sku = ""
    copy.name = f"{original.name} (copy)"
    copy.is_active = False  # hidden until it has been checked
    copy.is_featured = False
    copy.save()
    messages.success(request, f"Copied “{original.name}”. The copy is hidden until you save it as visible.")
    return redirect("dashboard:product_edit", pk=copy.pk)


@staff_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    name = product.name
    try:
        product.delete()
        messages.success(request, f"Product “{name}” deleted.")
    except ProtectedError:
        messages.error(request, "This product can't be deleted.")
    return redirect(safe_next(request, "/dashboard/products/"))


@staff_required
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
        product.save(update_fields=["stock", "updated_at"])
        messages.success(request, f"Stock for “{product.name}” set to {value}.")
    return redirect(safe_next(request, "/dashboard/products/"))


BULK_ACTIONS = {
    "show": ("shown in the store", {"is_active": True}),
    "hide": ("hidden from the store", {"is_active": False}),
    "feature": ("featured", {"is_featured": True}),
    "unfeature": ("no longer featured", {"is_featured": False}),
}


@staff_required
@require_POST
def product_bulk(request):
    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()]
    action = request.POST.get("action", "")
    back = safe_next(request, "/dashboard/products/")
    if not ids:
        messages.error(request, "Select at least one product first.")
        return redirect(back)
    qs = Product.objects.filter(pk__in=ids)
    if action in BULK_ACTIONS:
        label, changes = BULK_ACTIONS[action]
        n = qs.update(**changes, updated_at=timezone.now())
        messages.success(request, f"{n} product{'s' if n != 1 else ''} {label}.")
    elif action == "delete":
        n = qs.count()
        qs.delete()
        messages.success(request, f"{n} product{'s' if n != 1 else ''} deleted.")
    else:
        messages.error(request, "Choose an action.")
    return redirect(back)


# ---------- Categories ----------

@staff_required
def category_list(request):
    categories = Category.objects.annotate(n=Count("products")).order_by("group", "position", "name")
    return render(request, "dashboard/categories.html", {"categories": categories,
                                                        "groups": Category.Group.choices})


@staff_required
def category_form(request, pk=None):
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, f"Category “{obj.name}” {'updated' if pk else 'created'}.")
        return redirect("dashboard:categories")
    return render(request, "dashboard/category_form.html", {"form": form, "category": category})


@staff_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    try:
        category.delete()
        messages.success(request, f"Category “{category.name}” deleted.")
    except ProtectedError:
        messages.error(request, f"“{category.name}” still has products. Move or delete them first.")
    return redirect("dashboard:categories")


# ---------- Orders ----------

def filtered_orders(request):
    qs = (Order.objects.select_related("user").annotate(item_count=Sum("items__quantity"))
          .order_by("-created_at"))
    f = {k: request.GET.get(k, "").strip() for k in ("q", "status", "payment")}
    if f["status"]:
        qs = qs.filter(status=f["status"])
    if f["payment"]:
        qs = qs.filter(payment_status=f["payment"])
    if f["q"]:
        q = f["q"]
        number = q.upper().removeprefix("TC-").lstrip("0")
        cond = (Q(full_name__icontains=q) | Q(phone__icontains=q) | Q(user__username__icontains=q)
                | Q(user__email__icontains=q))
        if number.isdigit():
            cond |= Q(pk=int(number))
        qs = qs.filter(cond)
    return qs, f


@staff_required
def order_list(request):
    qs, f = filtered_orders(request)
    if request.GET.get("export") == "csv":
        return csv_response("techcart-orders.csv",
                            ["Order", "Date", "Customer", "Username", "Phone", "Address", "Items", "Total",
                             "Payment method", "Payment", "Status"],
                            [(o.number, timezone.localtime(o.created_at).strftime("%Y-%m-%d %H:%M"), o.full_name,
                              o.user.username, o.phone, o.address, o.item_count or 0, o.total,
                              o.get_payment_method_display(), o.get_payment_status_display(),
                              o.get_status_display()) for o in qs])
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "dashboard/orders.html", {
        "page": Paginator(qs, PER_PAGE).get_page(request.GET.get("page")), "f": f,
        "statuses": Order.Status.choices, "payments": Order.PaymentStatus.choices,
        "query": query.urlencode()})


@staff_required
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


# ---------- Customers ----------

@staff_required
def customer_list(request):
    money = DecimalField(max_digits=12, decimal_places=2)
    qs = (User.objects.filter(is_staff=False)
          .annotate(order_count=Count("orders", distinct=True),
                    spent=Coalesce(Sum("orders__total", filter=~Q(orders__status=Order.Status.CANCELLED)),
                                   Value(0), output_field=money))
          .order_by("-date_joined"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q))
    if request.GET.get("export") == "csv":
        return csv_response("techcart-customers.csv",
                            ["Username", "Name", "Email", "Joined", "Last login", "Orders", "Spent", "Active"],
                            [(u.username, u.get_full_name(), u.email, u.date_joined.date(),
                              u.last_login.date() if u.last_login else "", u.order_count, u.spent,
                              "yes" if u.is_active else "no") for u in qs])
    return render(request, "dashboard/customers.html", {
        "page": Paginator(qs, PER_PAGE).get_page(request.GET.get("page")), "q": q,
        "query": urlencode({"q": q}) if q else ""})


@staff_required
@require_POST
def customer_toggle(request, pk):
    user = get_object_or_404(User, pk=pk, is_staff=False)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, f"{user.username} can {'now' if user.is_active else 'no longer'} log in.")
    return redirect(safe_next(request, "/dashboard/customers/"))


@owner_required
@require_POST
def customer_make_admin(request, pk):
    user = get_object_or_404(User, pk=pk, is_staff=False)
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    messages.success(request, f"{user.username} is now a staff admin.")
    return redirect("dashboard:team_edit", pk=user.pk)


# ---------- Admin team ----------

@staff_required
def team_list(request):
    team = User.objects.filter(is_staff=True).order_by("-is_superuser", "-is_active", "username")
    return render(request, "dashboard/team.html", {"team": team})


@owner_required
def team_add(request):
    form = AdminCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        role = "owner" if user.is_superuser else "staff admin"
        messages.success(request, f"{user.get_full_name() or user.username} was added as {role}. "
                                  f"They can log in as “{user.username}”.")
        return redirect("dashboard:team")
    return render(request, "dashboard/team_form.html", {"form": form, "member": None})


@owner_required
def team_edit(request, pk):
    member = get_object_or_404(User, pk=pk, is_staff=True)
    form = AdminEditForm(request.POST or None, instance=member, editor=request.user)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if user.pk == request.user.pk and form.cleaned_data.get("new_password"):
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)  # stay logged in after changing your own password
        messages.success(request, f"Saved {user.get_full_name() or user.username}.")
        return redirect("dashboard:team")
    return render(request, "dashboard/team_form.html", {"form": form, "member": member})


@owner_required
@require_POST
def team_remove(request, pk):
    member = get_object_or_404(User, pk=pk, is_staff=True)
    if member.pk == request.user.pk:
        messages.error(request, "You can't remove your own admin access.")
    elif member.is_superuser and not User.objects.filter(is_superuser=True, is_active=True).exclude(
            pk=member.pk).exists():
        messages.error(request, "The store needs at least one active owner.")
    else:
        member.is_staff = member.is_superuser = False
        member.save(update_fields=["is_staff", "is_superuser"])
        messages.success(request, f"{member.username} no longer has admin access (their account still exists).")
    return redirect("dashboard:team")
