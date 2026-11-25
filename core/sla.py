"""
Ish muddatlari (kechikish ogohlantirishi).

Har bir bosqich holati o'zgargan vaqtdan boshlab faqat ISH VAQTI hisoblanadi
(Sozlama: ish kunlari va soatlari, Bayram kunlari chiqarib tashlanadi). Belgilangan muddat o'tsa —
qator qizil miltillaydi va panelda "Kechikkan ishlar" kartasi chiqadi.
"""
from datetime import datetime, timedelta

from django.utils import timezone

from .models import Ariza, Bayram, Namuna, Shartnoma, Sozlama, Topshiriq

H = Namuna.LabHolat
T = Topshiriq.Holat


class Muddat:
    """Sozlama va bayramlarni bir marta o'qib, ko'p marta hisoblaydi (so'rov davomida)."""

    def __init__(self, hozir=None):
        self.s = Sozlama.ol()
        self.bayramlar = set(Bayram.objects.values_list("sana", flat=True))
        self.kunlar = self.s.ish_kunlari_list
        self.hozir = hozir or timezone.now()

    def ish_daqiqalari(self, boshi, oxiri=None):
        """[boshi, oxiri] oralig'idagi ish vaqti (daqiqa)."""
        oxiri = oxiri or self.hozir
        if not boshi or oxiri <= boshi:
            return 0
        tz = timezone.get_current_timezone()
        b, o = timezone.localtime(boshi, tz), timezone.localtime(oxiri, tz)
        jami = 0.0
        kun = b.date()
        while kun <= o.date():
            if kun.weekday() in self.kunlar and kun not in self.bayramlar:
                ish_b = timezone.make_aware(datetime.combine(kun, self.s.ish_boshlanishi), tz)
                ish_o = timezone.make_aware(datetime.combine(kun, self.s.ish_tugashi), tz)
                start, end = max(b, ish_b), min(o, ish_o)
                if end > start:
                    jami += (end - start).total_seconds() / 60
            kun += timedelta(days=1)
        return jami

    def otdimi(self, boshi, muddat_maydoni):
        return boshi is not None and self.ish_daqiqalari(boshi) > getattr(self.s, muddat_maydoni)

    # --- bosqichlar ------------------------------------------------------
    def ariza(self, a):
        return a.holat == Ariza.Holat.YANGI and self.otdimi(a.yuborilgan_at, "muddat_ariza_qabul")

    def shartnoma_lab(self, sh):
        return sh.is_active and sh.holat == Shartnoma.Holat.YUBORILMAGAN and \
            self.otdimi(sh.created_at, "muddat_shartnoma_yuborish")

    def shartnoma_bux(self, sh):
        return sh.is_active and sh.holat == Shartnoma.Holat.YUBORILGAN and \
            self.otdimi(sh.yuborilgan_at, "muddat_bux_korish")

    def topshiriq(self, t):
        if t.holat == T.YUBORILDI:
            return self.otdimi(t.yuborilgan_at, "muddat_topshiriq_qabul")
        if t.holat == T.QABUL:
            return self.otdimi(t.qabul_at, "muddat_tahlil")
        if t.holat == T.QAYTARILDI:
            return self.otdimi(t.qaytarilgan_at, "muddat_qaytarilgan")
        return False

    def namuna_lab(self, n):
        """Laboratoriya mudiri (va uning mas'ullari) uchun namunadagi kechikish."""
        sh = n.shartnoma if n.shartnoma_id and n.shartnoma.is_active else None
        if n.lab_holat == H.YANGI:
            if not sh:
                return self.otdimi(n.ariza.qabul_vaqti or n.qabul_vaqti, "muddat_narx_belgilash")
            if sh.holat == Shartnoma.Holat.YUBORILMAGAN:
                return self.shartnoma_lab(sh)
            return sh.tahlil_boshlash_mumkin and self.otdimi(sh.tahlilga_ruxsat_at, "muddat_tahlilga_yuborish")
        if n.lab_holat in (H.TAHLILDA, H.JARAYONDA):
            return any(self.topshiriq(t) for t in n.topshiriqlar.all())
        if n.lab_holat == H.NATIJA:
            return self.otdimi(n.tahlil_tugagan_vaqti, "muddat_xulosa_tasdiqlash")
        if n.lab_holat == H.XULOSA and sh and sh.xulosa_yuborish_mumkin:
            x = getattr(n, "xulosa", None)
            boshi = max(d for d in [sh.toliq_tolangan_at, x.tasdiqlangan_at if x else None] if d) \
                if (sh.toliq_tolangan_at or (x and x.tasdiqlangan_at)) else None
            return self.otdimi(boshi, "muddat_xulosa_berish")
        return False


def topshiriq_kechikdi(t, m=None):
    return (m or Muddat()).topshiriq(t)


# ---------------------------------------------------------------------------
# Rol bo'yicha kechikkan ishlar (panel kartasi va ?kechikkan=1 filtri uchun)
# ---------------------------------------------------------------------------
def kechikkan_arizalar(m):
    return [a.pk for a in Ariza.objects.filter(holat=Ariza.Holat.YANGI) if m.ariza(a)]


def kechikkan_namunalar(m, kategoriya=None):
    qs = (Namuna.objects.exclude(lab_holat=H.BERILDI)
          .select_related("ariza", "shartnoma", "xulosa").prefetch_related("topshiriqlar"))
    if kategoriya:
        qs = qs.filter(namuna_turi__kategoriya=kategoriya)
    return [n.pk for n in qs if m.namuna_lab(n)]


def kechikkan_shartnomalar_bux(m):
    return [sh.pk for sh in Shartnoma.objects.filter(is_active=True, holat=Shartnoma.Holat.YUBORILGAN)
            if m.shartnoma_bux(sh)]


def kechikkan_topshiriqlar(m, user):
    return [t.pk for t in Topshiriq.objects.filter(masul=user).exclude(holat=T.TAYYOR) if m.topshiriq(t)]


def kechikkan_filtri(ids_fn):
    """list_page(post_filter=...) uchun: ?kechikkan=1 bo'lsa faqat kechikkanlarni qoldiradi."""
    def f(request, qs):
        if request.GET.get("kechikkan") == "1":
            return qs.filter(pk__in=ids_fn())
        return qs
    return f
