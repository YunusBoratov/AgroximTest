"""
3-bosqich: shartnoma (oferta) tuzish, buxgalteriyaga yuborish, to'lovlar va shartnoma hujjati.
"""
from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from accounts.models import Role

from . import xabarnoma
from .forms import RekvizitForm, TolovForm
from .hujjatlar import docx_to_pdf, shartnoma_docx
from .models import Ariza, Narxnoma, NazoratTarixi, Shartnoma, ShartnomaBand, Tolov
from .permissions import AD, BX, LAB, SA, korinadigan_hujjatlar, role_required, user_role


def _lab_kategoriya_tekshir(request, kategoriya):
    if user_role(request.user) in LAB and request.user.lab_kategoriya != kategoriya:
        raise PermissionDenied


def _narxnoma_qatorlari(kategoriya):
    obyektlar = Narxnoma.KATEGORIYA_OBYEKTLARI.get(kategoriya)
    qs = Narxnoma.objects.filter(aktiv=True)
    if obyektlar:
        qs = qs.filter(sinov_obyekti__in=obyektlar)
    return qs


# ---------------------------------------------------------------------------
# Laboratoriya: shartnoma tuzish
# ---------------------------------------------------------------------------
@role_required(AD, *LAB)
def shartnoma_tanlash(request):
    """Shartnoma tuzilishi kutilayotgan (qabul qilingan) arizalar."""
    qs = (Ariza.objects.filter(holat=Ariza.Holat.QABUL)
          .exclude(shartnomalar__is_active=True)
          .select_related("namuna_turi").prefetch_related("namunalar"))
    kat = request.user.lab_kategoriya if user_role(request.user) in LAB else None
    if kat:
        qs = qs.filter(kategoriya=kat)
    return render(request, "core/shartnoma_tanlash.html", {"title": _("Yangi shartnoma"), "arizalar": qs})


def _bandlar_postdan(request, qatorlar):
    tanlangan = []
    for nx in qatorlar:
        if request.POST.get(f"band_{nx.pk}"):
            try:
                soni = int(request.POST.get(f"soni_{nx.pk}") or 1)
            except ValueError:
                soni = 1
            tanlangan.append((nx, max(1, min(soni, 100))))
    return tanlangan


@role_required(AD, *LAB)
def shartnoma_form(request, ariza_pk=None, pk=None):
    """Narxnomadan tekshiriladigan ko'rsatkichlarni tanlab shartnoma tuzish yoki tahrirlash."""
    if pk:
        sh = get_object_or_404(Shartnoma.objects.select_related("ariza"), pk=pk, is_active=True)
        ariza = sh.ariza
        if not sh.tahrirlash_mumkin:
            messages.error(request, _("Buxgalteriyaga yuborilgan yoki to'lov qilingan shartnomani o'zgartirib bo'lmaydi"))
            return redirect("shartnoma_detail", pk=sh.pk)
    else:
        sh = None
        ariza = get_object_or_404(Ariza, pk=ariza_pk, holat=Ariza.Holat.QABUL)
        if ariza.shartnomalar.filter(is_active=True).exists():
            messages.info(request, _("Bu ariza uchun shartnoma allaqachon tuzilgan"))
            return redirect("shartnoma_detail", pk=ariza.shartnomalar.filter(is_active=True).first().pk)
    _lab_kategoriya_tekshir(request, ariza.kategoriya)

    qatorlar = list(_narxnoma_qatorlari(ariza.kategoriya))
    namuna_soni = ariza.namunalar.count() or ariza.namuna_soni
    oldingi = {b.narxnoma_id: b.namuna_soni for b in sh.bandlar.all()} if sh else {}

    if request.method == "POST":
        tanlangan = _bandlar_postdan(request, qatorlar)
        if not tanlangan:
            messages.error(request, _("Kamida bitta ko'rsatkich tanlang"))
        else:
            with transaction.atomic():
                if sh is None:
                    sh = Shartnoma.objects.create(ariza=ariza, yaratgan=request.user)
                    ariza.namunalar.update(shartnoma=sh)
                else:
                    sh.bandlar.all().delete()
                for nx, soni in tanlangan:
                    ShartnomaBand.objects.create(shartnoma=sh, narxnoma=nx, narx=nx.narx, namuna_soni=soni)
                sh.qayta_hisobla()
            messages.success(request, _("Shartnoma №%(r)s saqlandi") % {"r": sh.raqam})
            return redirect("shartnoma_detail", pk=sh.pk)
        oldingi = {nx.pk: soni for nx, soni in _bandlar_postdan(request, qatorlar)}

    rows = [(nx, nx.pk in oldingi, oldingi.get(nx.pk, namuna_soni)) for nx in qatorlar]
    return render(request, "core/shartnoma_form.html", {
        "title": (_("Shartnoma №%(r)s — ko'rsatkichlar") % {"r": sh.raqam}) if sh else _("Yangi shartnoma"),
        "ariza": ariza, "sh": sh, "rows": rows, "namuna_soni": namuna_soni,
        "hujjatlar": korinadigan_hujjatlar(request.user, ariza.hujjatlar.all()),
    })


# ---------------------------------------------------------------------------
# Shartnoma sahifasi (laboratoriya, buxgalteriya, admin)
# ---------------------------------------------------------------------------
@role_required(AD, BX, *LAB)
def shartnoma_detail(request, pk):
    sh = get_object_or_404(Shartnoma.objects.select_related("ariza", "ariza__namuna_turi", "yaratgan"),
                           pk=pk, is_active=True)
    role = user_role(request.user)
    _lab_kategoriya_tekshir(request, sh.ariza.kategoriya)
    if role == BX and sh.holat == Shartnoma.Holat.YUBORILMAGAN:
        raise PermissionDenied

    # Buxgalter ochib ko'rgach — "Buxgalter qabul qilgan" (dizayndagi izoh bo'yicha)
    if role == BX and sh.holat == Shartnoma.Holat.YUBORILGAN:
        sh.holat = Shartnoma.Holat.QABUL
        sh.qabul_at = timezone.now()
        sh.save(update_fields=["holat", "qabul_at"])

    is_bux = role in (BX, SA)
    rek_form = RekvizitForm(instance=sh.ariza) if is_bux else None
    tolov_form = TolovForm(qoldiq=sh.qoldiq, initial={"sana": timezone.localdate(), "summa": sh.qoldiq}) \
        if is_bux and sh.qoldiq > 0 else None
    return render(request, "core/shartnoma_detail.html", {
        "title": _("Shartnoma №%(r)s") % {"r": sh.raqam},
        "sh": sh, "ariza": sh.ariza, "bandlar": sh.bandlar.select_related("narxnoma"),
        "tolovlar": sh.tolovlar.select_related("kiritgan"), "namunalar": sh.namunalar.all(),
        "hujjatlar": korinadigan_hujjatlar(request.user, sh.ariza.hujjatlar.all()),
        "is_lab": role in LAB or role in (AD, SA), "is_bux": is_bux,
        "tolov_ochirish_mumkin": sh.tolov_ochirish_mumkin,
        "rek_form": rek_form, "tolov_form": tolov_form,
    })


@role_required(AD, *LAB)
@require_POST
def shartnoma_yuborish(request, pk):
    sh = get_object_or_404(Shartnoma, pk=pk, is_active=True)
    _lab_kategoriya_tekshir(request, sh.ariza.kategoriya)
    if sh.holat == Shartnoma.Holat.YUBORILMAGAN and sh.jami_summa > 0:
        sh.holat = Shartnoma.Holat.YUBORILGAN
        sh.yuborilgan_at = timezone.now()
        sh.save(update_fields=["holat", "yuborilgan_at"])
        xabarnoma.shartnoma_tayyor(sh)
        messages.success(request, _("Shartnoma buxgalteriyaga yuborildi"))
    return redirect("shartnoma_detail", pk=pk)


@role_required(AD, *LAB)
@require_POST
def shartnoma_ochirish(request, pk):
    sh = get_object_or_404(Shartnoma, pk=pk, is_active=True)
    _lab_kategoriya_tekshir(request, sh.ariza.kategoriya)
    if not sh.tahrirlash_mumkin:
        messages.error(request, _("Buxgalteriyaga yuborilgan shartnomani o'chirib bo'lmaydi"))
        return redirect("shartnoma_detail", pk=pk)
    with transaction.atomic():
        sh.is_active = False
        sh.save(update_fields=["is_active"])
        sh.namunalar.update(shartnoma=None)
    messages.success(request, _("Shartnoma o'chirildi"))
    return redirect("shartnoma_list")


# ---------------------------------------------------------------------------
# Buxgalteriya: rekvizitlar va to'lovlar
# ---------------------------------------------------------------------------
@role_required(BX)
@require_POST
def rekvizit_saqlash(request, pk):
    sh = get_object_or_404(Shartnoma, pk=pk, is_active=True)
    form = RekvizitForm(request.POST, instance=sh.ariza)
    if form.is_valid():
        form.save()
        messages.success(request, _("Rekvizitlar saqlandi"))
    else:
        messages.error(request, _("Rekvizitlarda xato bor: %(e)s") % {"e": form.errors.as_text()})
    return redirect("shartnoma_detail", pk=pk)


@role_required(BX)
@require_POST
def tolov_qoshish(request, pk):
    sh = get_object_or_404(Shartnoma, pk=pk, is_active=True)
    if sh.holat == Shartnoma.Holat.YUBORILMAGAN:
        raise PermissionDenied
    form = TolovForm(request.POST, qoldiq=sh.qoldiq)
    if form.is_valid():
        d = form.cleaned_data
        sana = timezone.make_aware(datetime.combine(d["sana"], time(12, 0)))
        with transaction.atomic():
            Tolov.objects.create(shartnoma=sh, summa=d["summa"], usul=d["usul"], sana=sana, izoh=d["izoh"],
                                 kiritgan=request.user)
            oldin_mumkin = sh.tahlil_boshlash_mumkin
            sh.qayta_hisobla()
            xabarnoma.tolov_qabul(sh, d["summa"])
        msg = _("To'lov kiritildi. To'langan: %(f)s%%") % {"f": sh.tolangan_foiz}
        if sh.tahlil_boshlash_mumkin and not oldin_mumkin:
            msg += " " + _("Laboratoriyada tahlil boshlash mumkin.")
        messages.success(request, msg)
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("shartnoma_detail", pk=pk)


@role_required(BX)
@require_POST
def tolov_ochirish(request, pk, tolov_pk):
    t = get_object_or_404(Tolov.objects.select_related("shartnoma__ariza"), pk=tolov_pk, shartnoma_id=pk)
    sh = t.shartnoma
    sabab = (request.POST.get("sabab") or "").strip()
    if not sh.tolov_ochirish_mumkin:
        messages.error(request, _("Namuna tahlilga olingan. Bu shartnoma bo'yicha to'lovni o'chirib bo'lmaydi."))
        return redirect("shartnoma_detail", pk=pk)
    if len(sabab) < 3:
        messages.error(request, _("To'lovni o'chirish sababini yozing"))
        return redirect("shartnoma_detail", pk=pk)
    with transaction.atomic():
        NazoratTarixi.yoz(
            request.user, NazoratTarixi.Turi.TOLOV_OCHIRISH, f"Shartnoma №{sh.raqam} — {sh.ariza.buyurtmachi}",
            _("Summa: %(s)s so'm; usul: %(u)s; to'lov sanasi: %(d)s; izoh: %(i)s; sabab: %(r)s") % {
                "s": f"{int(t.summa):,}".replace(",", " "), "u": t.get_usul_display(),
                "d": timezone.localtime(t.sana).strftime("%d.%m.%Y"), "i": t.izoh or "—", "r": sabab},
            sh.pk)
        t.delete()
        sh.qayta_hisobla()
    messages.success(request, _("To'lov o'chirildi"))
    return redirect("shartnoma_detail", pk=pk)


# ---------------------------------------------------------------------------
# Shartnoma hujjati (DOCX / PDF) — xodimlar va shartnoma egasi (mijoz)
# ---------------------------------------------------------------------------
@login_required
@xframe_options_sameorigin
def shartnoma_hujjat(request, pk, fmt):
    sh = get_object_or_404(Shartnoma.objects.select_related("ariza"), pk=pk, is_active=True)
    role = user_role(request.user)
    if role == Role.MIJOZ:
        if sh.ariza.mijoz_id != request.user.id or sh.holat == Shartnoma.Holat.YUBORILMAGAN:
            raise PermissionDenied
    elif role == Role.NAMUNA_QABUL:
        raise PermissionDenied
    else:
        _lab_kategoriya_tekshir(request, sh.ariza.kategoriya)
    data = shartnoma_docx(sh)
    nom = f"shartnoma_{sh.raqam}"
    if fmt == "pdf":
        try:
            data = docx_to_pdf(data)
        except Exception:  # LibreOffice yo'q yoki xato — Word fayl beriladi
            messages.error(request, _("PDF yaratib bo'lmadi, Word fayl yuklab olinadi"))
            fmt = "docx"
    ctype = "application/pdf" if fmt == "pdf" else \
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    resp = HttpResponse(data, content_type=ctype)
    disp = "inline" if fmt == "pdf" else "attachment"
    resp["Content-Disposition"] = f'{disp}; filename="{nom}.{fmt}"'
    return resp
