from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("accounts.urls")),
    path("", include("core.urls")),
]
# Yuklangan hujjatlar to'g'ridan-to'g'ri berilmaydi: /hujjat/<id>/ ruxsatni tekshiradi.
