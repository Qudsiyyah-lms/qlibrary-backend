from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "storages",
    "anymail",
    "apps.accounts",
    "apps.books",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
        "DIRS": [],
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
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "id-id"
TIME_ZONE = "Asia/Jakarta"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- REST Framework -----------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "120/min",
        "login": "10/min",
        "otp": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MIN", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Nama cookie httpOnly tempat access/refresh token JWT disimpan (lihat apps/accounts/authentication.py)
JWT_ACCESS_COOKIE_NAME = "qlibrary_access"
JWT_REFRESH_COOKIE_NAME = "qlibrary_refresh"

# --- CORS ----------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# URL frontend Next.js — dipakai untuk menyusun link di email undangan admin
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")

# --- Object storage (S3-compatible: Cloudflare R2 / Backblaze B2) -------
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
AWS_S3_ENDPOINT_URL = env("R2_ENDPOINT_URL", default=None)
AWS_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY", default=None)
AWS_STORAGE_BUCKET_NAME = env("R2_BUCKET_NAME", default=None)
AWS_QUERYSTRING_EXPIRE = 300  # presigned URL berlaku 5 menit
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False

# --- Email (django-anymail) ---------------------------------------------
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
ANYMAIL = {
    "RESEND_API_KEY": env("RESEND_API_KEY", default=None),
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@qlibrary.example.com")

# --- 2FA (OTP email) & pewarisan admin -----------------------------------
OTP_LIFETIME_MINUTES = env.int("OTP_LIFETIME_MINUTES", default=5)
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=5)
OTP_RESEND_COOLDOWN_SECONDS = env.int("OTP_RESEND_COOLDOWN_SECONDS", default=60)
ADMIN_INVITE_LIFETIME_DAYS = env.int("ADMIN_INVITE_LIFETIME_DAYS", default=3)

# --- Batas ukuran upload PDF ---------------------------------------------
MAX_UPLOAD_SIZE_BYTES = env.int("MAX_UPLOAD_SIZE_BYTES", default=100 * 1024 * 1024)  # 100MB
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB — di atas ini di-stream ke temp file, bukan RAM
