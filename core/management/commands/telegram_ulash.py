"""
Telegram botni platformaga ulaydi (webhook o'rnatadi) va holatini ko'rsatadi.
Kalitlar faqat serverdagi .env faylidan olinadi:
    TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME, TELEGRAM_WEBHOOK_SECRET, PUBLIC_BASE_URL (ixtiyoriy)

    python manage.py telegram_ulash            # ulash va tekshirish
    python manage.py telegram_ulash --uzish    # webhook'ni o'chirish
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

from core import xabarnoma


class Command(BaseCommand):
    help = "Telegram botni platformaga ulaydi (setWebhook) va holatini tekshiradi"

    def add_arguments(self, parser):
        parser.add_argument("--uzish", action="store_true", help="Webhook'ni o'chirish")

    def handle(self, *args, **opts):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError(".env faylida TELEGRAM_BOT_TOKEN yo'q")
        try:
            me = xabarnoma._tg("getMe", json_body={})
        except Exception as e:
            raise CommandError(f"Telegram'ga ulanib bo'lmadi (token noto'g'ri yoki internet yo'q): {e}")
        bot = (me.get("result") or {}).get("username", "")
        self.stdout.write(f"Bot: @{bot}")
        if settings.TELEGRAM_BOT_USERNAME and settings.TELEGRAM_BOT_USERNAME.lstrip("@").lower() != bot.lower():
            self.stdout.write(self.style.WARNING(
                f".env dagi TELEGRAM_BOT_USERNAME ({settings.TELEGRAM_BOT_USERNAME}) bot nomiga mos emas — "
                f"uni {bot} qilib to'g'rilang"))

        if opts["uzish"]:
            xabarnoma._tg("deleteWebhook", json_body={})
            self.stdout.write(self.style.SUCCESS("Webhook o'chirildi"))
            return

        if not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError(".env faylida TELEGRAM_WEBHOOK_SECRET yo'q")
        base = (settings.PUBLIC_BASE_URL or "https://agroximtest.uz").rstrip("/")
        url = base + reverse("telegram_webhook", args=[settings.TELEGRAM_WEBHOOK_SECRET])
        r = xabarnoma._tg("setWebhook", json_body={"url": url, "allowed_updates": ["message"],
                                                   "drop_pending_updates": True})
        if not r.get("ok"):
            raise CommandError(f"Webhook o'rnatilmadi: {r}")
        info = xabarnoma._tg("getWebhookInfo", json_body={}).get("result", {})
        self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {base}/telegram/webhook/***/"))
        if info.get("last_error_message"):
            self.stdout.write(self.style.WARNING(f"Oxirgi xato: {info['last_error_message']}"))
        self.stdout.write(f"Tekshirish: Telegram'da @{bot} ga /start yozing — bot javob berishi kerak.")
