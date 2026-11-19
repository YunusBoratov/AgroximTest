"""
2-bosqich: mijoz sayti, ariza berish, kabinet va namuna qabul qiluvchi ishi.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.models import Role

from .forms import ArizaForm, NamunaQabulForm, RadForm
from .models import ARIZA_MAYDONLARI, REKVIZIT_MAYDONLARI, ZARUR_HUJJATLAR, Ariza, ArizaTuri, Namuna
from .permissions import AD, ADMINS, BX, LAB, NQ, role_required, user_role


def _forma_config():
    """JS uchun: har bir ariza turida qaysi maydonlar ko'rinadi va qaysi hujjatlar shart."""
    return json.dumps({
        turi: {
            "majburiy": cfg["majburiy"],
            "ixtiyoriy": cfg["ixtiyoriy"],
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


def _ariza_ctx(form, **extra):
    ctx = {"form": form, "config": _forma_config(), "turi_choices": ArizaTuri.choices}
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
    return render(request, "public/ariza_form.html", _ariza_ctx(ArizaForm(), preview=True))


def mijoz_required(view):
    @login_required
    def wrapper(request, *args, **kwargs):
        if user_role(request.user) != Role.MIJOZ:
            return redirect("dashboard")
        return view(request, *args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


@mijoz_required
def ariza_yangi(request):
    form = ArizaForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        ariza = form.save(commit=False)
        ariza.mijoz = request.user
        ariza.save()
        form.save_hujjatlar(ariza)
        messages.success(request, _("Arizangiz qabul qilindi. Ariza raqami: %(r)s") % {"r": ariza.raqam})
        return redirect("kabinet")
    return render(request, "public/ariza_form.html", _ariza_ctx(form))


@mijoz_required
def kabinet(request):
    arizalar = (Ariza.objects.filter(mijoz=request.user)
                .select_related("namuna_turi").prefetch_related("namunalar__xulosa", "shartnomalar"))
    return render(request, "public/kabinet.html", {"arizalar": arizalar})


# ---------------------------------------------------------------------------
# Ariza tafsilotlari va namuna qabul qilish
# ---------------------------------------------------------------------------
def _ariza_access(request, ariza):
    role = user_role(request.user)
    if role == Role.MIJOZ:
        if ariza.mijoz_id != request.user.id:
            raise PermissionDenied
    elif role in LAB and request.user.lab_kategoriya != ariza.kategoriya:
        raise PermissionDenied


@login_required
def ariza_detail(request, pk):
    ariza = get_object_or_404(Ariza.objects.select_related("namuna_turi", "qabul_qilgan", "mijoz"), pk=pk)
    _ariza_access(request, ariza)
    role = user_role(request.user)
    tpl = "public/ariza_detail.html" if role == Role.MIJOZ else "core/ariza_detail.html"
    return render(request, tpl, {
        "title": _("Ariza") + f" {ariza.raqam}",
        "ariza": ariza,
        "hujjatlar": ariza.hujjatlar.all(),
        "namunalar": ariza.namunalar.select_related("namuna_turi"),
        "shartnomalar": ariza.shartnomalar.filter(is_active=True),
        "can_accept": role in (NQ, Role.SUPER_ADMIN) and ariza.holat == Ariza.Holat.YANGI,
        "rad_form": RadForm(),
    })


@role_required(NQ)
def ariza_qabul(request, pk):
    """Namuna olib kelingach: har bir namuna ma'lumotini kiritib, laboratoriyaga yuborish."""
    ariza = get_object_or_404(Ariza, pk=pk)
    if ariza.holat != Ariza.Holat.YANGI:
        messages.info(request, _("Bu ariza allaqachon ko'rib chiqilgan"))
        return redirect("ariza_detail", pk=pk)
    initial = {"nomi": ariza.namuna_nomi, "namuna_olgan": ariza.fish}
    forms = [NamunaQabulForm(request.POST or None, prefix=f"n{i}", initial=initial)
             for i in range(ariza.namuna_soni)]
    if request.method == "POST" and all(f.is_valid() for f in forms):
        with transaction.atomic():
            for i, f in enumerate(forms, 1):
                nam = f.save(commit=False)
                nam.ariza = ariza
                nam.tartib = i
                nam.namuna_turi = ariza.namuna_turi
                nam.qabul_qilgan = request.user
                nam.save()
            ariza.holat = Ariza.Holat.QABUL
            ariza.qabul_qilgan = request.user
            ariza.qabul_vaqti = timezone.now()
            ariza.save(update_fields=["holat", "qabul_qilgan", "qabul_vaqti"])
        messages.success(request, _("Namunalar qabul qilindi va laboratoriyaga yuborildi"))
        return redirect("namuna_list")
    return render(request, "core/ariza_qabul.html", {
        "title": _("Namunani qabul qilish"), "ariza": ariza, "forms": forms,
        "hujjatlar": ariza.hujjatlar.all(),
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
        messages.success(request, _("Ariza rad etildi"))
    return redirect("ariza_list")


@role_required(NQ)
def namuna_yaratish(request):
    """Namuna qabul qiluvchi mijoz nomidan ariza yaratadi (mijoz o'zi kelganda)."""
    form = ArizaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        ariza = form.save()
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
