from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("ariza/", views.ariza_list, name="ariza_list"),
    path("namuna/", views.namuna_list, name="namuna_list"),
    path("namuna/yaratish/", views.ariza_list, name="namuna_yaratish"),  # 2-bosqichda forma bo'ladi
    path("shartnoma/", views.shartnoma_list, name="shartnoma_list"),
    path("oferta/", views.oferta_list, name="oferta_list"),
    path("tahlil-holati/", views.tahlil_holati, name="tahlil_holati"),
    path("xulosa/", views.xulosa_list, name="xulosa_list"),
    path("narxnoma/", views.narxnoma_list, name="narxnoma_list"),
    path("narxnoma/qoshish/", views.narxnoma_form, name="narxnoma_add"),
    path("narxnoma/<int:pk>/", views.narxnoma_form, name="narxnoma_edit"),
    path("kabinet/", views.kabinet, name="kabinet"),
]
