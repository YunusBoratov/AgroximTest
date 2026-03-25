from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseForbidden
from django.http import HttpResponse
from .models import Xulosa


# =========================
# VERIFY (QR orqali ko‘rish)
# =========================
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from .models import Xulosa
from .telegram_send import send_xulosa_telegram


def verify_xulosa(request, token):
    xulosa = get_object_or_404(Xulosa, verify_token=token)

    # Status tekshirish (katta harf bilan!)
    can_download = xulosa.status in ("tayyor", "yuborildi")

    pdf_url = reverse("lab:xulosa_pdf", kwargs={"pk": xulosa.pk})
    #docx_url = reverse("xulosa_docx", kwargs={"pk": xulosa.pk}) if can_download else None

    return render(request, "verify.html", {
        "xulosa": xulosa,
        "can_download": can_download,
        "pdf_url": pdf_url,
        #"docx_url": docx_url,
    })


# =========================
# DOCX (token orqali)
# =========================
def xulosa_docx_by_token(request, token):
    xulosa = get_object_or_404(Xulosa, verify_token=token)

    if xulosa.status not in ("Tayyor", "yuborildi"):
        return HttpResponseForbidden("Xulosa hali tayyor emas.")

    return render(request, "pdf/stub_docx.html", {"xulosa": xulosa})

def send_xulosa_view(request, pk):

    shartnoma = get_object_or_404(Shartnoma, pk=pk)

    if shartnoma.status != "tayyor":
        return HttpResponse("Shartnoma hali tayyor emas")

    xulosa = get_object_or_404(Xulosa, pk=pk)

    if xulosa.status == "tayyor":

        try:
            send_xulosa_telegram(xulosa)

            xulosa.status = "yuborildi"
            xulosa.save()

        except Exception as e:
            print("Telegram xato:", e)

    return redirect("/admin/lab/xulosa/")


# =========================
# PDF (token orqali)
# =========================
def xulosa_pdf_by_token(request, token):
    xulosa = get_object_or_404(Xulosa, verify_token=token)

    if xulosa.status not in ("tayyor", "yuborildi"):
        return HttpResponseForbidden("Xulosa hali tayyor emas.")

    return render(request, "pdf/stub_pdf.html", {"xulosa": xulosa})
def xulosa_pdf(request, pk):
    return HttpResponse("PDF test ishlayapti")

def xulosa_docx(request, pk):
    return HttpResponse("DOCX test ishlayapti")

def xulosa_kiritish(request, pk):
    xulosa = get_object_or_404(Xulosa, pk=pk)

    if request.method == "POST":
        print("POST:", request.POST)
        print("SINOV:", request.POST.get("sinov_otkazuvchi"))       
        xulosa.sinov_otkazuvchi = request.POST.get("sinov_otkazuvchi")
        xulosa.save()

        # 🔥 ENG MUHIM QISM
        return redirect('xulosa_kiritish', pk=xulosa.id)

    return render(request, "lab/xulosa_form.html", {
        "xulosa": xulosa
    })
