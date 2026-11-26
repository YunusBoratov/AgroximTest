from django.contrib import admin

from . import models


@admin.register(models.Hisoblagich)
class HisoblagichAdmin(admin.ModelAdmin):
    list_display = ("kalit", "yil", "qiymat")
    list_editable = ("qiymat",)


@admin.register(models.NamunaTuri)
class NamunaTuriAdmin(admin.ModelAdmin):
    list_display = ("nomi", "kategoriya", "tartib", "aktiv")
    list_filter = ("kategoriya",)


@admin.register(models.Narxnoma)
class NarxnomaAdmin(admin.ModelAdmin):
    list_display = ("tartib", "parametr", "tahlil_usuli", "sinov_obyekti", "narx", "aktiv")
    list_filter = ("sinov_obyekti", "aktiv")
    search_fields = ("parametr", "tahlil_usuli")


class HujjatInline(admin.TabularInline):
    model = models.ArizaHujjat
    extra = 0


@admin.register(models.Ariza)
class ArizaAdmin(admin.ModelAdmin):
    list_display = ("raqam", "turi", "buyurtmachi_nomi", "fish", "namuna_turi", "holat", "created_at")
    list_filter = ("turi", "holat", "kategoriya")
    inlines = [HujjatInline]


class BandInline(admin.TabularInline):
    model = models.ShartnomaBand
    extra = 0


class TolovInline(admin.TabularInline):
    model = models.Tolov
    extra = 0


@admin.register(models.Shartnoma)
class ShartnomaAdmin(admin.ModelAdmin):
    list_display = ("raqam", "ariza", "jami_summa", "tolangan_summa", "holat", "tolov_holati")
    inlines = [BandInline, TolovInline]


@admin.register(models.Namuna)
class NamunaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "namuna_turi", "nomi", "lab_holat", "qabul_vaqti")
    list_filter = ("lab_holat",)


class NatijaInline(admin.TabularInline):
    model = models.XulosaNatija
    extra = 0


@admin.register(models.Xulosa)
class XulosaAdmin(admin.ModelAdmin):
    list_display = ("raqam", "namuna", "tayyor_at")
    inlines = [NatijaInline]


@admin.register(models.Xabar)
class XabarAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kanal", "kimga", "holat", "matn")
    list_filter = ("kanal", "holat")
    search_fields = ("kimga", "matn")


@admin.register(models.ClickTranzaksiya)
class ClickTranzaksiyaAdmin(admin.ModelAdmin):
    list_display = ("click_trans_id", "shartnoma", "summa", "holat", "created_at")
    list_filter = ("holat",)


@admin.register(models.NazoratTarixi)
class NazoratTarixiAdmin(admin.ModelAdmin):
    """Faqat o'qish: tarixni admin paneldan ham o'zgartirib yoki o'chirib bo'lmaydi."""

    list_display = ("vaqt", "turi", "user_nomi", "obyekt", "tafsilot")
    list_filter = ("turi",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import Bayram, Sozlama  # noqa: E402

admin.site.register(Sozlama)
admin.site.register(Bayram)

from .models import BosqichTarixi  # noqa: E402


@admin.register(BosqichTarixi)
class BosqichTarixiAdmin(admin.ModelAdmin):
    list_display = ("vaqt", "ariza", "namuna", "nomi", "user_nomi", "izoh")
    search_fields = ("ariza__raqam", "nomi", "user_nomi")
    readonly_fields = [f.name for f in BosqichTarixi._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
