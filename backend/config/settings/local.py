"""Local development only."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "[::1]"]  # noqa: F405
EXPOSE_API_SCHEMA = True
HEMIS_ALLOW_MOCK = True
