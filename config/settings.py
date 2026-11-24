"""
AgroximTest — Mineral o'g'it va kimyoviy vositalar tahlili platformasi.

Sozlamalar muhit o'zgaruvchilari (environment) orqali boshqariladi:
  DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS,
  DB_ENGINE=postgres (bo'lmasa SQLite), DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
"""
import os
from pathlib import Path

from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Loyiha ildizidagi .env faylini o'qiydi (agar mavjud bo'lsa). Tizim o'zgaruvchilari ustun turadi."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-in-production")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.sidebar",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

if env("DB_ENGINE") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "agroximtest"),
            "USER": env("DB_USER", "agroximtest"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "bosh"
LOGOUT_REDIRECT_URL = "bosh"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

LANGUAGE_CODE = "uz"
LANGUAGES = [
    ("uz", _("O'zbekcha")),
    ("ru", _("Русский")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Biznes qoidalari
TAHLIL_BOSHLASH_MIN_FOIZ = 30  # tahlil kamida 30% to'lovdan keyin boshlanadi
XULOSA_YUBORISH_MIN_FOIZ = 100  # xulosa buyurtmachiga faqat to'liq to'lovdan keyin

# Markaz ma'lumotlari (sayt sarlavhasida)
MARKAZ = {
    "nomi": "Agrokimyo va tuproq tahlili markazi",
    "nomi_ru": "Центр агрохимического и почвенного анализа",
    "shior": "Tuproq yagona boylik",
    "telefonlar": ["+998 71 203 14 14 (1015)", "+998 71 260 42 20"],
    "manzil": "111215, Toshkent viloyati, Qibray tumani, Bobur ko'chasi, 8-uy",
    "sayt": "www.agrokimlab.uz",
    "email": "info@agrokimlab.uz",
}

# Shartnoma raqami: oddiy tartib raqami (har yili 1 dan). Joriy yil uchun boshlang'ich
# raqamni admin panelda (Hisoblagich) yoki shu sozlama bilan belgilash mumkin.
SHARTNOMA_RAQAM_BOSHLANISH = int(env("SHARTNOMA_RAQAM_BOSHLANISH", "0"))
TUPROQ_TAHLILI_URL = env("TUPROQ_TAHLILI_URL", "#")
# Xulosadagi QR kod shu manzilga olib boradi (masalan https://agroximtest.uz)
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "")
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 80 * 1024 * 1024


# ---------------------------------------------------------------------------
# Tashqi xizmatlar (kalitlar faqat serverdagi .env faylida saqlanadi, kodga yozilmaydi)
# ---------------------------------------------------------------------------
# Telegram bot (@BotFather beradi)
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", "")  # @ belgisisiz, masalan AgroximTestBot
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", "")

# SMS — Eskiz.uz (notify.eskiz.uz)
ESKIZ_EMAIL = env("ESKIZ_EMAIL", "")
ESKIZ_PASSWORD = env("ESKIZ_PASSWORD", "")
ESKIZ_FROM = env("ESKIZ_FROM", "4546")  # tasdiqlangan jo'natuvchi nomi

# Click SHOP API (merchant.click.uz kabinetidan)
CLICK_SERVICE_ID = env("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_ID = env("CLICK_MERCHANT_ID", "")
CLICK_SECRET_KEY = env("CLICK_SECRET_KEY", "")
CLICK_MERCHANT_USER_ID = env("CLICK_MERCHANT_USER_ID", "")

# HTTPS (sertifikat o'rnatilgach DJANGO_HTTPS=1). Sertifikatsiz sinovda (http://IP) DJANGO_HTTPS=0.
if not DEBUG and env("DJANGO_HTTPS", "1") == "1":
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"core": {"handlers": ["console"], "level": "INFO"}},
}
