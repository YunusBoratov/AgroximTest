from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("kirish/oneid/", views.onaid_login, name="oneid_login"),
    path("chiqish/", LogoutView.as_view(), name="logout"),
    path("xodimlar/", views.xodim_list, name="xodim_list"),
    path("xodimlar/qoshish/", views.xodim_form, name="xodim_add"),
    path("xodimlar/<int:pk>/", views.xodim_form, name="xodim_edit"),
]
