from django.urls import path
from . import views_contract
from . import views
from .views_contract import (
    shartnoma_yangi,
    shartnoma_monitoring,
    shartnoma_soft_delete,
    status_update,
    lab_shartnomalar,
)

urlpatterns = [
    path("verify/<uuid:token>/", views.verify_xulosa, name="verify_xulosa"),
    path("xulosa/<int:pk>/pdf/", views.xulosa_pdf_by_token, name="xulosa_pdf"),
    path("send-xulosa/<int:pk>/", views.send_xulosa_view, name="send_xulosa"),
    path("shartnoma/yangi/", shartnoma_yangi, name="shartnoma_yangi"),
    path("shartnoma/monitoring/", shartnoma_monitoring, name="shartnoma_monitoring"),
    path("shartnoma/delete/<int:pk>/", shartnoma_soft_delete, name="shartnoma_delete"),
    path("shartnoma/status/<int:pk>/<str:new_status>/", status_update, name="status_update"),
    path("lab/shartnomalar/", lab_shartnomalar, name="lab_shartnomalar"),
    path("lab/xulosa/<int:namuna_id>/", views_contract.xulosa_yaratish, name="xulosa_yaratish"),
    path("lab/namunalar/", views_contract.lab_namunalar, name="lab_namunalar"),
    path("shartnoma/<int:pk>/tolov/", views_contract.tolov_kiritish, name="tolov_kiritish"),
    path("lab/", views_contract.lab_shartnomalar, name="lab_shartnomalar"),
    path("lab/<int:pk>/natija/", views_contract.natija_kiritish, name="natija_kiritish"),
    path("lab/<int:pk>/xulosa/", views_contract.xulosa_korish, name="xulosa_korish"),
    path("lab/<int:pk>/pdf/", views_contract.xulosa_pdf, name="xulosa_pdf"),
    path("xulosa/<int:namuna_id>/",views_contract.xulosa_yaratish,name="xulosa_yaratish"),
    path("xulosa/<int:pk>/", views.xulosa_kiritish, name="xulosa_kiritish")

    
]
