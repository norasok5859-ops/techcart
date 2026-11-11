from .models import CartItem, Category


def cart_summary(request):
    count = 0
    if request.user.is_authenticated:
        count = sum(CartItem.objects.filter(user=request.user).values_list("quantity", flat=True))
    categories = list(Category.objects.all())
    groups = [(label, [c for c in categories if c.group == value]) for value, label in Category.Group.choices]
    return {"cart_count": count, "nav_categories": categories,
            "nav_groups": [(label, cats) for label, cats in groups if cats]}
