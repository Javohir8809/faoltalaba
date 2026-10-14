"""Actual Redis/cache and PostgreSQL readiness integration checks."""

from uuid import uuid4

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.mark.redis_integration
def test_real_redis_cache_roundtrip() -> None:
    key = f"bootstrap-test:{uuid4()}"
    try:
        cache.set(key, {"status": "verified"}, timeout=30)
        assert cache.get(key) == {"status": "verified"}
    finally:
        cache.delete(key)
    assert cache.get(key) is None


@pytest.mark.django_db
@pytest.mark.redis_integration
@pytest.mark.integration
def test_real_database_and_redis_readiness() -> None:
    response = APIClient().get("/api/v1/ready/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
