"""
5-bosqich: Click SHOP API (prepare / complete), Telegram bot webhook va mijoz uchun to'lov sahifasi.

Click so'rovlari imzosi (sign_string) maxfiy kalit bilan tekshiriladi:
  prepare : md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time)
  complete: md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + merchant_prepare_id
                + amount + action + sign_time)
merchant_trans_id = shartnoma ID si.
"""
import hashlib
import hmac
import json
import logging
import urllib.parse
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import User

from . import xabarnoma
from .models import ClickTranzaksiya, Shartnoma, Tolov
from .views_ariza import mijoz_required

log = logging.getLogger("core.click")

# Click xato kodlari
OK, SIGN_XATO, SUMMA_XATO, ACTION_XATO, ALLAQACHON, TOPILMADI, TRANZ_YOQ, YANGILASH_XATO, SOROV_XATO, BEKOR = (
    0, -1, -2, -3, -4, -5, -6, -7, -8, -9)


def click_sozlangan():
    return bool(settings.CLICK_SERVICE_ID and settings.CLICK_MERCHANT_ID and settings.CLICK_SECRET_KEY)


def click_havola(sh, summa, return_url=""):
    params = {
        "service_id": settings.CLICK_SERVICE_ID,
        "merchant_id": settings.CLICK_MERCHANT_ID,
        "amount": f"{Decimal(summa):.2f}",
        "transaction_param": str(sh.pk),
    }
    if settings.CLICK_MERCHANT_USER_ID:
        params["merchant_user_id"] = settings.CLICK_MERCHANT_USER_ID
    if return_url:
        params["return_url"] = return_url
    return "https://my.click.uz/services/pay?" + urllib.parse.urlencode(params)


def _imzo(p, prepare_id=""):
    s = (f"{p.get('click_trans_id', '')}{p.get('service_id', '')}{settings.CLICK_SECRET_KEY}"
         f"{p.get('merchant_trans_id', '')}{prepare_id}{p.get('amount', '')}{p.get('action', '')}"
         f"{p.get('sign_time', '')}")
    return hashlib.md5(s.encode()).hexdigest()


def _javob(p, error, note, **extra):
    data = {"click_trans_id": p.get("click_trans_id"), "merchant_trans_id": p.get("merchant_trans_id"),
            "error": error, "error_note": note}
    data.update(extra)
    if error != OK:
        log.info("Click javob xato %s: %s (%s)", error, note, p.get("click_trans_id"))
    return JsonResponse(data)


def _tekshir(p, prepare_id=""):
    """Umumiy tekshiruvlar. (shartnoma, summa, xato_javob) qaytaradi."""
    kerak = ["click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time", "sign_string"]
    if any(k not in p for k in kerak):
        return None, None, _javob(p, SOROV_XATO, "Error in request from click")
    if not click_sozlangan() or not hmac.compare_digest(_imzo(p, prepare_id), p["sign_string"]):
        return None, None, _javob(p, SIGN_XATO, "SIGN CHECK FAILED!")
    if str(p["service_id"]) != str(settings.CLICK_SERVICE_ID):
        return None, None, _javob(p, SIGN_XATO, "Incorrect service")
    try:
        summa = Decimal(p["amount"])
    except InvalidOperation:
        return None, None, _javob(p, SUMMA_XATO, "Incorrect parameter amount")
    sh = Shartnoma.objects.filter(pk=p["merchant_trans_id"] if str(p["merchant_trans_id"]).isdigit() else 0,
                                  is_active=True).first()
    if not sh or sh.holat == Shartnoma.Holat.YUBORILMAGAN:
        return None, None, _javob(p, TOPILMADI, "Order not found")
    return sh, summa, None


@csrf_exempt
@require_POST
def click_prepare(request):
    p = request.POST.dict()
    sh, summa, xato = _tekshir(p)
    if xato:
        return xato
    if str(p["action"]) != "0":
        return _javob(p, ACTION_XATO, "Action not found")
    if str(p.get("error", "0")) not in ("0", ""):
        return _javob(p, BEKOR, "Transaction cancelled")
    if sh.tolov_holati == Shartnoma.TolovHolati.TOLANGAN:
        return _javob(p, ALLAQACHON, "Already paid")
    if summa <= 0 or summa > sh.qoldiq + Decimal("0.01"):
        return _javob(p, SUMMA_XATO, "Incorrect parameter amount")
    tr, _ = ClickTranzaksiya.objects.get_or_create(
        click_trans_id=str(p["click_trans_id"]),
        defaults={"shartnoma": sh, "summa": summa, "click_paydoc_id": str(p.get("click_paydoc_id", ""))})
    return _javob(p, OK, "Success", merchant_prepare_id=tr.pk)


@csrf_exempt
@require_POST
def click_complete(request):
    p = request.POST.dict()
    prepare_id = p.get("merchant_prepare_id", "")
    sh, summa, xato = _tekshir(p, prepare_id)
    if xato:
        return xato
    if str(p["action"]) != "1":
        return _javob(p, ACTION_XATO, "Action not found")
    with transaction.atomic():
        tr = (ClickTranzaksiya.objects.select_for_update()
              .filter(pk=prepare_id if str(prepare_id).isdigit() else 0,
                      click_trans_id=str(p["click_trans_id"])).first())
        if not tr or tr.shartnoma_id != sh.pk:
            return _javob(p, TRANZ_YOQ, "Transaction does not exist")
        if tr.holat == ClickTranzaksiya.Holat.COMPLETED:
            return _javob(p, ALLAQACHON, "Already paid", merchant_confirm_id=tr.pk)
        if tr.holat == ClickTranzaksiya.Holat.CANCELLED:
            return _javob(p, BEKOR, "Transaction cancelled")
        if summa != tr.summa:
            return _javob(p, SUMMA_XATO, "Incorrect parameter amount")
        if str(p.get("error", "0")) not in ("0", ""):
            # Click tomonida bekor qilingan / xato
            tr.holat = ClickTranzaksiya.Holat.CANCELLED
            tr.save(update_fields=["holat", "updated_at"])
            return _javob(p, BEKOR, "Transaction cancelled")
        tolov = Tolov.objects.create(shartnoma=sh, summa=summa, usul=Tolov.Usul.CLICK,
                                     tashqi_id=str(p["click_trans_id"]),
                                     izoh=f"Click paydoc {p.get('click_paydoc_id', '')}")
        tr.holat = ClickTranzaksiya.Holat.COMPLETED
        tr.tolov = tolov
        tr.save(update_fields=["holat", "tolov", "updated_at"])
        sh.qayta_hisobla()
        xabarnoma.tolov_qabul(sh, summa)
    return _javob(p, OK, "Success", merchant_confirm_id=tr.pk)


@mijoz_required
@require_POST
def click_tolash(request, pk):
    """Mijoz kabinetidan: summani tanlab Click to'lov sahifasiga o'tish."""
    sh = get_object_or_404(Shartnoma, pk=pk, is_active=True, ariza__mijoz=request.user)
    if not click_sozlangan() or sh.holat == Shartnoma.Holat.YUBORILMAGAN or sh.qoldiq <= 0:
        messages.error(request, _("Onlayn to'lov hozircha mavjud emas"))
        return redirect("kabinet")
    try:
        summa = Decimal(request.POST.get("summa", "").replace(" ", "") or sh.qoldiq)
    except InvalidOperation:
        summa = sh.qoldiq
    summa = min(max(summa, Decimal(1000)), sh.qoldiq)
    return redirect(click_havola(sh, summa, request.build_absolute_uri(reverse("kabinet"))))


# ---------------------------------------------------------------------------
# Telegram bot webhook: mijoz kabinetdagi havola orqali botga /start <kod> yuboradi
# ---------------------------------------------------------------------------
@csrf_exempt
@require_POST
def telegram_webhook(request, secret):
    if not settings.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(secret, settings.TELEGRAM_WEBHOOK_SECRET):
        return HttpResponseBadRequest()
    try:
        upd = json.loads(request.body.decode())
    except ValueError:
        return HttpResponseBadRequest()
    msg = upd.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    text = (msg.get("text") or "").strip()
    if not chat_id:
        return JsonResponse({"ok": True})
    if text.startswith("/start"):
        kod = text[6:].strip()
        user_id = xabarnoma.telegram_kodni_tekshir(kod) if kod else None
        user = User.objects.filter(pk=user_id).first() if user_id else None
        if user:
            User.objects.filter(telegram_chat_id=chat_id).exclude(pk=user.pk).update(telegram_chat_id="")
            user.telegram_chat_id = chat_id
            user.save(update_fields=["telegram_chat_id"])
            xabarnoma.telegram_yubor(chat_id, f"✅ {user.fish or user.username}, Telegram ulandi. Ariza, to'lov va "
                                              f"sinov bayonnomasi haqidagi xabarlar shu yerga keladi.", user=user)
        else:
            xabarnoma.telegram_yubor(chat_id, "Assalomu alaykum! Xabarnomalarni olish uchun saytdagi kabinetingizda "
                                              "\"Telegram'ni ulash\" tugmasini bosing.")
    return JsonResponse({"ok": True})


@mijoz_required
@require_POST
def telegram_uzish(request):
    request.user.telegram_chat_id = ""
    request.user.save(update_fields=["telegram_chat_id"])
    messages.success(request, _("Telegram uzildi"))
    return redirect("kabinet")
