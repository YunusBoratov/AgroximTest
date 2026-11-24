from django.urls import path

from . import views, views_ariza, views_lab as vl, views_shartnoma as vs, views_tolov as vt

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
    path("ariza/<int:pk>/tahrirlash/", views_ariza.ariza_tahrirlash, name="ariza_tahrirlash"),
    path("ariza/<int:pk>/rad/", views_ariza.ariza_rad, name="ariza_rad"),
    path("hujjat/<int:pk>/", views_ariza.ariza_hujjat, name="ariza_hujjat"),
    path("namuna/", views.namuna_list, name="namuna_list"),
    path("namuna/yaratish/", views_ariza.namuna_yaratish, name="namuna_yaratish"),
    path("namuna/<int:pk>/", views_ariza.namuna_edit, name="namuna_edit"),
    path("namuna/<int:pk>/ochirish/", views_ariza.namuna_delete, name="namuna_delete"),
    # shartnoma / laboratoriya
    path("shartnoma/", views.shartnoma_list, name="shartnoma_list"),
    path("shartnoma/yangi/", vs.shartnoma_tanlash, name="shartnoma_tanlash"),
    path("shartnoma/yangi/<int:ariza_pk>/", vs.shartnoma_form, name="shartnoma_yangi"),
    path("shartnoma/<int:pk>/", vs.shartnoma_detail, name="shartnoma_detail"),
    path("shartnoma/<int:pk>/korsatkichlar/", vs.shartnoma_form, name="shartnoma_edit"),
    path("shartnoma/<int:pk>/yuborish/", vs.shartnoma_yuborish, name="shartnoma_yuborish"),
    path("shartnoma/<int:pk>/ochirish/", vs.shartnoma_ochirish, name="shartnoma_ochirish"),
    path("shartnoma/<int:pk>/rekvizit/", vs.rekvizit_saqlash, name="rekvizit_saqlash"),
    path("shartnoma/<int:pk>/tolov/", vs.tolov_qoshish, name="tolov_qoshish"),
    path("shartnoma/<int:pk>/tolov/<int:tolov_pk>/ochirish/", vs.tolov_ochirish, name="tolov_ochirish"),
    path("shartnoma/<int:pk>/hujjat.<str:fmt>", vs.shartnoma_hujjat, name="shartnoma_hujjat"),
    path("oferta/", views.oferta_list, name="oferta_list"),
    path("tahlil-holati/", views.tahlil_holati, name="tahlil_holati"),
    path("xulosa/", views.xulosa_list, name="xulosa_list"),
    path("namuna/<int:pk>/tahlilga/", vl.tahlilga_olish, name="tahlilga_olish"),
    path("namuna/<int:pk>/natija-tayyor/", vl.natija_tayyor, name="natija_tayyor"),
    path("namuna/<int:pk>/natija/", vl.xulosa_kiritish, name="xulosa_kiritish"),
    path("xulosa/<int:pk>/", vl.xulosa_korish, name="xulosa_korish"),
    path("xulosa/<int:pk>/tasdiqlash/", vl.xulosa_tasdiqlash, name="xulosa_tasdiqlash"),
    path("xulosa/<int:pk>/berish/", vl.xulosa_berish, name="xulosa_berish"),
    path("xulosa/<int:pk>/hujjat.<str:fmt>", vl.xulosa_hujjat, name="xulosa_hujjat"),
    path("tekshirish/<uuid:token>/", vl.xulosa_tekshirish, name="xulosa_tekshirish"),
    # Click SHOP API va Telegram bot
    path("click/prepare/", vt.click_prepare, name="click_prepare"),
    path("click/complete/", vt.click_complete, name="click_complete"),
    path("kabinet/tolov/<int:pk>/", vt.click_tolash, name="click_tolash"),
    path("telegram/webhook/<str:secret>/", vt.telegram_webhook, name="telegram_webhook"),
    path("kabinet/telegram/uzish/", vt.telegram_uzish, name="telegram_uzish"),
    path("narxnoma/", views.narxnoma_list, name="narxnoma_list"),
    path("narxnoma/qoshish/", views.narxnoma_form, name="narxnoma_add"),
    path("narxnoma/<int:pk>/", views.narxnoma_form, name="narxnoma_edit"),
]
