import requests


def send_telegram_message(bot_token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": text})
    r.raise_for_status()
    return r.json()


def send_telegram_document(bot_token: str, chat_id: str, file_bytes: bytes, filename: str, caption: str = ""):
    url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
    files = {"document": (filename, file_bytes)}
    data = {"chat_id": chat_id, "caption": caption}
    r = requests.post(url, data=data, files=files)
    r.raise_for_status()
    return r.json()
from django.conf import settings


def send_xulosa_telegram(xulosa):
    """
    Xulosani Telegram orqali yuborish (matn + keyin fayl qo‘shish mumkin)
    """

    bot_token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    text = (
        "🧪 Agrokimyoviy tahlil xulosasi\n\n"
        f"👤 Buyurtmachi: {xulosa.buyurtmachi}\n"
        f"🔢 Namuna raqami: {xulosa.namuna_raqami}\n"
        f"📅 Sana: {xulosa.sana}\n"
        f"📌 Holat: {xulosa.get_status_display()}\n\n"
        "📎 Xulosa tayyor."
    )

    # 1️⃣ Avval MATN yuboramiz
    send_telegram_message(
        bot_token=bot_token,
        chat_id=chat_id,
        text=text
    )

    # 🔜 Keyin xohlasak PDF/DOCX ham qo‘shamiz