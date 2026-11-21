"""
Mijozga xabarnomalar: SMS (Eskiz.uz) va Telegram bot.

Kalitlar sozlanmagan bo'lsa xabar yuborilmaydi, faqat jurnalga (Xabar) "sozlanmagan" deb yoziladi —
tizim ishlashda davom etadi. Tashqi so'rovlar standart urllib bilan (qo'shimcha kutubxonasiz).
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import uuid

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction

log = logging.getLogger("core.xabarnoma")
TIMEOUT = 10


def _http(method, url, data=None, headers=None, json_body=None, files=None):
    headers = dict(headers or {})
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif files:
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in (data or {}).items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for k, (fname, content, ctype) in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'
                         f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode() or "{}")


def _jurnal(kanal, kimga, matn, holat, xato="", user=None):
    from .models import Xabar

    Xabar.objects.create(kanal=kanal, kimga=kimga, matn=matn, holat=holat, xato=xato[:500], user=user)


# ---------------------------------------------------------------------------
# SMS — Eskiz.uz
# ---------------------------------------------------------------------------
ESKIZ_URL = "https://notify.eskiz.uz/api"


def sms_sozlangan():
    return bool(settings.ESKIZ_EMAIL and settings.ESKIZ_PASSWORD)


def _eskiz_token(yangilash=False):
    token = None if yangilash else cache.get("eskiz_token")
    if not token:
        r = _http("POST", f"{ESKIZ_URL}/auth/login",
                  data={"email": settings.ESKIZ_EMAIL, "password": settings.ESKIZ_PASSWORD})
        token = r["data"]["token"]
        cache.set("eskiz_token", token, 60 * 60 * 24 * 25)
    return token


def sms_yubor(telefon, matn, user=None):
    from .models import Xabar

    raqam = "".join(ch for ch in telefon or "" if ch.isdigit())
    if len(raqam) != 12:
        return False
    if not sms_sozlangan():
        _jurnal(Xabar.Kanal.SMS, raqam, matn, Xabar.Holat.OCHIQ, user=user)
        return False
    payload = {"mobile_phone": raqam, "message": matn, "from": settings.ESKIZ_FROM}
    try:
        try:
            _http("POST", f"{ESKIZ_URL}/message/sms/send", data=payload,
                  headers={"Authorization": f"Bearer {_eskiz_token()}"})
        except urllib.error.HTTPError as e:
            if e.code != 401:
                raise
            _http("POST", f"{ESKIZ_URL}/message/sms/send", data=payload,
                  headers={"Authorization": f"Bearer {_eskiz_token(yangilash=True)}"})
        _jurnal(Xabar.Kanal.SMS, raqam, matn, Xabar.Holat.YUBORILDI, user=user)
        return True
    except Exception as e:  # tarmoq / provayder xatosi — asosiy jarayonni to'xtatmaydi
        log.warning("SMS yuborilmadi: %s", e)
        _jurnal(Xabar.Kanal.SMS, raqam, matn, Xabar.Holat.XATO, str(e), user=user)
        return False


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------
def telegram_sozlangan():
    return bool(settings.TELEGRAM_BOT_TOKEN)


def _tg(method, **kw):
    return _http("POST", f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}", **kw)


def telegram_yubor(chat_id, matn, user=None, hujjat=None):
    """hujjat: (fayl_nomi, bytes) — bo'lsa PDF hujjat sifatida yuboriladi."""
    from .models import Xabar

    if not chat_id:
        return False
    if not telegram_sozlangan():
        _jurnal(Xabar.Kanal.TELEGRAM, chat_id, matn, Xabar.Holat.OCHIQ, user=user)
        return False
    try:
        if hujjat:
            _tg("sendDocument", data={"chat_id": chat_id, "caption": matn[:1000]},
                files={"document": (hujjat[0], hujjat[1], "application/pdf")})
        else:
            _tg("sendMessage", json_body={"chat_id": chat_id, "text": matn, "disable_web_page_preview": True})
        _jurnal(Xabar.Kanal.TELEGRAM, chat_id, matn, Xabar.Holat.YUBORILDI, user=user)
        return True
    except Exception as e:
        log.warning("Telegram xabar yuborilmadi: %s", e)
        _jurnal(Xabar.Kanal.TELEGRAM, chat_id, matn, Xabar.Holat.XATO, str(e), user=user)
        return False


def telegram_ulash_havolasi(user):
    """Kabinetdagi 'Telegram'ni ulash' tugmasi uchun: t.me/<bot>?start=<imzolangan kod>."""
    if not (settings.TELEGRAM_BOT_USERNAME and telegram_sozlangan()):
        return ""
    kod = signing.dumps(user.pk, salt="tg-ulash", compress=True)
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={kod}"


def telegram_kodni_tekshir(kod):
    try:
        return signing.loads(kod, salt="tg-ulash", max_age=60 * 60 * 24)
    except signing.BadSignature:
        return None


# ---------------------------------------------------------------------------
# Hodisalar: mijozga xabar (SMS + Telegram)
# ---------------------------------------------------------------------------
def mijozga(ariza, matn, hujjat=None):
    """Ariza egasiga (yoki arizadagi telefonga) SMS va Telegram orqali xabar.
    Tranzaksiya tugagach yuboriladi, xato bo'lsa jarayon to'xtamaydi."""
    user = ariza.mijoz
    telefon = (user.telefon if user else "") or ariza.telefon
    sms_ruxsat = user.sms_xabar if user else True
    chat_id = user.telegram_chat_id if user else ""

    def yubor():
        if sms_ruxsat:
            sms_yubor(telefon, matn, user=user)
        if chat_id:
            telegram_yubor(chat_id, matn, user=user, hujjat=hujjat() if callable(hujjat) else hujjat)

    transaction.on_commit(yubor)


MARKAZ_QISQA = "Agrokimyo va tuproq tahlili markazi"


def ariza_qabul(ariza):
    mijozga(ariza, f"{MARKAZ_QISQA}: {ariza.raqam} raqamli arizangiz qabul qilindi, namunalar laboratoriyaga "
                   f"topshirildi.")


def ariza_rad(ariza):
    mijozga(ariza, f"{MARKAZ_QISQA}: {ariza.raqam} raqamli arizangiz rad etildi. Sabab: {ariza.rad_sababi}")


def shartnoma_tayyor(sh):
    mijozga(sh.ariza, f"{MARKAZ_QISQA}: {sh.raqam}-sonli shartnoma tayyor. Summa: {int(sh.jami_summa):,} so'm. "
                      f"Tahlil kamida 30% to'lovdan keyin boshlanadi. Shartnoma va to'lov: kabinetingizda."
            .replace(",", " "))


def tolov_qabul(sh, summa):
    mijozga(sh.ariza, f"{MARKAZ_QISQA}: {sh.raqam}-sonli shartnoma bo'yicha {int(summa):,} so'm to'lov qabul "
                      f"qilindi. Jami to'langan: {sh.tolangan_foiz}%.".replace(",", " "))


def xulosa_berildi(x, pdf_fn=None):
    mijozga(x.namuna.ariza, f"{MARKAZ_QISQA}: {x.raqam} raqamli sinov bayonnomasi tayyor. "
                            f"Kabinetingizdan yuklab olishingiz mumkin.",
            hujjat=(lambda: (f"{x.raqam}.pdf", pdf_fn())) if pdf_fn else None)
