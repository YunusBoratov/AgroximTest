from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Xulosa, Norma


@admin.register(Xulosa)
class XulosaAdmin(admin.ModelAdmin):

    # Admin ro'yxatda ko'rinadigan ustunlar
    list_display = (
        "id",
        "namuna_raqami",
        "buyurtmachi",
        "rangli_status",
        "moslik",
        "sana",
        "verify_link",
        "docx_link",
        "pdf_link",
        "telegram_link",
    )

    # O‘ng tomondagi filterlar
    list_filter = ("status", "sana")
    search_fields = ("namuna_raqami", "buyurtmachi")

    readonly_fields = ("verify_token", "sana")
    ordering = ("-sana",)
    fieldsets = (
        ("Asosiy ma’lumotlar", {
            "fields": (
                "namuna_raqami",
                "buyurtmachi",
                "status",
                "moslik",
                "sana",
                "verify_token",
            )
        }),
        ("Tahlil natijalari", {
            "fields": (
                "azot",
                "fosfor",
                "kaliy",
                "namlik",
                "xulosa_matni",
            )
        }),
    )

    # 🔴🟡🟢 Rangli status
    def rangli_status(self, obj):
        ranglar = {
            'kutilmoqda': '#fff3cd',      # sariq
            'tahlil': '#ffe5b4',           # to‘q sariq
            'tayyor': '#d4edda',           # yashil
            'yuborildi': '#d1ecf1',        # ko‘k
        }
        rang = ranglar.get(obj.status, "#ffffff")
        return format_html(
            '<div style="background:{}; padding:4px 8px; border-radius:6px; font-weight:600;">{}</div>',
            rang,
            obj.get_status_display()
        )

    rangli_status.short_description = "Status"

    # ✅ Verify link
    def verify_link(self, obj):
        url = reverse("verify", kwargs={"token": str(obj.verify_token)})
        return format_html(
            '<a href="{}" target="_blank" style="font-weight:700;">✅ VERIFY</a>',
            url
        )

    verify_link.short_description = "Tasdiqlash"

    # 📄 DOCX
    def docx_link(self, obj):
        url = reverse("xulosa_docx_token", kwargs={"token": str(obj.verify_token)})
        return format_html('<a href="{}" target="_blank">DOCX</a>', url)

    docx_link.short_description = "DOCX"

    # 📄 PDF
    def pdf_link(self, obj):
        url = reverse("xulosa_pdf_token", kwargs={"token": str(obj.verify_token)})
        return format_html('<a href="{}" target="_blank">PDF</a>', url)

    pdf_link.short_description = "PDF"

    # 📲 Telegram yuborish
    def telegram_link(self, obj):
        
        if obj.status not in ("tayyor", "yuborildi"):
            return "—"

        if obj.yuborilgan:
            text = "🔁 Qayta yuborish"
            color = "#ffc107"
        else:
            text = "📨 TG SEND"
            color = "#28a745"

        url = reverse("confirm_send_xulosa", args=[obj.pk])
        return format_html(
            '<a href="{}" style="background:{}; color:white; padding:4px 8px; border-radius:6px; font-weight:700;">{}</a>',
            url, color, text
        )

    telegram_link.short_description = "Telegram"



@admin.register(Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ("element", "min_qiymat", "max_qiymat")
    search_fields = ("element",)

def get_queryset(self, request):
    qs = super().get_queryset(request)
    qs = qs.annotate()
    return qs