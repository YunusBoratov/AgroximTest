from django.urls import path
from .views import xulosa_docx, xulosa_pdf, verify

urlpatterns = [
    path("xulosa/<int:pk>/docx/", xulosa_docx, name="xulosa_docx"),
    path("xulosa/<int:pk>/pdf/", xulosa_pdf, name="xulosa_pdf"),
    path("verify/<uuid:token>/", verify, name="verify"),
]
