from django.urls import path

from . import views, views_ariza

urlpatterns = [
    path("", views_ariza.bosh_sahifa, name="bosh"),
    path("panel/", views.dashboard, name="dashboard"),
    # mijoz
    path("ariza/yangi/", views_ariza.ariza_yangi, name="ariza_yangi"),
    path("kabinet/", views_ariza.kabinet, name="kabinet"),
    # ariza / namuna
    path("ariza/", views.ariza_list, name="ariza_list"),
    path("ariza/<int:pk>/", views_ariza.ariza_detail, name="ariza_detail"),
    path("ariza/<int:pk>/qabul/", views_ariza.ariza_qabul, name="ariza_qabul"),
    path("ariza/<int:pk>/rad/", views_ariza.ariza_rad, name="ariza_rad"),
    path("namuna/", views.namuna_list, name="namuna_list"),
    path("namuna/yaratish/", views_ariza.namuna_yaratish, name="namuna_yaratish"),
    path("namuna/<int:pk>/", views_ariza.namuna_edit, name="namuna_edit"),
    path("namuna/<int:pk>/ochirish/", views_ariza.namuna_delete, name="namuna_delete"),
    # shartnoma / laboratoriya
    path("shartnoma/", views.shartnoma_list, name="shartnoma_list"),
    path("oferta/", views.oferta_list, name="oferta_list"),
    path("tahlil-holati/", views.tahlil_holati, name="tahlil_holati"),
    path("xulosa/", views.xulosa_list, name="xulosa_list"),
    path("narxnoma/", views.narxnoma_list, name="narxnoma_list"),
    path("narxnoma/qoshish/", views.narxnoma_form, name="narxnoma_add"),
    path("narxnoma/<int:pk>/", views.narxnoma_form, name="narxnoma_edit"),
]
