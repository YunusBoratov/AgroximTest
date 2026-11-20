"""
4-bosqich: laboratoriya jarayoni va xulosa (sinov bayonnomasi).

Namuna holatlari: yangi -> tahlilda -> natija -> xulosa -> berildi
- tahlilga olish: shartnoma bo'yicha kamida 30% to'langan bo'lishi shart
- natija kiritish: shartnomadagi ko'rsatkichlar avtomatik xulosa jadvaliga tushadi
- tasdiqlash: laboratoriya xulosani ko'rib chiqib tasdiqlaydi (keyin o'zgartirilmaydi)
- berish: 100% to'lovdan keyin xulosa mijoz kabinetiga chiqadi
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from accounts.models import Role

from .forms import NatijaFormSet, XulosaForm
from .hujjatlar import docx_to_pdf, xulosa_docx
from .models import Namuna, Xulosa, XulosaNatija
from .permissions import AD, LAB, SA, role_required, user_role

H = Namuna.LabHolat
# Namuna olish / tayyorlash xizmatlari xulosa jadvaliga tushmaydi
XIZMAT_SOZLARI = ("namuna olish", "namuna tayyorlash")


def _namuna(request, pk):
    nam = get_object_or_404(Namuna.objects.select_related("ariza", "namuna_turi", "shartnoma"), pk=pk)
    if user_role(request.user) in LAB and request.user.lab_kategoriya != nam.kategoriya:
        raise PermissionDenied
    return nam


def _keyingi(request, default="tahlil_holati"):
    nxt = request.POST.get("next") or request.GET.get("next")
    return nxt if nxt and nxt.startswith("/") and not nxt.startswith("//") else reverse(default)


@role_required(AD, *LAB)
@require_POST
def tahlilga_olish(request, pk):
    nam = _namuna(request, pk)
    if nam.lab_holat != H.YANGI:
        return redirect(_keyingi(request))
    if not nam.shartnoma or not nam.shartnoma.is_active:
        messages.error(request, _("Bu namuna uchun shartnoma tuzilmagan"))
    elif not nam.shartnoma.tahlil_boshlash_mumkin:
        messages.error(request, _("Tahlil kamida %(f)s%% to'lovdan keyin boshlanadi. Hozir to'langan: %(t)s%%") % {
            "f": settings.TAHLIL_BOSHLASH_MIN_FOIZ, "t": nam.shartnoma.tolangan_foiz})
    else:
        nam.lab_holat = H.TAHLILDA
        nam.tahlilga_vaqti = timezone.now()
        nam.tahlil_qabul_qilgan = request.user
        nam.save(update_fields=["lab_holat", "tahlilga_vaqti", "tahlil_qabul_qilgan"])
        messages.success(request, _("Namuna %(n)s tahlilga olindi") % {"n": nam})
    return redirect(_keyingi(request))


@role_required(AD, *LAB)
@require_POST
def natija_tayyor(request, pk):
    nam = _namuna(request, pk)
    if nam.lab_holat == H.TAHLILDA:
        nam.lab_holat = H.NATIJA
        nam.tahlil_tugagan_vaqti = timezone.now()
        nam.save(update_fields=["lab_holat", "tahlil_tugagan_vaqti"])
        messages.success(request, _("Tahlil natijalari tayyor. Endi natijalarni kiriting."))
        return redirect("xulosa_kiritish", pk=nam.pk)
    return redirect(_keyingi(request))


def _xulosa_yarat(nam, user):
    """Xulosani shartnomadagi ko'rsatkichlar va oldingi xulosalardagi ma'lumotlar bilan to'ldirib yaratadi."""
    oldingi = (Xulosa.objects.filter(namuna__namuna_turi__kategoriya=nam.kategoriya)
               .exclude(namuna=nam).order_by("-created_at").first())
    x = Xulosa.objects.create(
        namuna=nam, yaratgan=user, sinov_sanasi=timezone.now(),
        tasdiqlagan=oldingi.tasdiqlagan if oldingi else "",
        bosh_agrokimyogar=oldingi.bosh_agrokimyogar if oldingi else "",
        yetakchi_agrokimyogar=oldingi.yetakchi_agrokimyogar if oldingi else (user.fish or ""),
    )
    rows = [("Tashqi ko‘rinishi, rangi", "")]
    if nam.shartnoma:
        for b in nam.shartnoma.bandlar.all():
            if not b.parametr.lower().startswith(XIZMAT_SOZLARI):
                rows.append((b.parametr, b.tahlil_usuli))
    for i, (k, usul) in enumerate(rows, 1):
        # me'yorni shu namuna turi bo'yicha oxirgi xulosadan olish
        avval = (XulosaNatija.objects.filter(korsatkich=k, xulosa__namuna__namuna_turi=nam.namuna_turi)
                 .exclude(meyor="").order_by("-id").first())
        XulosaNatija.objects.create(xulosa=x, tartib=i, korsatkich=k, sinov_usuli=usul,
                                    meyor=avval.meyor if avval else "")
    return x


@role_required(AD, *LAB)
def xulosa_kiritish(request, pk):
    nam = _namuna(request, pk)
    if nam.lab_holat in (H.YANGI, H.TAHLILDA):
        messages.error(request, _("Avval tahlilni yakunlang (\"Tahlil natijalari tayyor\")"))
        return redirect("tahlil_holati")
    x = getattr(nam, "xulosa", None) or _xulosa_yarat(nam, request.user)
    if x.tasdiqlangan and user_role(request.user) != SA:
        messages.info(request, _("Xulosa tasdiqlangan, uni o'zgartirib bo'lmaydi"))
        return redirect("xulosa_korish", pk=x.pk)

    form = XulosaForm(request.POST or None, instance=x)
    fs = NatijaFormSet(request.POST or None, instance=x, prefix="nt")
    if request.method == "POST" and form.is_valid() and fs.is_valid():
        with transaction.atomic():
            form.save()
            fs.save()
            # tartib formadagi ko'rinish bo'yicha (qo'shilgan qatorlar oxirida)
            qolgan = [f.instance for f in fs.forms
                      if f.instance.pk and not fs._should_delete_form(f)]
            for i, nt in enumerate(qolgan, 1):
                if nt.tartib != i:
                    nt.tartib = i
                    nt.save(update_fields=["tartib"])
            if nam.lab_holat == H.NATIJA:
                nam.lab_holat = H.XULOSA
                nam.save(update_fields=["lab_holat"])
            x.tayyor_at = x.tayyor_at or timezone.now()
            x.save(update_fields=["tayyor_at"])
        messages.success(request, _("Natijalar saqlandi. Xulosani ko'rib chiqib tasdiqlang."))
        return redirect("xulosa_korish", pk=x.pk)
    return render(request, "core/xulosa_form.html", {
        "title": _("Natijalarni kiritish — %(n)s") % {"n": nam}, "nam": nam, "x": x, "form": form, "fs": fs,
    })


@role_required(AD, *LAB)
def xulosa_korish(request, pk):
    x = get_object_or_404(Xulosa.objects.select_related("namuna__ariza", "namuna__shartnoma"), pk=pk)
    _namuna(request, x.namuna_id)
    sh = x.namuna.shartnoma
    return render(request, "core/xulosa_korish.html", {
        "title": _("Sinov bayonnomasi %(r)s") % {"r": x.raqam}, "x": x, "nam": x.namuna, "sh": sh,
        "natijalar": x.natijalar.all(),
        "berish_mumkin": x.tasdiqlangan and sh and sh.xulosa_yuborish_mumkin and x.namuna.lab_holat != H.BERILDI,
    })


@role_required(AD, *LAB)
@require_POST
def xulosa_tasdiqlash(request, pk):
    x = get_object_or_404(Xulosa, pk=pk)
    _namuna(request, x.namuna_id)
    if not x.tasdiqlangan:
        x.tasdiqlangan_at = timezone.now()
        x.tasdiqlagan_user = request.user
        x.save(update_fields=["tasdiqlangan_at", "tasdiqlagan_user"])
        messages.success(request, _("Xulosa tasdiqlandi"))
    return redirect("xulosa_korish", pk=pk)


@role_required(AD, *LAB)
@require_POST
def xulosa_berish(request, pk):
    x = get_object_or_404(Xulosa.objects.select_related("namuna__shartnoma"), pk=pk)
    nam = _namuna(request, x.namuna_id)
    sh = nam.shartnoma
    if not x.tasdiqlangan:
        messages.error(request, _("Avval xulosani tasdiqlang"))
    elif not sh or not sh.xulosa_yuborish_mumkin:
        messages.error(request, _("Xulosa faqat 100%% to'lovdan keyin beriladi. Hozir to'langan: %(t)s%%") % {
            "t": sh.tolangan_foiz if sh else 0})
    else:
        nam.lab_holat = H.BERILDI
        nam.berilgan_vaqti = timezone.now()
        nam.save(update_fields=["lab_holat", "berilgan_vaqti"])
        messages.success(request, _("Xulosa buyurtmachi kabinetiga yuborildi"))
    return redirect("xulosa_korish", pk=pk)


# ---------------------------------------------------------------------------
# Hujjat va QR orqali tekshirish
# ---------------------------------------------------------------------------
def _verify_url(request, x):
    path = reverse("xulosa_tekshirish", args=[x.verify_token])
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{path}" if base else request.build_absolute_uri(path)


@login_required
def xulosa_hujjat(request, pk, fmt):
    x = get_object_or_404(Xulosa.objects.select_related("namuna__ariza", "namuna__namuna_turi"), pk=pk)
    role = user_role(request.user)
    if role == Role.MIJOZ:
        if x.namuna.ariza.mijoz_id != request.user.id or x.namuna.lab_holat != H.BERILDI:
            raise PermissionDenied
    elif role in (Role.BUXGALTERIYA, Role.NAMUNA_QABUL):
        raise PermissionDenied
    else:
        _namuna(request, x.namuna_id)
    return _hujjat_javob(request, x, fmt)


def _hujjat_javob(request, x, fmt):
    data = xulosa_docx(x, _verify_url(request, x))
    if fmt == "pdf":
        try:
            data = docx_to_pdf(data)
        except Exception:
            fmt = "docx"
    resp = HttpResponse(data, content_type="application/pdf" if fmt == "pdf" else
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    resp["Content-Disposition"] = (f'{"inline" if fmt == "pdf" else "attachment"}; '
                                   f'filename="sinov_bayonnomasi_{x.raqam}.{fmt}"')
    return resp


def xulosa_tekshirish(request, token):
    """QR kod orqali ochiladigan ochiq sahifa: bayonnoma haqiqiyligini tasdiqlaydi."""
    x = Xulosa.objects.select_related("namuna__ariza", "namuna__namuna_turi").filter(verify_token=token).first()
    if not x or not x.tasdiqlangan:
        raise Http404
    if request.GET.get("pdf"):
        return _hujjat_javob(request, x, "pdf")
    return render(request, "public/tekshirish.html", {"x": x, "nam": x.namuna, "natijalar": x.natijalar.all()})
