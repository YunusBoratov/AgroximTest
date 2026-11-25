"""
2-bosqich: mijoz sayti, ariza berish, kabinet va namuna qabul qiluvchi ishi.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.models import Role

from . import fayl_saqlash, xabarnoma
from .forms import ArizaToplam, NamunaQabulForm, RadForm
from .models import (ARIZA_MAYDONLARI, NAMUNA_MAYDONLARI, REKVIZIT_MAYDONLARI, ZARUR_HUJJATLAR, Ariza, ArizaTuri, Namuna,
                     NazoratTarixi, Shartnoma)
from .permissions import AD, ADMINS, BX, LAB, NQ, hujjat_korinadimi, korinadigan_hujjatlar, role_required, user_role


def _forma_config():
    """JS uchun: har bir ariza turida qaysi maydonlar ko'rinadi va qaysi hujjatlar shart."""
    return json.dumps({
        turi: {
            "majburiy": cfg["majburiy"],
            "ixtiyoriy": cfg["ixtiyoriy"],
            "n_majburiy": NAMUNA_MAYDONLARI[turi]["majburiy"],
            "n_ixtiyoriy": NAMUNA_MAYDONLARI[turi]["ixtiyoriy"],
            "hujjat_shart": [str(h) for h in ZARUR_HUJJATLAR[turi]],
            "hujjatlar": {
                ArizaTuri.IMPORTYOR: ["invoys", "analiz", "guvohnoma"],
                ArizaTuri.DAVLAT: ["guvohnoma", "analiz", "qoshimcha"],
                ArizaTuri.IXTIYORIY: ["guvohnoma", "qoshimcha"],
            }[turi],
            "rekvizit": REKVIZIT_MAYDONLARI if turi != ArizaTuri.IXTIYORIY else ["manzil"],
        }
        for turi, cfg in ARIZA_MAYDONLARI.items()
    })


def _ariza_ctx(toplam, **extra):
    ctx = {"form": toplam.form, "toplam": toplam, "config": _forma_config(), "turi_choices": ArizaTuri.choices}
    ctx.update(extra)
    return ctx


# ---------------------------------------------------------------------------
# Bosh sahifa va mijoz
# ---------------------------------------------------------------------------
def bosh_sahifa(request):
    user = request.user
    if user.is_authenticated:
        if user_role(user) == Role.MIJOZ:
            return redirect("kabinet")
        return redirect("dashboard")
    return render(request, "public/ariza_form.html", _ariza_ctx(ArizaToplam(), preview=True))


def mijoz_required(view):
    @login_required
    def wrapper(request, *args, **kwargs):
        if user_role(request.user) != Role.MIJOZ:
            return redirect("dashboard")
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


def _ariza_forma(request, nom, instance=None, user=None):
    """Ariza formasi: (toplam, saqlangan_ariza | None). Xato bo'lsa yuklangan fayllar vaqtincha saqlanadi."""
    if request.method != "POST":
        fayl_saqlash.tozala(request, nom)
        return ArizaToplam(instance=instance, user=user), None
    toplam = ArizaToplam(request.POST, request.FILES, instance=instance, user=user,
                         saqlangan=fayl_saqlash.ol(request, nom))
    valid = toplam.is_valid()
    fayl_saqlash.yangilarini_saqla(request, nom, toplam)
    if not valid:
        return toplam, None
    with transaction.atomic():
        ariza = toplam.save(user=user)
    request.session.pop(f"ariza_fayllar_{nom}", None)
    return toplam, ariza


@mijoz_required
def ariza_yangi(request):
    form, ariza = _ariza_forma(request, "yangi", user=request.user)
    if ariza:
        messages.success(request, _("Arizangiz qabul qilindi. Ariza raqami: %(r)s") % {"r": ariza.raqam})
        return redirect("kabinet")
    return render(request, "public/ariza_form.html", _ariza_ctx(form))


@login_required
def ariza_tahrirlash(request, pk):
    """Yangi yoki rad etilgan arizani tahrirlab (qayta) yuborish."""
    ariza = get_object_or_404(Ariza, pk=pk)
    role = user_role(request.user)
    if role == Role.MIJOZ:
        if ariza.mijoz_id != request.user.id:
            raise PermissionDenied
    elif role not in (NQ, Role.SUPER_ADMIN):
        raise PermissionDenied
    if ariza.holat == Ariza.Holat.QABUL:
        messages.error(request, _("Qabul qilingan arizani o'zgartirib bo'lmaydi"))
        return redirect("ariza_detail", pk=pk)
    rad_edi = ariza.holat == Ariza.Holat.RAD
    form, saqlandi = _ariza_forma(request, f"tahrir_{pk}", instance=ariza)
    if saqlandi:
        if rad_edi:
            saqlandi.holat = Ariza.Holat.YANGI
            saqlandi.rad_sababi = ""
            saqlandi.qabul_qilgan = None
            saqlandi.qabul_vaqti = None
            saqlandi.yuborilgan_at = timezone.now()
            saqlandi.save(update_fields=["holat", "rad_sababi", "qabul_qilgan", "qabul_vaqti", "yuborilgan_at"])
            messages.success(request, _("Ariza %(r)s qayta yuborildi") % {"r": saqlandi.raqam})
        else:
            messages.success(request, _("Ariza saqlandi"))
        if role == Role.MIJOZ:
            return redirect("kabinet")
        return redirect("ariza_detail", pk=pk)
    ctx = _ariza_ctx(form, title=_("Arizani tahrirlash — %(r)s") % {"r": ariza.raqam}, ariza=ariza,
                     rad_edi=rad_edi)
    tpl = "public/ariza_form.html" if role == Role.MIJOZ else "core/ariza_form.html"
    return render(request, tpl, ctx)


@mijoz_required
def kabinet(request):
    arizalar = (Ariza.objects.filter(mijoz=request.user)
                .select_related("namuna_turi").prefetch_related("namunalar__xulosa", "namunalar__namuna_turi", Prefetch("shartnomalar", Shartnoma.objects.filter(is_active=True))))
    from .views_tolov import click_sozlangan

    return render(request, "public/kabinet.html", {
        "arizalar": arizalar, "click": click_sozlangan(),
        "tg_havola": xabarnoma.telegram_ulash_havolasi(request.user) if not request.user.telegram_chat_id else "",
    })


# ---------------------------------------------------------------------------
# Ariza tafsilotlari va namuna qabul qilish
# ---------------------------------------------------------------------------
def _ariza_access(request, ariza):
    role = user_role(request.user)
    if role == Role.MIJOZ:
        if ariza.mijoz_id != request.user.id:
            raise PermissionDenied
    elif role in LAB and request.user.lab_kategoriya not in ariza.kategoriyalar_list:
        raise PermissionDenied


@login_required
def ariza_detail(request, pk):
    ariza = get_object_or_404(Ariza.objects.select_related("namuna_turi", "qabul_qilgan", "mijoz")
                              .prefetch_related("namunalar__namuna_turi"), pk=pk)
    _ariza_access(request, ariza)
    role = user_role(request.user)
    tpl = "public/ariza_detail.html" if role == Role.MIJOZ else "core/ariza_detail.html"
    return render(request, tpl, {
        "title": _("Ariza") + f" {ariza.raqam}",
        "ariza": ariza,
        "hujjatlar": korinadigan_hujjatlar(request.user, ariza.hujjatlar.all()),
        "namunalar": ariza.namunalar.select_related("namuna_turi"),
        "shartnomalar": ariza.shartnomalar.filter(is_active=True),
        "can_accept": role in (NQ, Role.SUPER_ADMIN) and ariza.holat == Ariza.Holat.YANGI,
        "can_edit": ariza.holat != Ariza.Holat.QABUL and (
            role in (NQ, Role.SUPER_ADMIN) or (role == Role.MIJOZ and ariza.mijoz_id == request.user.id)),
        "can_contract": role in (Role.ADMIN, Role.SUPER_ADMIN, *LAB) and ariza.holat == Ariza.Holat.QABUL
        and not ariza.shartnomalar.filter(is_active=True).exists(),
        "rad_form": RadForm(),
    })


@role_required(NQ)
def ariza_qabul(request, pk):
    """Namuna olib kelingach: har bir namuna ma'lumotini kiritib, laboratoriyaga yuborish."""
    ariza = get_object_or_404(Ariza, pk=pk)
    if ariza.holat != Ariza.Holat.YANGI:
        messages.info(request, _("Bu ariza allaqachon ko'rib chiqilgan"))
        return redirect("ariza_detail", pk=pk)
    bloklar = list(ariza.arizanamunalar.prefetch_related("hujjatlar"))
    if not bloklar:  # juda eski ariza: bloklar yo'q
        bloklar = [None] * ariza.namuna_soni
    forms = []
    for i, blok in enumerate(bloklar):
        initial = {"nomi": (blok.nomi if blok else "") or ariza.namuna_nomi, "namuna_olgan": ariza.fish}
        if ariza.namuna_turi_id:  # eski arizalar: tur oldindan tanlangan
            initial["namuna_turi"] = ariza.namuna_turi_id
        f = NamunaQabulForm(request.POST or None, prefix=f"n{i}", initial=initial,
                            kategoriya=blok.kategoriya if blok else ariza.kategoriya)
        f.blok = blok
        f.blok_hujjatlar = korinadigan_hujjatlar(request.user, blok.hujjatlar.all()) if blok else []
        forms.append(f)
    if request.method == "POST" and all(f.is_valid() for f in forms):
        with transaction.atomic():
            for i, f in enumerate(forms, 1):
                nam = f.save(commit=False)
                nam.ariza = ariza
                nam.ariza_namuna = f.blok
                nam.tartib = i
                nam.qabul_qilgan = request.user
                nam.save()
            ariza.holat = Ariza.Holat.QABUL
            ariza.qabul_qilgan = request.user
            ariza.qabul_vaqti = timezone.now()
            ariza.save(update_fields=["holat", "qabul_qilgan", "qabul_vaqti"])
            xabarnoma.ariza_qabul(ariza)
        messages.success(request, _("Namunalar qabul qilindi va laboratoriyaga yuborildi"))
        return redirect("namuna_list")
    return render(request, "core/ariza_qabul.html", {
        "title": _("Arizani qabul qilish"), "ariza": ariza, "forms": forms,
        "hujjatlar": korinadigan_hujjatlar(request.user, ariza.hujjatlar.all()),
    })


@role_required(NQ)
@require_POST
def ariza_rad(request, pk):
    ariza = get_object_or_404(Ariza, pk=pk, holat=Ariza.Holat.YANGI)
    form = RadForm(request.POST)
    if form.is_valid():
        ariza.holat = Ariza.Holat.RAD
        ariza.rad_sababi = form.cleaned_data["sabab"]
        ariza.qabul_qilgan = request.user
        ariza.qabul_vaqti = timezone.now()
        ariza.save(update_fields=["holat", "rad_sababi", "qabul_qilgan", "qabul_vaqti"])
        NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.ARIZA_RAD, f"{ariza.raqam} — {ariza.buyurtmachi}",
                          _("Sabab: %(s)s") % {"s": ariza.rad_sababi}, ariza.pk)
        xabarnoma.ariza_rad(ariza)
        messages.success(request, _("Ariza rad etildi"))
    return redirect("ariza_list")


@role_required(NQ)
def namuna_yaratish(request):
    """Namuna qabul qiluvchi mijoz nomidan ariza yaratadi (mijoz o'zi kelganda)."""
    form, ariza = _ariza_forma(request, "xodim")
    if ariza:
        messages.success(request, _("Ariza yaratildi. Endi namuna ma'lumotlarini kiriting."))
        return redirect("ariza_qabul", pk=ariza.pk)
    return render(request, "core/ariza_form.html", _ariza_ctx(form, title=_("Namuna yaratish")))


@role_required(NQ)
def namuna_edit(request, pk):
    nam = get_object_or_404(Namuna, pk=pk)
    if nam.lab_holat != Namuna.LabHolat.YANGI:
        messages.error(request, _("Tahlil boshlangan namunani o'zgartirib bo'lmaydi"))
        return redirect("namuna_list")
    form = NamunaQabulForm(request.POST or None, instance=nam)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Saqlandi"))
        return redirect("namuna_list")
    return render(request, "core/form.html", {"title": _("Namuna") + f" {nam}", "form": form,
                                              "back": reverse("namuna_list")})


@role_required(NQ)
@require_POST
def namuna_delete(request, pk):
    nam = get_object_or_404(Namuna, pk=pk)
    if nam.lab_holat != Namuna.LabHolat.YANGI or nam.shartnoma_id:
        messages.error(request, _("Shartnoma tuzilgan yoki tahlil boshlangan namunani o'chirib bo'lmaydi"))
    else:
        ariza = nam.ariza
        nam.delete()
        if not ariza.namunalar.exists():
            ariza.holat = Ariza.Holat.YANGI
            ariza.save(update_fields=["holat"])
        messages.success(request, _("Namuna o'chirildi"))
    return redirect("namuna_list")


@login_required
def ariza_hujjat(request, pk):
    """Ariza hujjatini faqat ruxsati bor foydalanuvchiga beradi (media papka ochiq emas)."""
    from django.http import FileResponse

    from .models import ArizaHujjat

    h = get_object_or_404(ArizaHujjat.objects.select_related("ariza"), pk=pk)
    role = user_role(request.user)
    if role == Role.BUXGALTERIYA and not h.ariza.shartnomalar.exclude(holat=Shartnoma.Holat.YUBORILMAGAN).exists():
        raise PermissionDenied
    _ariza_access(request, h.ariza)
    if not hujjat_korinadimi(request.user, h):
        raise PermissionDenied
    ext = h.fayl.name.rsplit(".", 1)[-1]
    return FileResponse(h.fayl.open("rb"), filename=f"{h.ariza.raqam}_{h.turi}.{ext}",
                        as_attachment=ext not in ("pdf", "jpg", "jpeg", "png"))
