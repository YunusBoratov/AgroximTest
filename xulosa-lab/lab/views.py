import os
import tempfile
import subprocess
from io import BytesIO
from decimal import Decimal

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
import qrcode
from .telegram_send import (send_telegram_message, send_telegram_document, send_xulosa_telegram,)
from lab.telegram_send import send_xulosa_telegram
from django.utils import timezone
from django.contrib import messages





from .models import Xulosa, Norma

def _norma_text(element: str) -> str:
    n = Norma.objects.filter(element=element).first()
    if not n:
        return "-"
    # min/max bo'sh bo'lsa ham chiroyli ko'rsatamiz
    left = "-" if n.min_qiymat is None else str(n.min_qiymat)
    right = "-" if n.max_qiymat is None else str(n.max_qiymat)
    return f"{left} – {right}"


def _qaror_uz_ru(is_ok):
    # is_ok: True/False/None
    if is_ok is None:
        return "-", "-"
    return ("Mos", "Соответствует") if is_ok else ("Mos emas", "Не соответствует")


def _norma_ichidami(element: str, qiymat):
    if qiymat is None:
        return None

    norma = Norma.objects.filter(element=element).first()
    if norma is None:
        return None

    v = Decimal(str(qiymat))

    if norma.min_qiymat is not None and v < norma.min_qiymat:
        return False
    if norma.max_qiymat is not None and v > norma.max_qiymat:
        return False
    return True


def _build_verify_url(request, xulosa: Xulosa) -> str:
    path = reverse("verify", kwargs={"token": xulosa.verify_token})

    base = getattr(settings, "PUBLIC_BASE_URL", None)
    if base:
        return base.rstrip("/") + path

    return request.build_absolute_uri(path)


def _make_qr_inline_image(doc: DocxTemplate, data: str, size_mm: int = 28):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    """bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)"""

    tmp_png = os.path.join(tempfile.gettempdir(), "qr_tmp.png")
    img.save(tmp_png, format="PNG")

    return InlineImage(doc, tmp_png, width=Mm(size_mm))


def xulosa_docx(request, pk):
    xulosa = get_object_or_404(Xulosa, pk=pk)
    ALLOWED_EXPORT_STATUSES = {"tayyor", "yuborildi"}

    if xulosa.status not in ALLOWED_EXPORT_STATUSES:
        return HttpResponse(
            "Hujjat hali tayyor emas. PDF/DOCX faqat 'Xulosa tayyor' yoki 'Xulosa yuborildi' holatida beriladi.",
            status=403
    )

    template_path = getattr(settings, "PDF_TEMPLATE_PATH", None)
    if not template_path or not os.path.exists(template_path):
        return HttpResponse("Template topilmadi: templates/pdf/Xulosa_official_template_QR_visible.docx", status=500)

    doc = DocxTemplate(template_path)

    # elementlar mosligi (normaga tekshirish)
    azot_ok = _norma_ichidami("azot", xulosa.azot)
    fosfor_ok = _norma_ichidami("fosfor", xulosa.fosfor)
    kaliy_ok = _norma_ichidami("kaliy", xulosa.kaliy)
    namlik_ok = _norma_ichidami("namlik", xulosa.namlik)

    verify_url = _build_verify_url(request, xulosa)
    qr_img = _make_qr_inline_image(doc, verify_url, size_mm=28)

    context = {
        "namuna_raqami": xulosa.namuna_raqami,
        "sana": xulosa.sana.strftime("%d.%m.%Y"),

        # Word'da sendagi templatega mos bo'lishi uchun:
        "buyurtmachi": xulosa.buyurtmachi,
        "buyurtmachi_uz": xulosa.buyurtmachi,
        "buyurtmachi_ru": xulosa.buyurtmachi,

        "azot": xulosa.azot if xulosa.azot is not None else "-",
        "fosfor": xulosa.fosfor if xulosa.fosfor is not None else "-",
        "kaliy": xulosa.kaliy if xulosa.kaliy is not None else "-",
        "namlik": xulosa.namlik if xulosa.namlik is not None else "-",

        "azot_norma": _norma_text("azot"),
        "fosfor_norma": _norma_text("fosfor"),
        "kaliy_norma": _norma_text("kaliy"),
        "namlik_norma": _norma_text("namlik"),

        "azot_qaror_uz": _qaror_uz_ru(azot_ok)[0],
        "azot_qaror_ru": _qaror_uz_ru(azot_ok)[1],

        "fosfor_qaror_uz": _qaror_uz_ru(fosfor_ok)[0],
        "fosfor_qaror_ru": _qaror_uz_ru(fosfor_ok)[1],

        "kaliy_qaror_uz": _qaror_uz_ru(kaliy_ok)[0],
        "kaliy_qaror_ru": _qaror_uz_ru(kaliy_ok)[1],

        "namlik_qaror_uz": _qaror_uz_ru(namlik_ok)[0],
        "namlik_qaror_ru": _qaror_uz_ru(namlik_ok)[1],

        # Xulosa matni (hozircha ikkala tilda bir xil bo'lsa ham mayli)
        "xulosa_matni_uz": xulosa.xulosa_matni or "",
        "xulosa_matni_ru": xulosa.xulosa_matni or "",

        # QR joyi template ichida {{ qr_code }} bo'lishi kerak
        "qr_code": qr_img,

        # Verify linkni matn sifatida ham qo'ysa bo'ladi (ixtiyoriy)
        "verify_url": verify_url,
    }

    doc.render(context)

    filename = f'Bayonnoma_{xulosa.namuna_raqami}_{xulosa.sana.strftime("%d-%m-%Y")}.docx'
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    doc.save(response)
    return response


def xulosa_pdf(request, pk):
    xulosa = get_object_or_404(Xulosa, pk=pk)
    ALLOWED_EXPORT_STATUSES = {"tayyor", "yuborildi"}

    if xulosa.status not in ALLOWED_EXPORT_STATUSES:
        return HttpResponse(
            "Hujjat hali tayyor emas. PDF/DOCX faqat 'Xulosa tayyor' yoki 'Xulosa yuborildi' holatida beriladi.",
            status=403
        )


    # Avval docx generatsiya qilib, keyin pdf ga aylantiramiz
    template_path = getattr(settings, "PDF_TEMPLATE_PATH", None)
    if not template_path or not os.path.exists(template_path):
        return HttpResponse("Template topilmadi: templates/pdf/Xulosa_official_template_QR_visible.docx", status=500)

    soffice = getattr(settings, "SOFFICE_PATH", "soffice")
    if not os.path.exists(soffice):
        return HttpResponse(
            "LibreOffice topilmadi. SOFFICE_PATH ni settings.py da tekshir.",
            status=500
        )

    doc = DocxTemplate(template_path)

    azot_ok = _norma_ichidami("azot", xulosa.azot)
    fosfor_ok = _norma_ichidami("fosfor", xulosa.fosfor)
    kaliy_ok = _norma_ichidami("kaliy", xulosa.kaliy)
    namlik_ok = _norma_ichidami("namlik", xulosa.namlik)

    verify_url = _build_verify_url(request, xulosa)
    qr_img = _make_qr_inline_image(doc, verify_url, size_mm=28)

    context = {
        "namuna_raqami": xulosa.namuna_raqami,
        "sana": xulosa.sana.strftime("%d.%m.%Y"),
        "buyurtmachi": xulosa.buyurtmachi,
        "buyurtmachi_uz": xulosa.buyurtmachi,
        "buyurtmachi_ru": xulosa.buyurtmachi,

        "azot": xulosa.azot if xulosa.azot is not None else "-",
        "fosfor": xulosa.fosfor if xulosa.fosfor is not None else "-",
        "kaliy": xulosa.kaliy if xulosa.kaliy is not None else "-",
        "namlik": xulosa.namlik if xulosa.namlik is not None else "-",

        "azot_norma": _norma_text("azot"),
        "fosfor_norma": _norma_text("fosfor"),
        "kaliy_norma": _norma_text("kaliy"),
        "namlik_norma": _norma_text("namlik"),

        "azot_qaror_uz": _qaror_uz_ru(azot_ok)[0],
        "azot_qaror_ru": _qaror_uz_ru(azot_ok)[1],

        "fosfor_qaror_uz": _qaror_uz_ru(fosfor_ok)[0],
        "fosfor_qaror_ru": _qaror_uz_ru(fosfor_ok)[1],

        "kaliy_qaror_uz": _qaror_uz_ru(kaliy_ok)[0],
        "kaliy_qaror_ru": _qaror_uz_ru(kaliy_ok)[1],

        "namlik_qaror_uz": _qaror_uz_ru(namlik_ok)[0],
        "namlik_qaror_ru": _qaror_uz_ru(namlik_ok)[1],

        "xulosa_matni_uz": xulosa.xulosa_matni or "",
        "xulosa_matni_ru": xulosa.xulosa_matni or "",

        "qr_code": qr_img,
        "verify_url": verify_url,
    }

    doc.render(context)

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = os.path.join(tmpdir, f"xulosa_{xulosa.id}.docx")
        doc.save(docx_path)

        subprocess.run(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nofirststartwizard",
                "--convert-to",
                "pdf",
                "--outdir",
                tmpdir,
                docx_path,
            ],
            check=True,
        )

        pdf_path = os.path.join(tmpdir, f"xulosa_{xulosa.id}.pdf")
        if not os.path.exists(pdf_path):
            # LibreOffice ba'zan nomni boshqacha qiladi
            # Shuning uchun tmp papkadan .pdf ni topamiz
            pdf_found = None
            for f in os.listdir(tmpdir):
                if f.lower().endswith(".pdf"):
                    pdf_found = os.path.join(tmpdir, f)
                    break
            if not pdf_found:
                return HttpResponse("PDF generatsiya bo'lmadi (LibreOffice convert xatosi).", status=500)
            pdf_path = pdf_found

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    filename = f'Bayonnoma_{xulosa.namuna_raqami}_{xulosa.sana.strftime("%d-%m-%Y")}.pdf'
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def verify(request, token):
    xulosa = get_object_or_404(Xulosa, verify_token=token)

    can_download = xulosa.status in ("tayyor", "yuborildi")

    pdf_url = reverse("xulosa_pdf_token", kwargs={"token": str(xulosa.verify_token)}) if can_download else None
    docx_url = reverse("xulosa_docx_token", kwargs={"token": str(xulosa.verify_token)}) if can_download else None

    return render(request, "verify.html", {
        "xulosa": xulosa,
        "can_download": can_download,
        "pdf_url": pdf_url,
        "docx_url": docx_url,
    })

def xulosa_docx_by_token(request, token):
    xulosa = get_object_or_404(Xulosa, verify_token=token)

    if xulosa.status not in ("tayyor", "yuborildi"):
        return HttpResponseForbidden("Xulosa hali tayyor emas.")

    return xulosa_docx(request, xulosa.pk)


def xulosa_pdf_by_token(request, token):
    xulosa = get_object_or_404(Xulosa, verify_token=token)

    if xulosa.status not in ("tayyor", "yuborildi"):
        return HttpResponseForbidden("Xulosa hali tayyor emas.")

    return xulosa_pdf(request, xulosa.pk)


# faqat tayyor/yuborildi bo'lsa yuborilsin

@staff_member_required
def confirm_send_xulosa(request, pk):
    xulosa = get_object_or_404(Xulosa, pk=pk)

    if xulosa.status not in ("tayyor", "yuborildi"):
        return HttpResponseForbidden("Xulosa hali tayyor emas.")

    # ⬇️ pastda sening eski telegram yuborish koding qoladi
    if request.method == "POST":
        # bu yerda telegramga yuboramiz
        send_xulosa_telegram(xulosa)

        xulosa.yuborilgan = True
        xulosa.yuborilgan_vaqt = timezone.now()
        xulosa.status = "yuborildi"
        xulosa.save()

        messages.success(request, "Xulosa muvaffaqiyatli yuborildi")
        return redirect("/admin/lab/xulosa/")

    return render(request, "admin/confirm_send.html", {
        "xulosa": xulosa
    })


    verify_link = request.build_absolute_uri(
        reverse("verify", kwargs={"token": xulosa.verify_token})
    )

    pdf_response = xulosa_pdf(request, pk)
    pdf_bytes = pdf_response.content

    text = (
        f"📄 Xulosa tayyor!\n"
        f"Namuna: {xulosa.namuna_raqami}\n"
        f"Buyurtmachi: {xulosa.buyurtmachi}\n"
        f"Tekshirish: {verify_link}"
    )

    send_telegram_message(
        settings.TELEGRAM_BOT_TOKEN,
        settings.TELEGRAM_CHAT_ID,
        text
    )

    send_telegram_document(
        settings.TELEGRAM_BOT_TOKEN,
        settings.TELEGRAM_CHAT_ID,
        pdf_bytes,
        filename=f"Bayonnoma_{xulosa.namuna_raqami}.pdf",
        caption="PDF biriktirildi."
    )

    xulosa.status = "yuborildi"
    xulosa.save(update_fields=["status"])

    return HttpResponse("Telegramga yuborildi ✅")

