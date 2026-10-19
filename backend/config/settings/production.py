"""Fail closed for non-local deployments."""

from .base import *  # noqa: F403
from .environment import required, validate_deployment

validate_deployment(
    SECRET_KEY,  # noqa: F405
    ALLOWED_HOSTS,  # noqa: F405
    CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS,  # noqa: F405
)
validate_deployment(JWT_SIGNING_KEY, ALLOWED_HOSTS, [])  # noqa: F405
validate_deployment(ATTENDANCE_TOKEN_KEY, ALLOWED_HOSTS, [])  # noqa: F405
if ATTENDANCE_TOKEN_KEY in [JWT_SIGNING_KEY, SECRET_KEY]:  # noqa: F405
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Attendance HMAC key must be independent.")
REDIS_URL = required("REDIS_URL")
CELERY_BROKER_URL = required("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = required("CELERY_RESULT_BACKEND")
DATABASES["default"]["OPTIONS"]["sslmode"] = "require"  # noqa: F405
DEBUG = False
EXPOSE_API_SCHEMA = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Configure trusted proxy handling only when the deployment boundary is established.
