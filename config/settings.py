import json
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me-at-least-32-chars!!")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080").split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "people",
    "organizations",
    "assignments",
    "accounts",
    "audit",
    "wordpress",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
    }
]

_default_db = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", _default_db),
        conn_max_age=60,
    )
}
if os.environ.get("SOURCE_DATABASE_URL"):
    DATABASES["source"] = dj_database_url.parse(
        os.environ["SOURCE_DATABASE_URL"],
        conn_max_age=0,
    )

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.MagicLinkBackend",
    "django.contrib.auth.backends.ModelBackend",
    # Later: django-auth-ldap (match Person.employee_id by default; do not auto-provision).
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []
_frontend_dist = BASE_DIR / "frontend" / "dist"
if _frontend_dist.is_dir():
    STATICFILES_DIRS.append(_frontend_dist)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

def _split_tenant_ids(raw: str) -> list[str]:
    sep = ";" if ";" in raw else ","
    return [p.strip() for p in raw.split(sep) if p.strip()]


TENANT_ID = os.environ.get("TENANT_ID", "VBC")
_multi = os.environ.get("DIRECTORY_EDITABLE_TENANT_IDS", "").strip()
DIRECTORY_EDITABLE_TENANT_IDS = _split_tenant_ids(_multi) if _multi else [TENANT_ID]

BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
WP_EMAIL_ENDPOINT = os.environ.get(
    "WP_EMAIL_ENDPOINT",
    "https://vanburencountymi.gov/wp-json/county/v1/send-email",
)
COUNTY_SEND_EMAIL_API_KEY = os.environ.get("COUNTY_SEND_EMAIL_API_KEY", "")

_wp_map = os.environ.get("WP_SYNC_TRIGGER_URL_BY_TENANT", "").strip()
try:
    WP_SYNC_TRIGGER_URL_BY_TENANT = json.loads(_wp_map) if _wp_map else {}
except json.JSONDecodeError as e:
    raise RuntimeError("WP_SYNC_TRIGGER_URL_BY_TENANT must be valid JSON object") from e
WP_SYNC_TRIGGER_SECRET = os.environ.get("WP_SYNC_TRIGGER_SECRET", "").strip() or None
SYNC_API_SECRET = os.environ.get("SYNC_API_SECRET", "").strip() or None

OTP_EXPIRY_HOURS = 1
GROUP_DIRECTORY_EDITOR = "directory_editor"
GROUP_PERMISSIONS_ADMIN = "permissions_admin"
