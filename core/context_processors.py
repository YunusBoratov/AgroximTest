from django.conf import settings
from django.utils.translation import get_language

from .permissions import menu_for


def _markaz():
    m = dict(settings.MARKAZ)
    if (get_language() or "").startswith("ru"):
        for k in ("nomi", "shior", "manzil"):
            m[k] = m.get(f"{k}_ru") or m[k]
    return m


def sidebar(request):
    ctx = {"MARKAZ": _markaz()}
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        ctx["menu_items"] = menu_for(user)
    return ctx
