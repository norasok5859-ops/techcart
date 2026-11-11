from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def money(value):
    """1049 -> "$1,049.00" (registered as a template builtin, no {% load %} needed)."""
    try:
        return f"${Decimal(value):,.2f}"
    except (InvalidOperation, TypeError, ValueError):
        return value
