# lab/utils/qr.py
import qrcode
import os
from django.conf import settings


def generate_qr_image(data: str, filename: str):
    file_path = os.path.join(settings.MEDIA_ROOT, filename)
    img = qrcode.make(data)
    img.save(file_path)
    return file_path
