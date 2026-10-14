"""Focused environment validation for deployment configuration."""

import os

from django.core.exceptions import ImproperlyConfigured


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required environment variable: {name}")
    return value


def csv_values(name: str, default: str = "") -> list[str]:
    return [value.strip() for value in os.environ.get(name, default).split(",") if value.strip()]


def validate_deployment(secret: str, hosts: list[str], origins: list[str]) -> None:
    if len(secret) < 50 or len(set(secret)) < 5 or secret.startswith("django-insecure-"):
        raise ImproperlyConfigured("Deployment SECRET_KEY must be strong.")
    if not hosts or any("*" in host for host in hosts):
        raise ImproperlyConfigured("Deployment ALLOWED_HOSTS must be an explicit allowlist.")
    if any(not origin.startswith("https://") or "*" in origin for origin in origins):
        raise ImproperlyConfigured("Deployment origins must be explicit HTTPS origins.")
