from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from accounts.models import Role

from .forms import NarxnomaForm
from .listing import Column, Filters, list_page
from .models import (Ariza, ArizaTuri, Kategoriya, NamunaTuri, Namuna, Narxnoma, Shartnoma, Xulosa)
from .permissions import ADMINS, AD, BX, LAB, NQ, SA, role_required, user_role

# Holat -> badge rangi
BADGE = {
    "yangi": "red", "qabul": "green", "rad": "grey",
    "kutilmoqda": "red", "qisman": "yellow", "tolangan": "green",
    "yuborilmagan": "grey", "yuborilgan": "yellow",
    "tahlilda": "yellow", "natija": "blue", "xulosa": "green", "berildi": "green",
}


def badge(field):
    return lambda o: BADGE.get(getattr(o, field), "grey")


def turi_tabs():
    return [("", _("Barchasi"))] + list(ArizaTuri.choices)


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
    role = user_role(request.user)
    if role == Role.MIJOZ:
        return redirect("kabinet")

    ctx = {"title": _("Monitoring")}
    if role == NQ:
        ctx["cards"] = [
            (_("Yangi arizalar"), Ariza.objects.filter(holat=Ariza.Holat.YANGI).count(),
             reverse("ariza_list") + "?holat=yangi"),
            (_("Qabul qilingan arizalar"), Ariza.objects.filter(holat=Ariza.Holat.QABUL).count(),
             reverse("ariza_list") + "?holat=qabul"),
        ]
        return render(request, "core/dash_namuna.html", ctx)

    if role == BX:
        ctx["title"] = _("Asosiy panel")
        groups = []
        for kat, label in Kategoriya.choices:
            qs = Shartnoma.objects.filter(is_active=True, ariza__kategoriya=kat).exclude(
                holat=Shartnoma.Holat.YUBORILMAGAN)
            groups.append((label, [
                (lbl, qs.filter(tolov_holati=val).count(),
                 reverse("oferta_list") + f"?kategoriya={kat}&holat={val}")
                for val, lbl in Shartnoma.TolovHolati.choices
            ]))
        ctx["groups"] = groups
        return render(request, "core/dash_bux.html", ctx)

    namunalar = lab_scope(request, Namuna.objects.all())
    if role in LAB:
        ctx["title"] = _("Asosiy panel")
        sh = lab_scope(request, Shartnoma.objects.filter(is_active=True), "ariza__kategoriya")
        ctx["shartnoma_cards"] = [
            (_("Ariza shakllantirilgan, shartnoma tuzilishi kutilmoqda"),
             lab_scope(request, Ariza.objects.filter(holat=Ariza.Holat.QABUL, shartnomalar__isnull=True),
                       "kategoriya").count(), reverse("shartnoma_list")),
            (_("Tuzilgan shartnomalar"), sh.count(), reverse("shartnoma_list")),
        ]
        tayyor = namunalar.filter(lab_holat=Namuna.LabHolat.YANGI, shartnoma__isnull=False)
        tayyor_n = sum(1 for n in tayyor.select_related("shartnoma") if n.shartnoma.tahlil_boshlash_mumkin)
        ctx["shartnoma_cards"].append(
            (_("Tahlil boshlash mumkin bo'lgan namunalar (30%+ to'langan)"), tayyor_n, reverse("tahlil_holati") + "?holat=yangi"))
        ctx["lab_cards"] = [
            (lbl, namunalar.filter(lab_holat=val).count(), reverse("tahlil_holati") + f"?holat={val}")
            for val, lbl in Namuna.LabHolat.choices if val in ("yangi", "tahlilda", "xulosa")
        ]
        ctx["xulosa_total"] = namunalar.filter(xulosa__isnull=False).count()
        ctx["turi_cards"] = _turi_cards(namunalar.filter(xulosa__isnull=False), request.user.lab_kategoriya)
        ctx["kat_labels"] = dict(Kategoriya.choices)
        return render(request, "core/dash_lab.html", ctx)

    # Admin / super admin
    turi = request.GET.get("turi", "")
    if turi:
        namunalar = namunalar.filter(ariza__turi=turi)
    ctx["turi_cards"] = _turi_cards(namunalar)
    ctx["kat_labels"] = dict(Kategoriya.choices)
    ctx["kat_totals"] = {k: namunalar.filter(namuna_turi__kategoriya=k).count() for k in Kategoriya.values}
    ctx["turi_tabs"] = turi_tabs()
    ctx["state"] = {"turi": turi}
    return render(request, "core/dash_admin.html", ctx)


# ---------------------------------------------------------------------------
# Ro'yxatlar
# ---------------------------------------------------------------------------
@role_required(AD, NQ)
def ariza_list(request):
    qs = Ariza.objects.select_related("namuna_turi").prefetch_related("hujjatlar")
    cols = [
        Column(_("Ariza raqami"), "raqam", "bold", url=lambda o: reverse("ariza_detail", args=[o.pk])),
        Column(_("Ariza turi"), "get_turi_display"),
        Column(_("Buyurtmachi nomi"), "buyurtmachi_nomi"),
        Column(_("F.I.SH."), "fish"),
        Column(_("INN"), "inn"),
        Column(_("Telefon nomeri"), "telefon"),
        Column(_("Namuna soni"), "namuna_soni"),
        Column(_("Namuna turi"), "namuna_turi.nomi"),
        Column(_("Namuna nomi"), "namuna_nomi"),
        Column(_("Partiya raqami"), "partiya_raqami"),
        Column(_("Chegara maskani"), "chegara_maskani"),
        Column(_("Sana va vaqti"), "created_at", "datetime"),
        Column(_("Zarur hujjatlar"), lambda o: o.hujjatlar.all(), "file"),
        Column(_("Holati"), "get_holat_display", "badge", badge=badge("holat")),
    ]
    if user_role(request.user) in (NQ, SA):
        cols.append(Column("", lambda o: [(_("Qabul qilish"), reverse("ariza_qabul", args=[o.pk]), "check", "btn")]
                           if o.holat == Ariza.Holat.YANGI else [], "actions", excel=False))
    f = Filters(search_fields=["raqam", "buyurtmachi_nomi", "fish", "inn", "telefon", "namuna_nomi"],
                date_field="created_at", holat_field="holat", holat_choices=Ariza.Holat.choices,
                turi_field="turi")
    return list_page(request, title=_("Ariza"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs())


@role_required(AD, NQ)
def namuna_list(request):
    qs = Namuna.objects.select_related("ariza", "namuna_turi").prefetch_related("ariza__hujjatlar")
    cols = [
        Column(_("Ariza raqami"), "__str__", "bold", url=lambda o: reverse("ariza_detail", args=[o.ariza_id])),
        Column(_("Ariza turi"), "ariza.get_turi_display"),
        Column(_("Namuna olgan mas'ul xodim"), "namuna_olgan"),
        Column(_("Chegara maskani yoki ombor nomi"), "ariza.chegara_maskani"),
        Column(_("Buyurtmachi nomi"), "ariza.buyurtmachi"),
        Column(_("INN"), "ariza.inn"),
        Column(_("Namuna nomi"), "nomi"),
        Column(_("Namuna turi"), "namuna_turi.nomi"),
        Column(_("Namuna qabul qilingan vaqt"), "qabul_vaqti", "datetime"),
        Column(_("Mavjud hujjatlar"), lambda o: o.ariza.hujjatlar.all(), "file"),
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
    return list_page(request, title=_("Namuna"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs())


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
    qs = lab_scope(request, Shartnoma.objects.filter(is_active=True).select_related("ariza"), "ariza__kategoriya")
    cols = _shartnoma_cols() + [
        Column(_("Biriktirilgan hujjatlar"), lambda o: o.ariza.hujjatlar.all(), "file"),
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
    qs = qs.prefetch_related("ariza__hujjatlar")
    return list_page(request, title=_("Shartnoma tuzilishi va bajarilishi"), qs=qs, columns=cols, filters=f,
                     turi_tabs=turi_tabs(), add_url=reverse("shartnoma_tanlash"), add_label=_("Shartnoma tuzish"))


@role_required(AD, BX)
def oferta_list(request):
    qs = Shartnoma.objects.filter(is_active=True).select_related("ariza")
    if user_role(request.user) == BX:
        qs = qs.exclude(holat=Shartnoma.Holat.YUBORILMAGAN)
    kat = request.GET.get("kategoriya")
    if kat in Kategoriya.values:
        qs = qs.filter(ariza__kategoriya=kat)
    cols = _shartnoma_cols() + [
        Column(_("Qoldiq"), "qoldiq", "money"),
        Column(_("Holati"), "get_tolov_holati_display", "badge", badge=badge("tolov_holati")),
        Column(_("Ko'rildi"), lambda o: _("Yangi") if o.holat == Shartnoma.Holat.YUBORILGAN else _("Ko'rilgan"),
               "badge", badge=lambda o: "yellow" if o.holat == Shartnoma.Holat.YUBORILGAN else "green"),
        Column("", lambda o: [
            (_("Ochish / to'lov"), reverse("shartnoma_detail", args=[o.pk]), "eye", ""),
            (_("Shartnoma (PDF)"), reverse("shartnoma_hujjat", args=[o.pk, "pdf"]), "file", ""),
        ], "actions", excel=False),
    ]
    f = Filters(search_fields=["raqam", "ariza__buyurtmachi_nomi", "ariza__fish", "ariza__inn"],
                date_field="created_at", holat_field="tolov_holati",
                holat_choices=Shartnoma.TolovHolati.choices, summa_field="jami_summa", turi_field="ariza__turi")
    return list_page(request, title=_("Oferta"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs(),
                     extra={"kategoriya_tabs": [("", _("Barchasi"))] + list(Kategoriya.choices)})


def _lab_amallar(o):
    """Tahlil holati jadvalidagi har bir namuna uchun navbatdagi amal (dizayndagi izohlar bo'yicha)."""
    H = Namuna.LabHolat
    sh = o.shartnoma if o.shartnoma_id and o.shartnoma.is_active else None
    if o.lab_holat == H.YANGI:
        if sh and sh.tahlil_boshlash_mumkin:
            return [(_("Tahlilga olish"), reverse("tahlilga_olish", args=[o.pk]), "send", "btn post")]
        return []
    if o.lab_holat == H.TAHLILDA:
        return [(_("Natijalar tayyor"), reverse("natija_tayyor", args=[o.pk]), "check", "btn post")]
    if o.lab_holat == H.NATIJA:
        return [(_("Natija kiritish"), reverse("xulosa_kiritish", args=[o.pk]), "edit", "btn")]
    x = getattr(o, "xulosa", None)
    if x:
        return [(_("Xulosa"), reverse("xulosa_korish", args=[x.pk]), "eye", ""),
                (_("PDF"), reverse("xulosa_hujjat", args=[x.pk, "pdf"]), "file", "")]
    return []


def _lab_izoh(o):
    H = Namuna.LabHolat
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
    qs = lab_scope(request, Namuna.objects.select_related("ariza", "namuna_turi", "shartnoma", "xulosa"))
    cols = [
        Column(_("Namuna"), "__str__", "bold", url=lambda o: reverse("ariza_detail", args=[o.ariza_id])),
        Column(_("Buyurtmachi nomi"), "ariza.buyurtmachi"),
        Column(_("Namuna turi"), "namuna_turi.nomi"),
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
    return list_page(request, title=_("Laboratoriya tahlil holati"), qs=qs, columns=cols, filters=f,
                     turi_tabs=turi_tabs())


@role_required(AD, *LAB)
def xulosa_list(request):
    qs = lab_scope(request, Xulosa.objects.select_related("namuna__ariza", "namuna__namuna_turi"),
                   "namuna__namuna_turi__kategoriya")
    cols = [
        Column(_("Xulosa raqami"), "raqam", "bold", url=lambda o: reverse("xulosa_korish", args=[o.pk])),
        Column(_("Namuna"), "namuna.__str__"),
        Column(_("Buyurtmachi nomi"), "namuna.ariza.buyurtmachi"),
        Column(_("Namuna turi"), "namuna.namuna_turi.nomi"),
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
    return list_page(request, title=_("Xulosa"), qs=qs, columns=cols, filters=f, turi_tabs=turi_tabs())


# ---------------------------------------------------------------------------
# Narxnoma
# ---------------------------------------------------------------------------
@role_required(AD, BX)
def narxnoma_list(request):
    qs = Narxnoma.objects.all()
    cols = [
        Column(_("№"), "tartib"),
        Column(_("Aniqlanadigan tavsiflar (parametrlar) nomi / olib boriladigan ishlar"), "parametr", width="34%"),
        Column(_("Tahlil usuli"), "tahlil_usuli"),
        Column(_("Sinovlar obyektining nomi"), "get_sinov_obyekti_display"),
        Column(_("Narxi, so'm"), "narx", "money"),
        Column(_("Holati"), lambda o: _("Faol") if o.aktiv else _("Nofaol"), "badge",
               badge=lambda o: "green" if o.aktiv else "grey"),
        Column("", lambda o: reverse("narxnoma_edit", args=[o.pk]), "actions", excel=False),
    ]
    f = Filters(search_fields=["parametr", "tahlil_usuli"], holat_field="sinov_obyekti",
                holat_choices=Narxnoma.SinovObyekti.choices)
    return list_page(request, title=_("Narxnoma"), qs=qs, columns=cols, filters=f,
                     add_url=reverse("narxnoma_add"), per_page=50)


@role_required(AD, BX)
def narxnoma_form(request, pk=None):
    obj = get_object_or_404(Narxnoma, pk=pk) if pk else None
    form = NarxnomaForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Saqlandi"))
        return redirect("narxnoma_list")
    return render(request, "core/form.html", {
        "title": _("Narxnoma") + (f" — {_('Tahrirlash')}" if obj else f" — {_('Qo‘shish')}"),
        "form": form, "back": reverse("narxnoma_list"),
    })
