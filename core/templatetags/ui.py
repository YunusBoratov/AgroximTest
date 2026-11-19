from decimal import Decimal

from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def money(v):
    """5374888.00 -> '5 374 888'"""
    if v in (None, ""):
        return ""
    try:
        v = Decimal(v).quantize(Decimal("1"))
    except Exception:
        return v
    return f"{int(v):,}".replace(",", " ")


@register.filter
def dt(v):
    if not v:
        return ""
    return timezone.localtime(v).strftime("%d.%m.%Y")


@register.filter
def tm(v):
    if not v:
        return ""
    return timezone.localtime(v).strftime("%H:%M:%S")
