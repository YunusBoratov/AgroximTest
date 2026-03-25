from django.contrib import admin
from django.urls import path

from config.views import home
from lab.views import confirm_send_xulosa

from lab.views import (
    verify,
    xulosa_docx,
    xulosa_pdf,
    xulosa_docx_by_token,
    xulosa_pdf_by_token,
)

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("xulosa/<int:pk>/send-telegram/", confirm_send_xulosa, name="confirm_send_xulosa"),


    # verify sahifa
    path("verify/<uuid:token>/", verify, name="verify"),

    # token orqali yuklab olish (public uchun)
    path("download/<uuid:token>/docx/", xulosa_docx_by_token, name="xulosa_docx_token"),
    path("download/<uuid:token>/pdf/", xulosa_pdf_by_token, name="xulosa_pdf_token"),
]
