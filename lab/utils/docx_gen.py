# lab/utils/docx_gen.py

from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from django.conf import settings
import os
from .context import get_xulosa_context


def generate_xulosa_docx(xulosa, qr_image_path=None):

    template_path = os.path.join(
        settings.BASE_DIR,
        "templates",
        "pdf",
        "Xulosa_official_template.docx"
    )

    # TEMPLATE BORLIGINI TEKSHIRAMIZ
    if not os.path.exists(template_path):
        raise Exception(f"Template topilmadi: {template_path}")

    doc = DocxTemplate(template_path)

    context = get_xulosa_context(xulosa)

    if qr_image_path:
        context["qr_code"] = InlineImage(
            doc,
            qr_image_path,
            width=Mm(30)
        )

    # MEDIA papka
    output_dir = os.path.join(settings.MEDIA_ROOT, "xulosalar")
    os.makedirs(output_dir, exist_ok=True)

    file_name = f"xulosa_{context['ariza_raqami']}.docx"
    full_path = os.path.join(output_dir, file_name)

    doc.render(context)
    doc.save(full_path)

    print("DOCX saved to:", full_path)

    return full_path