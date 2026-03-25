
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (Namuna, Narxnoma, Shartnoma, Xulosa,)
from django.contrib import messages
#from .utils.docx import generate_shartnoma_docx
from .telegram_send import send_telegram_message
from .utils.docx_gen import generate_xulosa_docx
from .utils.pdf import generate_xulosa_pdf
from .utils.qr import generate_qr_image
from django.db import models
from django import forms
from .models import XulosaBand, ShartnomaBand
from .models import Natija

class ShartnomaAdminForm(forms.ModelForm):

    namunalar = forms.ModelMultipleChoiceField(
        queryset=Namuna.objects.filter(shartnoma__isnull=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Namunalar"
    )

    class Meta:
        model = Shartnoma
        fields = "__all__"

    def save(self, commit=True):
        obj = super().save(commit)

        selected_namunalar = self.cleaned_data.get("namunalar")

        if selected_namunalar:
            for namuna in selected_namunalar:
                namuna.shartnoma = obj
                namuna.save(update_fields=["shartnoma"])

        return obj
class NamunaAdminForm(forms.ModelForm):
    namuna_soni = forms.IntegerField(
        min_value=1,
        initial=1,
        label="Namuna soni"
    )

    class Meta:
        model = Namuna
        fields = "__all__"

    def save(self, commit=True):

        obj = super().save(commit=False)

        soni = self.cleaned_data.get("namuna_soni", 1)

        if not obj.pk:
            created_objects = []

            for i in range(soni):
                new_obj = Namuna.objects.create(
                    shartnoma=obj.shartnoma,
                    korxona_nomi=obj.korxona_nomi,
                    inn=obj.inn,
                    telefon=obj.telefon,
                    masul_shaxs=obj.masul_shaxs,
                    namuna_turi=obj.namuna_turi,
                )
                created_objects.append(new_obj)

            return created_objects[0]

        if commit:
            obj.save()

        return obj

# =========================
# SHARTNOMA BAND INLINE
# =========================
class ShartnomaBandInline(admin.TabularInline):
    model = ShartnomaBand
    extra = 1
    readonly_fields = ("birlik_narx", "jami_summa")
    fields = (
        "narxnoma",
        "namuna_soni",
        "birlik_narx",
        "jami_summa",
        "tartib_raqam",
    )

    def _xulosa_yuborildimi(self, obj):
        return (
            obj
            and hasattr(obj, "xulosa")
            and obj.xulosa.status == "yuborildi"
        )

    def has_add_permission(self, request, obj):
        if self._xulosa_yuborildimi(obj):
            return False
        return True

    def has_change_permission(self, request, obj=None):
        if self._xulosa_yuborildimi(obj):
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        if self._xulosa_yuborildimi(obj):
            return False
        return True
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "narxnoma":

            # request orqali tanlangan shartnomani olamiz
            shartnoma_id = request.resolver_match.kwargs.get("object_id")

            if shartnoma_id:
                from .models import Shartnoma

                shartnoma = Shartnoma.objects.get(pk=shartnoma_id)

                # shu shartnomaga bog‘langan namunalarning turlarini olamiz
                namuna_turlari = shartnoma.namunalar.values_list("namuna_turi", flat=True)

                kwargs["queryset"] = Narxnoma.objects.filter(
                    namuna_turi__in=namuna_turlari,
                    aktiv=True
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# =========================
# NAMUNA ADMIN
# =========================
@admin.register(Namuna)
class NamunaAdmin(admin.ModelAdmin):

    form = NamunaAdminForm

    
    list_display = (
        "ariza_raqami",
        "korxona_nomi",
        "namuna_turi",
        "qabul_vaqti",
        
    )
    list_display_links = None

    ordering = ("-qabul_vaqti",)

    readonly_fields = (
        "ariza_raqami",
        "qabul_vaqti",
        #"umumiy_summa",
    )

    fieldsets = (
        ("Asosiy ma'lumotlar", {
            "fields": (
                "korxona_nomi",
                "inn",
                "telefon",
            )
        }),
        ("Namuna ma'lumotlari", {
            "fields": (
                "masul_shaxs",
                "namuna_turi",
                "namuna_soni",
            )
        }),
        ("Hisob-kitob", {
            "fields": (
                "umumiy_summa",
            )
        }),
        ("Tizim ma'lumotlari", {
            "fields": (
                "ariza_raqami",
                "qabul_vaqti",
            )
        }),
    )
    def has_add_permission(self, request):
        return False
   
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)

        if obj and hasattr(obj, "xulosa"):
            if obj.xulosa.status == "yuborildi":
                readonly += [
                    "korxona_nomi",
                    "inn",
                    "telefon",
                    "masul_shaxs",
                    "namuna_turi",
                    "namuna_soni",
                ]

        return readonly

# =========================
# NARXNOMA ADMIN
# =========================
@admin.register(Narxnoma)
class NarxnomaAdmin(admin.ModelAdmin):
    list_display = (
        "korsatkich_nomi",
        "tahlil_usuli",
        "birlik",
        "narx",
        "namuna_turi", 
        "aktiv",
    )
    list_filter = ("aktiv", "namuna_turi")
    search_fields = ("korsatkich_nomi", "tahlil_usuli")


# =========================
# XULOSA ADMIN
# =========================

class XulosaBandInline(admin.TabularInline):
    
    model = XulosaBand
    extra = 0
    can_delete = False
    readonly_fields = ("narxnoma", "tartib_raqam")
    fields = ("narxnoma", "tartib_raqam", "meyor", "natija")

    def has_add_permission(self, request, obj=None):
        return False

     
        
@admin.register(Xulosa)
class XulosaAdmin(admin.ModelAdmin):

    inlines = [XulosaBandInline]

    list_display = (
        "namuna",
        "status",
        "sana",
        "pdf_link",
        "tg_send_button",
    )

    list_filter = ("status",)

    fieldsets = (

        ("Asosiy", {
            "fields": (
                "shartnoma",
                "namuna",
                "status",
                "sana",
            )
        }),

        ("Sinov ma'lumotlari", {
            "fields": (
                "sinov_sana",
                "sinov_joy",
                "namuna_ogirligi",
                "bayonnoma_raqami",
                "bayonnoma_sana",
            )
        }),

        ("Atrof-muhit", {
            "fields": (
                "harorat",
                "namlik",
            )
        }),

        ("Namuna tavsifi", {
            "fields": (
                "namuna_tavsifi",
            )
        }),

        ("Imzo", {
            "fields": (
                "tahlilchi_1",
                "tahlilchi_2",
                "laboratoriya_mudiri",
            )
        }),

        ("Tasdiqlash", {
            "fields": (
                "tasdiqlovchi",
                "tasdiqlangan_sana",
            )
        }),
    )

    readonly_fields = ("sana", "verify_token")

    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_add_permission(self, request, obj=None):
        return False
    def status_colored(self, obj):

        if obj.status == "kiritilmagan":
            color = "gray"
            dot = "⚪"
        elif obj.status == "tayyor":
            color = "orange"
            dot = "🔴"
        elif obj.status == "yuborildi":
            color = "green"
            dot = "🟢"
        else:
            color = "black"
            dot = ""

        return format_html(
            '<b style="color:{};">{} {}</b>',
            color,
            dot,
            obj.get_status_display()
        )

    status_colored.short_description = "STATUS"

    def pdf_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">PDF</a>',
            reverse("lab:verify_xulosa", args=[obj.verify_token])
        )

    pdf_link.short_description = "PDF"

    def tg_send_button(self, obj):

        if obj.status == "tayyor":
            url = reverse("lab:send_xulosa", args=[obj.pk])
            return format_html(
                '<a class="button" href="{}">TG SEND</a>',
                url
            )

        elif obj.status == "yuborildi":
            return format_html('<span style="color:gray;">TG SEND</span>')

        return "-"

    tg_send_button.short_description = "PDF/TG"

    # ===============================
    # SAVE MODEL
    # ===============================
    def save_model(self, request, obj, form, change):

        # Eski statusni saqlaymiz
        if change:
            old_obj = Xulosa.objects.get(pk=obj.pk)
            obj._old_status = old_obj.status
        else:
            obj._old_status = None

        # ❗ To‘lov tekshiruvi
        if obj.namuna and obj.namuna.shartnoma.status != "tolandi":
            from django.core.exceptions import ValidationError
            raise ValidationError("❌ To‘lov qilinmagan. Xulosa yaratib bo‘lmaydi!")

        super().save_model(request, obj, form, change)

        # 🔥 Agar bandlar yo‘q bo‘lsa avtomatik yaratamiz
        if not obj.bandlar.exists():
            shartnoma_bandlari = obj.namuna.shartnoma.bandlar.all()
            tartib = 1

            for band in shartnoma_bandlari:
                XulosaBand.objects.create(
                    xulosa=obj,
                    narxnoma=band.narxnoma,
                    tartib_raqam=tartib,
                    meyor=band.narxnoma.meyor,
                    natija=""
                )
                tartib += 1


    # ===============================
    # SAVE RELATED
    # ===============================
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        obj = form.instance
        bandlar = obj.bandlar.all()

        # 🔥 1. Agar barcha bandlarda meyor va natija bo‘lsa → TAYYOR
        if bandlar.exists() and all(b.meyor and b.natija for b in bandlar):
            if obj.status != "yuborildi":
                obj.status = "tayyor"
                obj.save(update_fields=["status"])

        # 🚀 2. Agar status "yuborildi" bo‘lsa va oldin yuborilmagan bo‘lsa
        if obj.status == "yuborildi" and obj._old_status != "yuborildi":

            from .telegram_send import send_xulosa_telegram
            from django.urls import reverse
            from django.contrib import messages

            # 1️⃣ Verify URL
            verify_url = request.build_absolute_uri(
                reverse("lab:verify_xulosa", args=[obj.verify_token])
            )

            # 2️⃣ QR yaratish
            qr_path = generate_qr_image(
                verify_url,
                f"qr_{obj.namuna.ariza_raqami}.png"
            )

            # 3️⃣ PDF yaratish
            generate_xulosa_pdf(obj, qr_path)

            # 4️⃣ Telegramga yuborish
            send_xulosa_telegram(obj)

            messages.success(
                request,
                "✅ Xulosa yuborildi, PDF yaratildi va Telegramga jo‘natildi."
            )


@admin.register(Shartnoma)
class ShartnomaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    form = ShartnomaAdminForm
    
    list_display = (
        "id",
        "buyurtmachi",
        "jami_summa",
        "status",
        "sana",
    )
    list_display_links = None
    readonly_fields = ('sana',)

    list_filter = ("status",)

    #readonly_fields = ("sana", "umumiy_summa")
    search_fields = ("buyurtmachi", "inn")

    fieldsets = (
        ("Asosiy ma'lumotlar", {
            "fields": (
                "buyurtmachi",
                "status",
                "namunalar",
            )
        }),
        ("Hisob-kitob", {
            "fields": (
                "umumiy_summa",
            )
        }),
        ("Tizim ma'lumotlari", {
            "fields": (
                "sana",
            )
        }),
    )
    def has_add_permission(self, request):
        return False
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []
        return super().get_inline_instances(request, obj)
    def save_model(self, request, obj, form, change):

        old_status = None
        if change:
            old_status = Shartnoma.objects.get(pk=obj.pk).status

        # 1️⃣ Avval shartnomani saqlaymiz
        super().save_model(request, obj, form, change)

        # 2️⃣ Agar yangi bo‘lsa — Namuna yaratamiz
        if not change:
            soni = form.cleaned_data.get("namuna_soni", 1)

            for i in range(soni):
                Namuna.objects.create(
                    shartnoma=obj,
                )

        # 3️⃣ Agar status to‘landi bo‘lsa — Xulosa yaratamiz
        if obj.status == "tolandi" and old_status != "tolandi":

            from .models import Xulosa

            for namuna in obj.namunalar.all():

                if not hasattr(namuna, "xulosa"):
                    Xulosa.objects.create(
                        namuna=namuna,
                        shartnoma=obj,
                        status="kiritilmagan"
                    )
