from .permissions import menu_for


def sidebar(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    return {"menu_items": menu_for(user)}
