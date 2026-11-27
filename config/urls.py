from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import include, path


def _admin_kirish(request, extra_context=None):
    """Admin panelining o'z login sahifasi o'rniga — himoyalangan (bloklash bor) umumiy kirish sahifasi."""
    if request.user.is_authenticated:
        raise PermissionDenied
    return redirect_to_login(request.GET.get("next") or request.get_full_path())


admin.site.login = _admin_kirish

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
]
# Yuklangan hujjatlar to'g'ridan-to'g'ri berilmaydi: /hujjat/<id>/ ruxsatni tekshiradi.
