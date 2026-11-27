from django.shortcuts import redirect
from django.urls import reverse


class ParolAlmashtirishMiddleware:
    """Vaqtinchalik parol bilan kirgan foydalanuvchi avval o'z parolini o'rnatadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = getattr(request, "user", None)
        if u is not None and u.is_authenticated and getattr(u, "parol_almashtirish", False):
            ruxsat = (reverse("parol_almashtirish"), reverse("logout"))
            if not request.path.startswith(ruxsat) and not request.path.startswith(("/static/", "/i18n/")):
                return redirect("parol_almashtirish")
        return self.get_response(request)


class XavfsizlikSarlavhalariMiddleware:
    """Content-Security-Policy va Permissions-Policy: sahifaga begona skript/resurs ulanishini cheklaydi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        resp = self.get_response(request)
        csp = getattr(settings, "CSP", "")
        if csp and resp.get("Content-Type", "").startswith("text/html"):
            resp.setdefault("Content-Security-Policy", csp)
        resp.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        return resp
