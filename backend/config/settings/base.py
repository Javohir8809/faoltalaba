"""Shared settings. Production secrets are always provided by the environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .environment import csv_values, required

BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parent
if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith((".local", ".test")):
    load_dotenv(REPO_ROOT / ".env", override=False)

SECRET_KEY = required("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = csv_values("DJANGO_ALLOWED_HOSTS")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "organizations",
    "accounts",
    "students",
    "staff",
    "audit",
    "activities",
    "clubs",
    "integrations.hemis.apps.HemisConfig",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "corsheaders",
]
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
JWT_SIGNING_KEY = required("JWT_SIGNING_KEY")
JWT_ISSUER = "faol-talaba"
JWT_AUDIENCE = "faol-talaba-clients"
JWT_ACCESS_SECONDS = 300
JWT_REFRESH_SECONDS = 604800
AUTH_THROTTLE_ENABLED = True
AUTH_IP_LIMIT = 100
AUTH_ACCOUNT_LIMIT = 5
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "config.middleware.RequestLogMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
TEMPLATES = []
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required("POSTGRES_DB"),
        "USER": required("POSTGRES_USER"),
        "PASSWORD": required("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 5},
    }
}
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"socket_connect_timeout": 3, "socket_timeout": 3},
    }
}
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_CONNECTION_TIMEOUT = 5
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600}
HEMIS_ADAPTER = os.environ.get("HEMIS_ADAPTER", "disabled")
HEMIS_ALLOW_MOCK = False
HEMIS_BASE_URL = os.environ.get("HEMIS_BASE_URL", "")
HEMIS_API_TOKEN = os.environ.get("HEMIS_API_TOKEN", "")
HEMIS_HTTP_TIMEOUT = float(os.environ.get("HEMIS_HTTP_TIMEOUT", "5"))
HEMIS_HTTP_ATTEMPTS = int(os.environ.get("HEMIS_HTTP_ATTEMPTS", "3"))
LANGUAGE_CODE = "uz"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
CORS_ALLOWED_ORIGINS = csv_values("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = csv_values("CSRF_TRUSTED_ORIGINS")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
REST_FRAMEWORK = {
    "NUM_PROXIES": 0,  # Ignore untrusted forwarded-IP headers until proxy trust is configured.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.JWTAuthentication"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "config.errors.api_exception_handler",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Faol Talaba API",
    "VERSION": "1.0.0",
    "DESCRIPTION": "Faol Talaba modular monolith API. UTC timestamps; JSON transport.",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "OAS_VERSION": "3.0.3",
    "ENUM_NAME_OVERRIDES": {
        "ClubMembershipStatusEnum": [
            ("PENDING", "Pending"),
            ("ACTIVE", "Active"),
            ("REJECTED", "Rejected"),
            ("LEFT", "Left"),
        ],
        "ClubSessionStatusEnum": [
            ("PLANNED", "Planned"),
            ("OPEN", "Open"),
            ("CLOSED", "Closed"),
            ("CANCELLED", "Cancelled"),
        ],
        "StatusEnum": ["ok", "unavailable"],
        "HemisSyncStatusEnum": [
            ("RUNNING", "Running"),
            ("SUCCEEDED", "Succeeded"),
            ("FAILED", "Failed"),
        ],
    },
}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "config.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
