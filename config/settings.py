from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-change-me"

DEBUG = True

# NGROK / local test uchun:
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".ngrok-free.dev"]
CSRF_TRUSTED_ORIGINS = ["https://*.ngrok-free.dev"]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

PUBLIC_BASE_URL = "https://vorticose-acanthocladous-ariah.ngrok-free.dev"


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "lab",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    # CSRF kerak (admin uchun)
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # verify.html shu yerda bo'ladi
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]  # logo shu yerda bo'ladi (ixtiyoriy)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ===== NGROK HTTPS uchun (admin login 502/CSRF muammosini tuzatadi) =====
CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.dev",
    "https://*.ngrok.io",
]


# ===== Fayl yo'llari =====
# DOCX template shu joyda bo'lsin:
# templates/pdf/Xulosa_official_template_QR_visible.docx
PDF_TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "pdf", "Xulosa_official_template.docx")

# LibreOffice yo'li (Windows)
SOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"

TELEGRAM_BOT_TOKEN = "5645632094:AAGApqFwL-WKC-ctS2A3vZnQVHlwJ-jq_8I"
TELEGRAM_CHAT_ID = "1063436085"
SITE_URL = "http://127.0.0.1:8000"
# ===== MEDIA (DOCX, PDF) =====
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'


