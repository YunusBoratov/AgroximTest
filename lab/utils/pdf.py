# lab/utils/pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from django.conf import settings
import os
from .context import get_xulosa_context


def generate_xulosa_pdf(xulosa, qr_image_path=None):
    ctx = get_xulosa_context(xulosa)

    file_name = f"xulosa_{ctx['ariza_raqami']}.pdf"
    file_path = os.path.join(settings.MEDIA_ROOT, file_name)

    c = canvas.Canvas(file_path, pagesize=A4)
    width, height = A4

    y = height - 40

    # Sarlavha
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y, "AGROXIMIYA TAHLIL XULOSASI")

    y -= 40
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Ariza raqami: {ctx['ariza_raqami']}")
    y -= 18
    c.drawString(40, y, f"Korxona: {ctx['korxona']}")
    y -= 18
    c.drawString(40, y, f"Mas’ul shaxs: {ctx['masul_shaxs']}")
    y -= 18
    c.drawString(40, y, f"Namuna turi: {ctx['namuna_turi']}")
    y -= 18
    c.drawString(40, y, f"Sana: {ctx['sana']}")

    y -= 30
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Tahlillar:")
    y -= 20

    c.setFont("Helvetica", 10)
    for band in ctx["bandlar"]:
        c.drawString(
            50,
            y,
            f"- {band.narxnoma.korsatkich_nomi}: {band.jami_summa} so‘m"
        )
        y -= 15

    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, f"Umumiy summa: {ctx['umumiy_summa']} so‘m")

    # QR
    if qr_image_path:
        c.drawImage(qr_image_path, width - 140, 40, 100, 100)
        c.setFont("Helvetica", 8)
        c.drawCentredString(width - 90, 30, "QR orqali tekshirish")

    c.showPage()
    c.save()

    return file_path
