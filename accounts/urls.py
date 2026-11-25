from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("royxatdan-otish/", views.royxatdan_otish, name="royxat"),
    path("kirish/oneid/", views.onaid_login, name="oneid_login"),
    path("chiqish/", LogoutView.as_view(), name="logout"),
    path("parol/", views.parol_almashtirish, name="parol_almashtirish"),
    path("parolni-unutdim/", views.parol_unutdim, name="parol_unutdim"),
    path("buyurtmachilar/", views.buyurtmachi_list, name="buyurtmachi_list"),
    path("foydalanuvchi/<int:pk>/parol-tiklash/", views.parol_tiklash, name="parol_tiklash"),
    path("xodimlar/", views.xodim_list, name="xodim_list"),
    path("xodimlar/qoshish/", views.xodim_form, name="xodim_add"),
    path("xodimlar/<int:pk>/", views.xodim_form, name="xodim_edit"),
]
