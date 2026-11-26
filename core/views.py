from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from accounts.models import Role

from .forms import NarxnomaForm
from .listing import Column, Filters, list_page
from .models import (Ariza, ArizaTuri, Kategoriya, NamunaTuri, Namuna, Narxnoma, NazoratTarixi, Shartnoma,
                     Xulosa)
from .permissions import ADMINS, AD, BX, LAB, NQ, SA, role_required, user_role, korinadigan_hujjatlar
from . import sla
from .views_shartnoma import shartnoma_kutayotgan_arizalar

# Holat -> badge rangi
BADGE = {
    "yangi": "red", "qabul": "green", "rad": "grey",
    "kutilmoqda": "red", "qisman": "yellow", "tolangan": "green",
    "yuborilmagan": "grey", "yuborilgan": "yellow",
    "tahlilda": "yellow", "jarayonda": "yellow", "natija": "blue", "xulosa": "green", "berildi": "green",
}


# ---------------------------------------------------------------------------
# Jadvallar ustidagi statistika (tanlangan davr va filtrlar bo'yicha)
# ---------------------------------------------------------------------------
def _holat_stats(qs, field, choices, jami_label):
    sonlar = dict(qs.values_list(field).annotate(n=Count("id")).values_list(field, "n"))
    return [(jami_label, sum(sonlar.values()), "")] + [
        (lbl, sonlar.get(val, 0), "red" if val in ("yangi", "rad") else "") for val, lbl in choices if sonlar.get(val)]


def ariza_stats(qs):
    return _holat_stats(qs, "holat", Ariza.Holat.choices, _("Jami arizalar"))


def namuna_stats(qs):
    return _holat_stats(qs, "lab_holat", Namuna.LabHolat.choices, _("Jami namunalar"))


def shartnoma_stats(qs):
    from django.db.models import Sum

    a = qs.aggregate(j=Sum("jami_summa"), t=Sum("tolangan_summa"))
    jami, tol = a["j"] or Decimal(0), a["t"] or Decimal(0)
    return [(_("Shartnomalar"), qs.count(), ""), (_("Jami summa"), jami, "money"),
            (_("To'langan"), tol, "money"), (_("Qoldiq"), jami - tol, "money warn")] + [
        (lbl, n, "") for val, lbl in Shartnoma.TolovHolati.choices
        for n in [qs.filter(tolov_holati=val).count()] if n]


def xulosa_stats(qs):
    return [(_("Jami xulosalar"), qs.count(), ""),
            (_("Tasdiqlangan"), qs.filter(tasdiqlangan_at__isnull=False).count(), ""),
            (_("Buyurtmachiga berilgan"), qs.filter(namuna__lab_holat=Namuna.LabHolat.BERILDI).count(), "")]


def badge(field):
    return lambda o: BADGE.get(getattr(o, field), "grey")


def turi_tabs():
    return [("", _("Barchasi"))] + list(ArizaTuri.choices)


def tur_filtr(request, qs, path="namuna_turi"):
    """Monitoring kartasidan kelganda: ?tur=<namuna turi id>."""
    tur = request.GET.get("tur", "")
    return qs.filter(**{path: tur}) if tur.isdigit() else qs


def lab_scope(request, qs, path="namuna_turi__kategoriya"):
    """Laboratoriya xodimi faqat o'z kategoriyasini ko'radi."""
    kat = request.user.lab_kategoriya if user_role(request.user) in LAB else None
    if kat:
        qs = qs.filter(**{path: kat})
    kat_param = request.GET.get("kategoriya")
    if kat_param in Kategoriya.values:
        qs = qs.filter(**{path: kat_param})
    return qs


# ---------------------------------------------------------------------------
# Monitoring / Asosiy panel
# ---------------------------------------------------------------------------
def _turi_cards(qs, kategoriya=None, field="namuna_turi"):
    counts = dict(qs.values_list(field).annotate(c=Count("id")).values_list(field, "c"))
    out = {}
    for kat in Kategoriya.values:  # Mineral o'g'it birinchi
        if kategoriya and kat != kategoriya:
            continue
        out[kat] = [(t, counts.get(t.id, 0)) for t in NamunaTuri.objects.filter(aktiv=True, kategoriya=kat)]
    return out


@login_required
def dashboard(request):
    from .listing import DAVRLAR, davr_oraligi, sana_filtri

    role = user_role(request.user)
    if role == Role.MIJOZ:
        return redirect("kabinet")
    if role in (Role.MASUL_MINERAL, Role.MASUL_KIMYO):
        return redirect("masul_topshiriqlar")

    davr = request.GET.get("davr", "")
    d1, d2 = davr_oraligi(davr)
    q = f"&davr={davr}" if davr else ""

    def davrda(qs, field):
        return sana_filtri(qs, field, d1, d2)

    m = sla.Muddat()
    ctx = {"title": _("Monitoring"), "davrlar": DAVRLAR, "davr": davr, "kechikkan": []}

    if role == NQ:
        ar = davrda(Ariza.objects.all(), "created_at")
        ctx["cards"] = [
            (_("Yangi arizalar"), Ariza.objects.filter(holat=Ariza.Holat.YANGI).count(),
             reverse("ariza_list") + "?holat=yangi"),
            (_("Qabul qilingan arizalar"), ar.filter(holat=Ariza.Holat.QABUL).count(),
             reverse("ariza_list") + "?holat=qabul" + q),
            (_("Rad etilgan arizalar"), ar.filter(holat=Ariza.Holat.RAD).count(),
             reverse("ariza_list") + "?holat=rad" + q),
            (_("Jami arizalar"), ar.count(), reverse("ariza_list") + "?" + q.lstrip("&")),
        ]
        ctx["kechikkan"] = [(_("Kechikkan arizalar"), len(sla.kechikkan_arizalar(m)),
                             reverse("ariza_list") + "?kechikkan=1")]
        return render(request, "core/dash_namuna.html", ctx)

    if role == BX:
        ctx["title"] = _("Asosiy panel")
        groups = []
        for kat, label in Kategoriya.choices:
            qs = davrda(Shartnoma.objects.filter(is_active=True, ariza__kategoriyalar__contains=kat).exclude(
                holat=Shartnoma.Holat.YUBORILMAGAN), "created_at")
            groups.append((label, [
                (lbl, qs.filter(tolov_holati=val).count(),
                 reverse("oferta_list") + f"?kategoriya={kat}&holat={val}{q}")
                for val, lbl in Shartnoma.TolovHolati.choices
            ]))
        ctx["groups"] = groups
        ctx["kechikkan"] = [(_("Ko'rilmagan shartnomalar (muddati o'tgan)"),
                             len(sla.kechikkan_shartnomalar_bux(m)), reverse("oferta_list") + "?kechikkan=1")]
        return render(request, "core/dash_bux.html", ctx)

    namunalar = lab_scope(request, Namuna.objects.all())
    if role in LAB:
        ctx["title"] = _("Asosiy panel")
        sh = davrda(lab_scope(request, Shartnoma.objects.filter(is_active=True), "ariza__kategoriyalar__contains"), "created_at")
        ctx["shartnoma_cards"] = [
            (_("Ariza shakllantirilgan, shartnoma tuzilishi kutilmoqda"),
             shartnoma_kutayotgan_arizalar(request.user.lab_kategoriya).count(), reverse("shartnoma_tanlash")),
            (_("Tuzilgan shartnomalar"), sh.count(), reverse("shartnoma_list") + "?" + q.lstrip("&")),
        ]
        tayyor = namunalar.filter(lab_holat=Namuna.LabHolat.YANGI, shartnoma__isnull=False)
        tayyor_n = sum(1 for n in tayyor.select_related("shartnoma") if n.shartnoma.tahlil_boshlash_mumkin)
        ctx["shartnoma_cards"].append(
            (_("Tahlil boshlash mumkin bo'lgan namunalar (30%+ to'langan)"), tayyor_n, reverse("tahlil_holati") + "?holat=yangi"))
        davr_nam = davrda(namunalar, "qabul_vaqti")
        ctx["lab_cards"] = [
            (lbl, (namunalar if val != "xulosa" else davr_nam).filter(lab_holat=val).count(),
             reverse("tahlil_holati") + f"?holat={val}" + (q if val == "xulosa" else ""))
            for val, lbl in Namuna.LabHolat.choices if val in ("yangi", "tahlilda", "jarayonda", "natija", "xulosa")
        ]
        xul = davr_nam.filter(xulosa__isnull=False)
        ctx["xulosa_total"] = xul.count()
        ctx["turi_cards"] = _turi_cards(xul, request.user.lab_kategoriya)
        ctx["kat_labels"] = dict(Kategoriya.choices)
        ctx["kechikkan"] = [(_("Kechikkan ishlar"), len(sla.kechikkan_namunalar(m, request.user.lab_kategoriya)),
                             reverse("tahlil_holati") + "?kechikkan=1")]
        return render(request, "core/dash_lab.html", ctx)

    # Admin / super admin
    turi = request.GET.get("turi", "")
    namunalar = davrda(namunalar, "qabul_vaqti")
    if turi:
        namunalar = namunalar.filter(ariza__turi=turi)
    ctx["turi_cards"] = _turi_cards(namunalar)
    ctx["kat_labels"] = dict(Kategoriya.choices)
    ctx["kat_totals"] = {k: namunalar.filter(namuna_turi__kategoriya=k).count() for k in Kategoriya.values}
    ctx["turi_tabs"] = turi_tabs()
    ctx["state"] = {"turi": turi}
    ctx["kechikkan"] = [
        (_("Kechikkan arizalar"), len(sla.kechikkan_arizalar(m)), reverse("ariza_list") + "?kechikkan=1"),
        (_("Laboratoriyada kechikkan ishlar"), len(sla.kechikkan_namunalar(m)),
         reverse("tahlil_holati") + "?kechikkan=1"),
    ]
    return render(request, "core/dash_admin.html", ctx)


# ---------------------------------------------------------------------------
# Ro'yxatlar
# ---------------------------------------------------------------------------
@role_required(AD, NQ)
def ariza_list(request):
    qs = Ariza.objects.select_related("namuna_turi").prefetch_related("hujjatlar__ariza_namuna", "namunalar__namuna_turi")
    cols = [
        Column(_("Ariza raqami"), "raqam", "bold", url=lambda o: reverse("ariza_detail", args=[o.pk])),
        Column(_("Ariza turi"), "get_turi_display"),
        Column(_("Buyurtmachi nomi"), "buyurtmachi_nomi"),
        Column(_("F.I.SH."), "fish"),
        Column(_("INN"), "inn"),
        Column(_("Telefon nomeri"), "telefon"),
        Column(_("Namuna soni"), "namuna_soni"),
        Column(_("Namuna turi"), lambda o: o.turlar_matni),
        Column(_("Namuna nomi"), "namuna_nomi"),
        Column(_("Partiya raqami"), "partiya_raqami"),
        Column(_("Chegara maskani"), "chegara_maskani"),
        Column(_("Sana va vaqti"), "created_at", "datetime"),
        Column(_("Zarur hujjatlar"), lambda o: korinadigan_hujjatlar(request.user, o.hujjatlar.all()), "file"),
        Column(_("Holati"), "get_holat_display", "badge", badge=badge("holat")),
    ]
    if user_role(request.user) in (NQ, SA):
        cols.append(Column("", lambda o: [(_("Qabul qilish"), reverse("ariza_qabul", args=[o.pk]), "check", "btn")]
                           if o.holat == Ariza.Holat.YANGI else [], "actions", excel=False))
    f = Filters(search_fields=["raqam", "buyurtmachi_nomi", "fish", "inn", "telefon", "namuna_nomi"],
                date_field="created_at", holat_field="holat", holat_choices=Ariza.Holat.choices,
                turi_field="turi")
    m = sla.Muddat()
    return list_page(request, title=_("Ariza"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs(),
                     row_class=lambda o: "kechikdi" if m.ariza(o) else "",
                     post_filter=sla.kechikkan_filtri(lambda: sla.kechikkan_arizalar(m)), stats=ariza_stats)


@role_required(AD, NQ)
def namuna_list(request):
    qs = tur_filtr(request, Namuna.objects.select_related("ariza", "namuna_turi", "xulosa").prefetch_related("ariza__hujjatlar__ariza_namuna"))
    cols = [
        Column(_("Ariza raqami"), "__str__", "bold", url=lambda o: reverse("ariza_detail", args=[o.ariza_id])),
        Column(_("Ariza turi"), "ariza.get_turi_display"),
        Column(_("Namuna olgan mas'ul xodim"), "namuna_olgan"),
        Column(_("Chegara maskani yoki ombor nomi"), "ariza.chegara_maskani"),
        Column(_("Buyurtmachi nomi"), "ariza.buyurtmachi"),
        Column(_("INN"), "ariza.inn"),
        Column(_("Namuna nomi"), "nomi"),
        Column(_("Namuna turi"), lambda o: str(o.namuna_turi)),
        Column(_("Namuna qabul qilingan vaqt"), "qabul_vaqti", "datetime"),
        Column(_("Mavjud hujjatlar"), lambda o: korinadigan_hujjatlar(request.user, o.ariza.hujjatlar.all(), namuna=o),
               "file"),
        Column(_("Sinov bayonnomasi"), lambda o: [(o.xulosa.raqam, reverse("xulosa_hujjat", args=[o.xulosa.pk, "pdf"]),
                                                   "file", "btn")]
               if getattr(o, "xulosa", None) and o.xulosa.tasdiqlangan else [], "actions", excel=False),
        Column(_("Holati"), "get_lab_holat_display", "badge", badge=badge("lab_holat")),
    ]
    if user_role(request.user) in (NQ, SA):
        cols.append(Column("", lambda o: [
            (_("Tahrirlash"), reverse("namuna_edit", args=[o.pk]), "edit", ""),
            (_("O'chirish"), reverse("namuna_delete", args=[o.pk]), "delete", "danger post"),
        ] if o.lab_holat == Namuna.LabHolat.YANGI and not o.shartnoma_id else [], "actions", excel=False))
    f = Filters(search_fields=["ariza__raqam", "ariza__buyurtmachi_nomi", "ariza__fish", "ariza__inn", "nomi"],
                date_field="qabul_vaqti", holat_field="lab_holat", holat_choices=Namuna.LabHolat.choices,
                turi_field="ariza__turi")
    return list_page(request, title=_("Namuna"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs(),
                     stats=namuna_stats)


def _shartnoma_cols():
    return [
        Column(_("Shartnoma raqami"), "raqam", "bold", url=lambda o: reverse("shartnoma_detail", args=[o.pk])),
        Column(_("Ariza turi"), "ariza.get_turi_display"),
        Column(_("Buyurtmachi nomi"), "ariza.buyurtmachi"),
        Column(_("INN"), "ariza.inn"),
        Column(_("Sana va vaqti"), "created_at", "datetime"),
        Column(_("Summasi"), "jami_summa", "money"),
        Column(_("To'landi"), "tolangan_summa", "money"),
    ]


@role_required(AD, *LAB)
def shartnoma_list(request):
    qs = lab_scope(request, Shartnoma.objects.filter(is_active=True).select_related("ariza"), "ariza__kategoriyalar__contains")
    cols = _shartnoma_cols() + [
        Column(_("Biriktirilgan hujjatlar"), lambda o: korinadigan_hujjatlar(request.user, o.ariza.hujjatlar.all()),
               "file"),
        Column(_("Holati"), "get_holat_display", "badge", badge=badge("holat")),
        Column(_("To'lov"), "get_tolov_holati_display", "badge", badge=badge("tolov_holati")),
        Column("", lambda o: [
            (_("Ko'rish"), reverse("shartnoma_detail", args=[o.pk]), "eye", ""),
            (_("Shartnoma (PDF)"), reverse("shartnoma_hujjat", args=[o.pk, "pdf"]), "file", ""),
        ] + ([(_("Ko'rsatkichlar"), reverse("shartnoma_edit", args=[o.pk]), "edit", "")]
             if o.holat == Shartnoma.Holat.YUBORILMAGAN else []), "actions", excel=False),
    ]
    f = Filters(search_fields=["raqam", "ariza__buyurtmachi_nomi", "ariza__fish", "ariza__inn"],
                date_field="created_at", holat_field="holat", holat_choices=Shartnoma.Holat.choices,
                summa_field="jami_summa", turi_field="ariza__turi")
    qs = qs.prefetch_related("ariza__hujjatlar__ariza_namuna")
    m = sla.Muddat()
    return list_page(request, title=_("Shartnoma tuzilishi va bajarilishi"), qs=qs, columns=cols, filters=f,
                     turi_tabs=turi_tabs(), add_url=reverse("shartnoma_tanlash"), add_label=_("Shartnoma tuzish"),
                     row_class=lambda o: "kechikdi" if m.shartnoma_lab(o) else "", stats=shartnoma_stats)


@role_required(AD, BX)
def oferta_list(request):
    qs = Shartnoma.objects.filter(is_active=True).select_related("ariza")
    if user_role(request.user) == BX:
        qs = qs.exclude(holat=Shartnoma.Holat.YUBORILMAGAN)
    kat = request.GET.get("kategoriya")
    if kat in Kategoriya.values:
        qs = qs.filter(ariza__kategoriyalar__contains=kat)
    cols = _shartnoma_cols() + [
        Column(_("Qoldiq"), "qoldiq", "money"),
        Column(_("Holati"), "get_tolov_holati_display", "badge", badge=badge("tolov_holati")),
        Column(_("Ko'rildi"), lambda o: _("Ko'rilmagan") if o.holat == Shartnoma.Holat.YUBORILGAN else _("Ko'rilgan"),
               "badge", badge=lambda o: "yellow" if o.holat == Shartnoma.Holat.YUBORILGAN else "green"),
        Column("", lambda o: [
            (_("Ochish / to'lov"), reverse("shartnoma_detail", args=[o.pk]), "eye", ""),
            (_("Shartnoma (PDF)"), reverse("shartnoma_hujjat", args=[o.pk, "pdf"]), "file", ""),
        ], "actions", excel=False),
    ]
    f = Filters(search_fields=["raqam", "ariza__buyurtmachi_nomi", "ariza__fish", "ariza__inn"],
                date_field="created_at", holat_field="tolov_holati",
                holat_choices=Shartnoma.TolovHolati.choices, summa_field="jami_summa", turi_field="ariza__turi")
    m = sla.Muddat()
    return list_page(request, title=_("Oferta"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs(),
                     row_class=lambda o: "kechikdi" if m.shartnoma_bux(o) else "", stats=shartnoma_stats,
                     post_filter=sla.kechikkan_filtri(lambda: sla.kechikkan_shartnomalar_bux(m)),
                     extra={"kategoriya_tabs": [("", _("Barchasi"))] + list(Kategoriya.choices)})


def _lab_amallar(o):
    """Tahlil holati jadvalidagi har bir namuna uchun navbatdagi amal (dizayndagi izohlar bo'yicha)."""
    H = Namuna.LabHolat
    sh = o.shartnoma if o.shartnoma_id and o.shartnoma.is_active else None
    if o.lab_holat == H.YANGI:
        if not sh:
            # namuna qabul qilindi -> laboratoriya narxnomadan narx belgilaydi (shartnoma tuzadi)
            return [(_("Narx belgilash"), reverse("shartnoma_yangi", args=[o.ariza_id]), "plus", "btn")]
        if sh.holat == Shartnoma.Holat.YUBORILMAGAN:
            if o.namuna_turi_id and o.namuna_turi.kategoriya in sh.narxsiz_kategoriyalar:  # aralash ariza
                return [(_("Narx belgilash"), reverse("shartnoma_edit", args=[sh.pk]) +
                         f"?kategoriya={o.namuna_turi.kategoriya}", "plus", "btn")]
            return [(_("Buxgalteriyaga yuborish"), reverse("shartnoma_detail", args=[sh.pk]), "send", "btn")]
        if sh.tahlil_boshlash_mumkin:
            return [(_("Tahlilga yuborish"), reverse("tahlilga_yuborish", args=[o.pk]), "send", "btn")]
        return []
    x = getattr(o, "xulosa", None)
    if o.lab_holat == H.TAHLILDA and not o.topshiriqlar.exists():  # eski yozuvlar: mas'ul tayinlanmagan
        return [(_("Mas'ul tayinlash"), reverse("tahlilga_yuborish", args=[o.pk]), "send", "btn")]
    if o.lab_holat == H.NATIJA and x:
        return [(_("Tekshirish va tasdiqlash"), reverse("xulosa_korish", args=[x.pk]), "check", "btn")]
    if o.lab_holat in (H.TAHLILDA, H.JARAYONDA):
        return []
    if x:
        return [(_("Xulosa"), reverse("xulosa_korish", args=[x.pk]), "eye", ""),
                (_("PDF"), reverse("xulosa_hujjat", args=[x.pk, "pdf"]), "file", "")]
    return []


def _lab_izoh(o):
    H = Namuna.LabHolat
    if o.lab_holat in (H.TAHLILDA, H.JARAYONDA, H.NATIJA):
        return ", ".join(f"{t.masul} — {t.get_holat_display().lower()}" for t in o.topshiriqlar.all())
    if o.lab_holat != H.YANGI:
        return ""
    sh = o.shartnoma if o.shartnoma_id and o.shartnoma.is_active else None
    if not sh:
        return _("Shartnoma tuzilmagan")
    if sh.holat == Shartnoma.Holat.YUBORILMAGAN:
        return _("Shartnoma buxgalteriyaga yuborilmagan")
    if not sh.tahlil_boshlash_mumkin:
        return _("To'lov kutilmoqda (%(f)s%%)") % {"f": sh.tolangan_foiz}
    return _("To'lov qilingan (%(f)s%%)") % {"f": sh.tolangan_foiz}


@role_required(AD, *LAB)
def tahlil_holati(request):
    qs = lab_scope(request, Namuna.objects.select_related("ariza", "namuna_turi", "shartnoma", "xulosa")
                   .prefetch_related("topshiriqlar__masul"))
    cols = [
        Column(_("Namuna"), "__str__", "bold", url=lambda o: reverse("ariza_detail", args=[o.ariza_id])),
        Column(_("Buyurtmachi nomi"), "ariza.buyurtmachi"),
        Column(_("Namuna turi"), lambda o: str(o.namuna_turi)),
        Column(_("Namuna nomi"), "nomi"),
        Column(_("Shartnoma"), lambda o: o.shartnoma.raqam if o.shartnoma_id and o.shartnoma.is_active else "—",
               url=lambda o: reverse("shartnoma_detail", args=[o.shartnoma_id])
               if o.shartnoma_id and o.shartnoma.is_active else ""),
        Column(_("Kelib tushgan vaqti"), "qabul_vaqti", "datetime"),
        Column(_("Tahlil yakunlangan vaqt"), "tahlil_tugagan_vaqti", "datetime"),
        Column(_("Holati"), "get_lab_holat_display", "badge", badge=badge("lab_holat")),
        Column(_("Izoh"), _lab_izoh),
        Column("", _lab_amallar, "actions", excel=False),
    ]
    f = Filters(search_fields=["ariza__raqam", "ariza__buyurtmachi_nomi", "ariza__fish", "nomi"],
                date_field="qabul_vaqti", holat_field="lab_holat", holat_choices=Namuna.LabHolat.choices,
                turi_field="ariza__turi")
    m = sla.Muddat()
    kat = request.user.lab_kategoriya if user_role(request.user) in LAB else None
    return list_page(request, title=_("Laboratoriya tahlil holati"), qs=qs, columns=cols, filters=f,
                     turi_tabs=turi_tabs(), row_class=lambda o: "kechikdi" if m.namuna_lab(o) else "",
                     post_filter=sla.kechikkan_filtri(lambda: sla.kechikkan_namunalar(m, kat)), stats=namuna_stats)


@role_required(AD, *LAB)
def xulosa_list(request):
    qs = lab_scope(request, Xulosa.objects.select_related("namuna__ariza", "namuna__namuna_turi"),
                   "namuna__namuna_turi__kategoriya")
    qs = tur_filtr(request, qs, "namuna__namuna_turi")
    cols = [
        Column(_("Xulosa raqami"), "raqam", "bold", url=lambda o: reverse("xulosa_korish", args=[o.pk])),
        Column(_("Namuna"), "namuna.__str__"),
        Column(_("Buyurtmachi nomi"), "namuna.ariza.buyurtmachi"),
        Column(_("Namuna turi"), lambda o: str(o.namuna.namuna_turi)),
        Column(_("Kelib tushgan vaqti"), "namuna.qabul_vaqti", "datetime"),
        Column(_("Xulosa tayyor qilingan vaqt"), "tayyor_at", "datetime"),
        Column(_("Holati"), "namuna.get_lab_holat_display", "badge",
               badge=lambda o: BADGE.get(o.namuna.lab_holat, "grey")),
        Column(_("Tasdiqlangan"), lambda o: _("Ha") if o.tasdiqlangan else _("Yo'q"), "badge",
               badge=lambda o: "green" if o.tasdiqlangan else "yellow"),
        Column("", lambda o: [(_("Ko'rish"), reverse("xulosa_korish", args=[o.pk]), "eye", ""),
                              (_("PDF"), reverse("xulosa_hujjat", args=[o.pk, "pdf"]), "file", "")],
               "actions", excel=False),
    ]
    f = Filters(search_fields=["raqam", "namuna__ariza__buyurtmachi_nomi", "namuna__ariza__fish"],
                date_field="created_at", turi_field="namuna__ariza__turi")
    return list_page(request, title=_("Xulosa"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs(),
                     stats=xulosa_stats)


# ---------------------------------------------------------------------------
# Narxnoma
# ---------------------------------------------------------------------------
@role_required(BX)  # Super admin ham kiradi (faqat ko'rish)
def narxnoma_list(request):
    qs = Narxnoma.objects.all()
    bux = user_role(request.user) == BX
    cols = [
        Column(_("№"), "tartib"),
        Column(_("Aniqlanadigan tavsiflar (parametrlar) nomi / olib boriladigan ishlar"), "parametr", width="34%"),
        Column(_("Tahlil usuli"), "tahlil_usuli"),
        Column(_("Sinovlar obyektining nomi"), "get_sinov_obyekti_display"),
        Column(_("Narxi, so'm"), "narx", "money"),
        Column(_("Holati"), lambda o: _("Faol") if o.aktiv else _("Nofaol"), "badge",
               badge=lambda o: "green" if o.aktiv else "grey"),
    ]
    if bux:
        cols.append(Column("", lambda o: reverse("narxnoma_edit", args=[o.pk]), "actions", excel=False))
    else:  # Super admin: o'zgarishlar tarixi (faqat unga ko'rinadi)
        cols.append(Column("", lambda o: [(_("O'zgarishlar tarixi"), reverse("nazorat_tarixi")
                                           + f"?holat=narxnoma&obyekt_id={o.pk}", "eye", "")], "actions", excel=False))
    f = Filters(search_fields=["parametr", "tahlil_usuli"], holat_field="sinov_obyekti",
                holat_choices=Narxnoma.SinovObyekti.choices)
    return list_page(request, title=_("Narxnoma"), qs=qs, columns=cols, filters=f,
                     add_url=reverse("narxnoma_add") if bux else None, per_page=50)


NARXNOMA_MAYDONLARI = ["tartib", "parametr", "tahlil_usuli", "sinov_obyekti", "obyekt_nomi", "narx", "har_namunaga",
                       "aktiv"]


def _qiymat(v):
    if isinstance(v, bool):
        return _("Ha") if v else _("Yo'q")
    if isinstance(v, Decimal):
        return f"{int(v):,}".replace(",", " ") if v == v.to_integral() else f"{v:,.2f}".replace(",", " ")
    return v if v not in (None, "") else "—"


@role_required(BX)
def narxnoma_form(request, pk=None):
    if user_role(request.user) != BX:  # Super admin faqat ko'radi
        raise PermissionDenied
    obj = get_object_or_404(Narxnoma, pk=pk) if pk else None
    eski = {f: getattr(obj, f) for f in NARXNOMA_MAYDONLARI} if obj else {}
    form = NarxnomaForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        nx = form.save()
        if obj:
            ozg = []
            for f in NARXNOMA_MAYDONLARI:
                yangi = getattr(nx, f)
                if f == "sinov_obyekti":
                    a, b = dict(Narxnoma.SinovObyekti.choices).get(eski[f]), nx.get_sinov_obyekti_display()
                else:
                    a, b = _qiymat(eski[f]), _qiymat(yangi)
                if eski[f] != yangi:
                    ozg.append(f"{form.fields[f].label}: {a} → {b}")
            tafsilot = "; ".join(ozg)
        else:
            tafsilot = _("Yangi qator qo'shildi. Narxi: %(n)s so'm; usul: %(u)s") % {
                "n": _qiymat(nx.narx), "u": nx.tahlil_usuli or "—"}
        if tafsilot:
            NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.NARXNOMA,
                              f"{nx.parametr[:120]} ({nx.tahlil_usuli or '—'})", tafsilot, nx.pk)
        messages.success(request, _("Saqlandi"))
        return redirect("narxnoma_list")
    return render(request, "core/form.html", {
        "title": _("Narxnoma") + " — " + (_("Tahrirlash") if obj else _("Qo'shish")),
        "form": form, "back": reverse("narxnoma_list"),
    })
