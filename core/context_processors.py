from django.conf import settings

from .permissions import menu_for


def sidebar(request):
    ctx = {"MARKAZ": settings.MARKAZ, "TUPROQ_URL": settings.TUPROQ_TAHLILI_URL}
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        ctx["menu_items"] = menu_for(user)
    return ctx
