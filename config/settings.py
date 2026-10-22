import os
from pathlib import Path
from urllib.parse import urlsplit

from .environment import external_database, origin_setting

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("Set SECRET_KEY or enable DEBUG for local development.")
    SECRET_KEY = "local-development-only-do-not-use-in-production"
if not DEBUG and (
    len(SECRET_KEY) < 32
    or SECRET_KEY
    in {
        "local-development-only-do-not-use-in-production",
        "replace-with-a-long-random-secret-before-deploying",
        "generate-a-random-secret-and-share-it-between-both-services",
    }
):
    raise RuntimeError("Set a strong, unique SECRET_KEY for deployment; do not use an example value.")
ADMIN_ORIGIN = origin_setting("ADMIN_ORIGIN", "http://admin.localhost:8017", debug=DEBUG)
PUBLIC_ORIGIN = origin_setting("PUBLIC_ORIGIN", "http://forms.localhost:8017", debug=DEBUG)
if urlsplit(ADMIN_ORIGIN).hostname == urlsplit(PUBLIC_ORIGIN).hostname:
    raise RuntimeError("Admin and public forms require different hostnames, not just ports.")
ALLOWED_HOSTS = [urlsplit(x).hostname for x in (ADMIN_ORIGIN, PUBLIC_ORIGIN)]
LOCAL_HOST_ALIASES = (
    ("127.0.0.1", "localhost")
    if DEBUG and all(host and host.endswith(".localhost") for host in ALLOWED_HOSTS)
    else ()
)
ALLOWED_HOSTS.extend(LOCAL_HOST_ALIASES)
SERVICE_ROLE = os.getenv("SERVICE_ROLE", "combined")
if SERVICE_ROLE not in {"combined", "admin", "public"}:
    raise RuntimeError("SERVICE_ROLE must be combined, admin or public.")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
CSRF_TRUSTED_ORIGINS = [ADMIN_ORIGIN]
if os.getenv("TRUST_PROXY", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "crm",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "crm.middleware.SurfaceMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
if os.getenv("DATABASE_URL"):
    DATABASES = {"default": external_database(os.environ["DATABASE_URL"], debug=DEBUG)}
elif os.getenv("DB_ENGINE") == "sqlite":
    if not DEBUG:
        raise RuntimeError("SQLite is only available with DEBUG=1. Use PostgreSQL for deployment.")
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "lead_magnet_crm"),
            "USER": os.getenv("POSTGRES_USER", "lead_magnet_crm"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 512 * 1024
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAdminUser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "submit": "30/min"},
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Lead Magnet CRM Operations System — API",
    "VERSION": "1.0.0",
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "DESCRIPTION": "Session authentication. Obtain CSRF at /api/auth/csrf/; send X-CSRFToken on admin writes. Public endpoints are served only on PUBLIC_ORIGIN.",
}
