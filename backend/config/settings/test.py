"""Tests still use PostgreSQL; unit tests do not silently switch database engines."""

from .local import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
