"""Records admin actions for the dashboard's activity log."""
from decimal import Decimal

from .models import ActivityLog

# Product fields worth mentioning when they change, with their display names.
TRACKED_PRODUCT_FIELDS = {
    "name": "name", "category_id": "category", "brand": "brand", "sku": "SKU", "price": "price",
    "compare_at_price": "original price", "stock": "stock", "is_active": "visible", "is_featured": "featured",
    "image": "photo",
}


def log(request, action, target_type, target=None, details="", label=None):
    user = request.user if request.user.is_authenticated else None
    ActivityLog.objects.create(
        user=user, username=user.get_username() if user else "system", action=action,
        target_type=target_type, target_id=getattr(target, "pk", None),
        target_label=(label or str(target or ""))[:200], details=details[:2000])


def snapshot(product):
    return {f: getattr(product, f) for f in TRACKED_PRODUCT_FIELDS} if product and product.pk else {}


def _fmt(field, value):
    if value in (None, ""):
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return f"${value:,.2f}"
    if field == "image":
        return "new photo"
    if field == "category_id":
        from .models import Category
        return str(Category.objects.filter(pk=value).first() or value)
    return str(value)


def describe_changes(before, product):
    """"price $599.00 → $549.00; stock 3 → 10" for the fields that changed."""
    parts = []
    for field, label in TRACKED_PRODUCT_FIELDS.items():
        old, new = before.get(field), getattr(product, field)
        if field == "image":
            old, new = (old.name if old else ""), (new.name if new else "")
            if old != new:
                parts.append("photo changed" if new else "photo removed")
            continue
        if old != new:
            parts.append(f"{label} {_fmt(field, old)} → {_fmt(field, new)}")
    return "; ".join(parts)
