"""
Laboratoriya jarayoni va xulosa (sinov bayonnomasi).

Namuna holatlari:
  yangi -> tahlilda (mas'ullarga yuborildi) -> jarayonda (mas'ullar qabul qildi)
        -> natija (hammasi natija yubordi, "Xulosa tayyor") -> xulosa (mudir tasdiqladi) -> berildi

- Tahlilga yuborish: kamida 30% to'langan bo'lishi shart. Mudir har bir ko'rsatkichga mas'ul xodim tanlaydi.
- Mas'ul: topshiriqni qabul qiladi, o'z ko'rsatkichlari natijasini kiritadi (hamma maydon majburiy) va yuboradi.
- Mudir: xulosani tekshiradi, tasdiqlaydi yoki izoh bilan mas'ulga qaytaradi.
- Berish: faqat 100% to'lovdan keyin xulosa mijoz kabinetiga chiqadi.
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from accounts.models import Role, User

from . import xabarnoma
from .forms import MeyorFormSet, NatijaFormSet, QaytarishForm, XulosaForm, masul_xodimlar
from .hujjatlar import docx_to_pdf, xulosa_docx
from .models import BosqichTarixi, Namuna, NazoratTarixi, Topshiriq, Xulosa, XulosaNatija
from .permissions import AD, LAB, MASUL, SA, korinadigan_hujjatlar, role_required, user_role

H = Namuna.LabHolat
T = Topshiriq.Holat
# Namuna olish / tayyorlash xizmatlari xulosa jadvaliga tushmaydi
XIZMAT_SOZLARI = ("namuna olish", "namuna tayyorlash")
TASHQI = "Tashqi ko‘rinishi, rangi"

log = logging.getLogger("core.hujjat")


def _namuna(request, pk):
    nam = get_object_or_404(Namuna.objects.select_related("ariza", "namuna_turi", "shartnoma"), pk=pk)
    if user_role(request.user) in LAB and request.user.lab_kategoriya != nam.kategoriya:
        raise PermissionDenied
    return nam


def namuna_holatini_yangila(nam):
    """Topshiriqlar holatiga qarab namuna holatini aniqlaydi (tasdiqlangan/berilganiga tegmaydi)."""
    if nam.lab_holat in (H.XULOSA, H.BERILDI):
        return
    holatlar = list(nam.topshiriqlar.values_list("holat", flat=True))
    if not holatlar:
        return
    if T.YUBORILDI in holatlar:
        yangi = H.TAHLILDA
    elif all(h == T.TAYYOR for h in holatlar):
        yangi = H.NATIJA
    else:
        yangi = H.JARAYONDA
    if yangi != nam.lab_holat:
        nam.lab_holat = yangi
        fields = ["lab_holat"]
        if yangi == H.NATIJA:
            nam.tahlil_tugagan_vaqti = timezone.now()
            fields.append("tahlil_tugagan_vaqti")
        nam.save(update_fields=fields)


# ---------------------------------------------------------------------------
# Mudir: ko'rsatkichlarni mas'ullarga taqsimlab tahlilga yuborish
# ---------------------------------------------------------------------------
def _qatorlar(nam):
    """Xulosa jadvali qatorlari: [(ko'rsatkich, usul, mavjud XulosaNatija | None)]."""
    x = getattr(nam, "xulosa", None)
    if x and x.natijalar.exists():  # oldin yaratilgan (eski) xulosa
        return [(n.korsatkich, n.sinov_usuli, n) for n in x.natijalar.all()]
    rows = [(TASHQI, "", None)]
    if nam.shartnoma:
        for b in nam.shartnoma.bandlar.all():
            if not b.parametr.lower().startswith(XIZMAT_SOZLARI):
                rows.append((b.parametr, b.tahlil_usuli, None))
    return rows


@role_required(*LAB)
def tahlilga_yuborish(request, pk):
    nam = _namuna(request, pk)
    if nam.topshiriqlar.exists() or nam.lab_holat not in (H.YANGI, H.TAHLILDA):
        messages.info(request, _("Bu namuna allaqachon mas'ullarga yuborilgan"))
        return redirect("tahlil_holati")
    sh = nam.shartnoma
    if not sh or not sh.is_active:
        messages.error(request, _("Bu namuna uchun shartnoma tuzilmagan"))
        return redirect("tahlil_holati")
    if nam.lab_holat == H.YANGI and not sh.tahlil_boshlash_mumkin:
        messages.error(request, _("Tahlil kamida %(f)s%% to'lovdan keyin boshlanadi. Hozir to'langan: %(t)s%%") % {
            "f": settings.TAHLIL_BOSHLASH_MIN_FOIZ, "t": sh.tolangan_foiz})
        return redirect("tahlil_holati")
    masullar = list(masul_xodimlar(nam.kategoriya))
    rows = _qatorlar(nam)
    tanlov = {}
    if request.method == "POST":
        ids = {str(u.pk): u for u in masullar}
        for i, _row in enumerate(rows):
            tanlov[i] = request.POST.get(f"masul_{i}", "")
        if not masullar:
            messages.error(request, _("Laboratoriyada mas'ul xodim yo'q. Avval 'Xodimlar' bo'limida qo'shing."))
        elif any(v not in ids for v in tanlov.values()):
            messages.error(request, _("Har bir ko'rsatkich uchun mas'ul xodimni tanlang"))
        else:
            with transaction.atomic():
                x = getattr(nam, "xulosa", None) or Xulosa.objects.create(
                    namuna=nam, yaratgan=request.user, tasdiqlagan=request.user.fish or request.user.username)
                topshiriqlar = {}
                for uid in set(tanlov.values()):
                    topshiriqlar[uid] = Topshiriq.objects.create(namuna=nam, masul=ids[uid], yuborgan=request.user)
                for i, (k, usul, mavjud) in enumerate(rows):
                    t = topshiriqlar[tanlov[i]]
                    if mavjud:
                        mavjud.topshiriq = t
                        mavjud.save(update_fields=["topshiriq"])
                        continue
                    avval = (XulosaNatija.objects.filter(korsatkich=k, xulosa__namuna__namuna_turi=nam.namuna_turi)
                             .exclude(meyor="").order_by("-id").first())
                    XulosaNatija.objects.create(xulosa=x, tartib=i + 1, korsatkich=k, sinov_usuli=usul,
                                                meyor=avval.meyor if avval else "", topshiriq=t)
                nam.lab_holat = H.TAHLILDA
                nam.tahlilga_vaqti = timezone.now()
                nam.tahlil_qabul_qilgan = request.user
                nam.save(update_fields=["lab_holat", "tahlilga_vaqti", "tahlil_qabul_qilgan"])
                BosqichTarixi.yoz(nam.ariza, _("Mas'ullarga tahlilga yuborildi"), user=request.user, namuna=nam,
                                  izoh=", ".join(str(t.masul) for t in topshiriqlar.values()))
                for t in topshiriqlar.values():
                    xabarnoma.masulga_topshiriq(t)
            messages.success(request, _("Namuna %(n)s mas'ullarga tahlil uchun yuborildi") % {"n": nam})
            return redirect("tahlil_holati")
    return render(request, "core/tahlilga_yuborish.html", {
        "title": _("Tahlilga yuborish — %(n)s") % {"n": nam}, "nam": nam, "masullar": masullar,
        "rows": [(i, k, usul, tanlov.get(i, "")) for i, (k, usul, _m) in enumerate(rows)],
    })


# ---------------------------------------------------------------------------
# Mas'ul xodim paneli
# ---------------------------------------------------------------------------
def _topshiriq(request, pk):
    t = get_object_or_404(Topshiriq.objects.select_related("namuna__ariza", "namuna__namuna_turi", "masul"), pk=pk)
    if t.masul_id != request.user.id:
        raise PermissionDenied
    return t


@role_required(*MASUL)
def masul_topshiriqlar(request):
    from . import sla
    from .listing import Column, Filters, list_page

    m = sla.Muddat()

    qs = Topshiriq.objects.filter(masul=request.user).select_related("namuna__ariza", "namuna__namuna_turi")

    def amallar(t):
        if t.holat == T.YUBORILDI:
            return [(_("Qabul qilish"), reverse("topshiriq_qabul", args=[t.pk]), "check", "btn post")]
        if t.tahrirlash_mumkin:
            return [(_("Natija kiritish"), reverse("topshiriq_natija", args=[t.pk]), "edit", "btn")]
        return [(_("Ko'rish"), reverse("topshiriq_natija", args=[t.pk]), "eye", "")]

    cols = [
        Column(_("Namuna"), lambda t: str(t.namuna), "bold", url=lambda t: reverse("topshiriq_natija", args=[t.pk])),
        Column(_("Buyurtmachi nomi"), lambda t: t.namuna.ariza.buyurtmachi),
        Column(_("Namuna turi"), lambda t: str(t.namuna.namuna_turi)),
        Column(_("Namuna nomi"), "namuna.nomi"),
        Column(_("Ko'rsatkichlar"), lambda t: t.natijalar.count()),
        Column(_("Yuborilgan vaqt"), "yuborilgan_at", "datetime"),
        Column(_("Holati"), "get_holat_display", "badge",
               badge=lambda t: {"yuborildi": "red", "qabul": "yellow", "tayyor": "green", "qaytarildi": "red"}[t.holat]),
        Column("", amallar, "actions", excel=False),
    ]
    f = Filters(search_fields=["namuna__ariza__raqam", "namuna__ariza__buyurtmachi_nomi", "namuna__nomi"],
                date_field="yuborilgan_at", holat_field="holat", holat_choices=T.choices)
    return list_page(request, title=_("Topshiriqlar"), qs=qs, columns=cols, filters=f,
                     row_class=lambda t: "kechikdi" if m.topshiriq(t) else "",
                     post_filter=sla.kechikkan_filtri(lambda: sla.kechikkan_topshiriqlar(m, request.user)),
                     stats=lambda q: [(_("Jami topshiriqlar"), q.count(), "")] + [
                         (lbl, n, "red" if val in ("yuborildi", "qaytarildi") else "")
                         for val, lbl in T.choices for n in [q.filter(holat=val).count()] if n],
                     extra={"tg_havola": xabarnoma.telegram_ulash_havolasi(request.user)
                            if not request.user.telegram_chat_id else ""})


@role_required(*MASUL)
@require_POST
def topshiriq_qabul(request, pk):
    t = _topshiriq(request, pk)
    if t.holat == T.YUBORILDI:
        t.holat = T.QABUL
        t.qabul_at = timezone.now()
        t.save(update_fields=["holat", "qabul_at"])
        BosqichTarixi.yoz(t.namuna.ariza, _("Mas'ul topshiriqni qabul qildi"), user=request.user, namuna=t.namuna)
        namuna_holatini_yangila(t.namuna)
        messages.success(request, _("Topshiriq qabul qilindi. Natijalarni kiriting."))
        return redirect("topshiriq_natija", pk=pk)
    return redirect("masul_topshiriqlar")


@role_required(*MASUL)
def topshiriq_natija(request, pk):
    t = _topshiriq(request, pk)
    qs = t.natijalar.order_by("tartib", "id")
    fs = NatijaFormSet(request.POST or None, queryset=qs, prefix="nt")
    if request.method == "POST":
        if not t.tahrirlash_mumkin:
            raise PermissionDenied
        if fs.is_valid():
            with transaction.atomic():
                fs.save()
                t.holat = T.TAYYOR
                t.tayyor_at = timezone.now()
                t.save(update_fields=["holat", "tayyor_at"])
                BosqichTarixi.yoz(t.namuna.ariza, _("Mas'ul natijani yubordi"), user=request.user, namuna=t.namuna)
                namuna_holatini_yangila(t.namuna)
            messages.success(request, _("Natijalar yuborildi"))
            return redirect("masul_topshiriqlar")
        messages.error(request, _("Barcha maydonlarni to'ldiring"))
    nam = t.namuna
    return render(request, "core/topshiriq_natija.html", {
        "title": _("Natijalarni kiritish — %(n)s") % {"n": nam}, "t": t, "nam": nam, "fs": fs,
        "tahrir": t.tahrirlash_mumkin,
    })


# ---------------------------------------------------------------------------
# Mudir: tekshirish, tasdiqlash yoki qaytarish
# ---------------------------------------------------------------------------
def _xulosa_ctx(request, x, nam, form=None, meyor_fs=None):
    sh = nam.shartnoma
    mudir = user_role(request.user) in LAB or user_role(request.user) == SA
    tekshiruv = mudir and not x.tasdiqlangan and nam.lab_holat == H.NATIJA
    natijalar = x.natijalar.select_related("topshiriq__masul").order_by("tartib", "id")
    if tekshiruv:
        form = form or XulosaForm(instance=x)
        meyor_fs = meyor_fs or MeyorFormSet(queryset=natijalar, prefix="my")
    return {
        "title": _("Sinov bayonnomasi %(r)s") % {"r": x.raqam}, "x": x, "nam": nam, "sh": sh,
        "natijalar": natijalar, "meyor_fs": meyor_fs,
        "topshiriqlar": nam.topshiriqlar.select_related("masul"),
        "tekshiruv": tekshiruv, "form": form,
        "qaytarish_form": QaytarishForm(namuna=nam) if tekshiruv else None,
        "word_mumkin": user_role(request.user) in LAB,
        "berish_mumkin": mudir and x.tasdiqlangan and sh and sh.xulosa_yuborish_mumkin and nam.lab_holat != H.BERILDI,
        "bosqichlar": BosqichTarixi.objects.filter(ariza=nam.ariza).filter(
            Q(namuna__isnull=True) | Q(namuna=nam)),
    }


@role_required(AD, *LAB)
def xulosa_korish(request, pk):
    x = get_object_or_404(Xulosa.objects.select_related("namuna__ariza", "namuna__shartnoma"), pk=pk)
    nam = _namuna(request, x.namuna_id)
    return render(request, "core/xulosa_korish.html", _xulosa_ctx(request, x, nam))


@role_required(*LAB)
@require_POST
def xulosa_tasdiqlash(request, pk):
    x = get_object_or_404(Xulosa, pk=pk)
    nam = _namuna(request, x.namuna_id)
    if x.tasdiqlangan or nam.lab_holat != H.NATIJA:
        messages.error(request, _("Xulosani hozir tasdiqlab bo'lmaydi: barcha mas'ullar natijani yuborishi kerak"))
        return redirect("xulosa_korish", pk=pk)
    form = XulosaForm(request.POST, instance=x)
    meyor_fs = MeyorFormSet(request.POST, queryset=x.natijalar.order_by("tartib", "id"), prefix="my")
    if not (form.is_valid() and meyor_fs.is_valid()):
        messages.error(request, _("Formada xatolar bor, tekshiring"))
        return render(request, "core/xulosa_korish.html", _xulosa_ctx(request, x, nam, form, meyor_fs))
    with transaction.atomic():
        meyor_fs.save()
        x = form.save(commit=False)
        x.sinov_sanasi = timezone.now()  # xulosa kiritilgan (tasdiqlangan) aniq vaqt
        x.tasdiqlagan = request.user.fish or request.user.username
        x.tayyor_at = x.tayyor_at or timezone.now()
        x.tasdiqlangan_at = timezone.now()
        x.tasdiqlagan_user = request.user
        x.save()
        nam.ogirligi, nam.tavsifi = form.cleaned_data["ogirligi"], form.cleaned_data.get("tavsifi", "")
        nam.lab_holat = H.XULOSA
        nam.save(update_fields=["ogirligi", "tavsifi", "lab_holat"])
        BosqichTarixi.yoz(nam.ariza, _("Xulosa tasdiqlandi"), user=request.user, namuna=nam, izoh=x.raqam)
    messages.success(request, _("Xulosa tasdiqlandi"))
    return redirect("xulosa_korish", pk=pk)


@role_required(*LAB)
@require_POST
def xulosa_qaytarish(request, pk):
    x = get_object_or_404(Xulosa, pk=pk)
    nam = _namuna(request, x.namuna_id)
    form = QaytarishForm(request.POST, namuna=nam)
    if x.tasdiqlangan or not form.is_valid():
        messages.error(request, _("Kimga qaytarilishini va sababini yozing"))
        return redirect("xulosa_korish", pk=pk)
    t = form.cleaned_data["topshiriq"]
    with transaction.atomic():
        t.holat = T.QAYTARILDI
        t.izoh = form.cleaned_data["izoh"]
        t.qaytarilgan_at = timezone.now()
        t.save(update_fields=["holat", "izoh", "qaytarilgan_at"])
        BosqichTarixi.yoz(nam.ariza, _("Natija mas'ulga qaytarildi"), user=request.user, namuna=nam,
                          izoh=f"{t.masul}: {t.izoh}")
        namuna_holatini_yangila(nam)
        NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.XULOSA_QAYTARISH, f"{x.raqam} ({nam})",
                          _("Mas'ul: %(m)s; sabab: %(s)s") % {"m": t.masul, "s": t.izoh}, x.pk)
        xabarnoma.masulga_qaytarildi(t)
    messages.success(request, _("Xulosa %(m)s ga tuzatish uchun qaytarildi") % {"m": t.masul})
    return redirect("tahlil_holati")


@role_required(*LAB)
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
        BosqichTarixi.yoz(nam.ariza, _("Bayonnoma buyurtmachiga berildi"), user=request.user, namuna=nam,
                          izoh=x.raqam)
        url = _verify_url(request, x)
        xabarnoma.xulosa_berildi(x, pdf_fn=lambda: _himoyalangan_pdf(x, url))
        messages.success(request, _("Xulosa buyurtmachi kabinetiga yuborildi"))
    return redirect("xulosa_korish", pk=pk)


# ---------------------------------------------------------------------------
# Hujjat va QR orqali tekshirish
# ---------------------------------------------------------------------------
def _verify_url(request, x):
    path = reverse("xulosa_tekshirish", args=[x.verify_token])
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{path}" if base else request.build_absolute_uri(path)


def _himoyalangan_pdf(x, verify_url):
    from .hujjatlar import pdf_himoyala

    return pdf_himoyala(docx_to_pdf(xulosa_docx(x, verify_url)))


@login_required
@xframe_options_sameorigin
def xulosa_hujjat(request, pk, fmt):
    x = get_object_or_404(Xulosa.objects.select_related("namuna__ariza", "namuna__namuna_turi"), pk=pk)
    role = user_role(request.user)
    if role == Role.MIJOZ:
        if x.namuna.ariza.mijoz_id != request.user.id or x.namuna.lab_holat != H.BERILDI:
            raise PermissionDenied
    elif role == Role.NAMUNA_QABUL:
        if not x.tasdiqlangan:
            raise PermissionDenied
    elif role in MASUL:
        if not x.namuna.topshiriqlar.filter(masul=request.user).exists():
            raise PermissionDenied
    elif role == Role.BUXGALTERIYA:
        raise PermissionDenied
    else:
        _namuna(request, x.namuna_id)
    if fmt == "docx" and role not in LAB:  # Word (tahrirlanadigan) faqat laboratoriya mudiriga
        raise PermissionDenied
    return _hujjat_javob(request, x, fmt)


def _hujjat_javob(request, x, fmt):
    if fmt == "pdf":
        try:
            data, ctype = _himoyalangan_pdf(x, _verify_url(request, x)), "application/pdf"
        except Exception:  # xato yashirilmaydi: jurnalga yoziladi, foydalanuvchiga tushunarli javob
            log.exception("Bayonnoma PDF yaratilmadi: %s", x.raqam)
            return HttpResponse(_("Bayonnoma PDF'ini yaratib bo'lmadi. Administratorga murojaat qiling."),
                                status=500, content_type="text/plain; charset=utf-8")
        disp = "inline"
    else:
        data = xulosa_docx(x, _verify_url(request, x))
        ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        disp = "attachment"
    resp = HttpResponse(data, content_type=ctype)
    resp["Content-Disposition"] = f'{disp}; filename="sinov_bayonnomasi_{x.raqam}.{fmt}"'
    return resp


def xulosa_tekshirish(request, token):
    """QR kod orqali ochiladigan ochiq sahifa: bayonnoma haqiqiyligini tasdiqlaydi."""
    x = Xulosa.objects.select_related("namuna__ariza", "namuna__namuna_turi").filter(verify_token=token).first()
    if not x or not x.tasdiqlangan:
        raise Http404
    if request.GET.get("pdf"):
        return _hujjat_javob(request, x, "pdf")
    return render(request, "public/tekshirish.html", {"x": x, "nam": x.namuna, "natijalar": x.natijalar.all()})
