"""API, deployment configuration and privacy checks for the backend foundation."""

import json
import logging
from unittest.mock import patch

import pytest
from config.errors import api_exception_handler
from config.health import dependencies_ready
from config.logging import JsonFormatter
from config.settings.environment import validate_deployment
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, connection
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.settings import api_settings
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView


def test_health_is_public_read_only_and_uses_json() -> None:
    client = APIClient()
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response["Content-Type"] == "application/json"
    assert response["X-Content-Type-Options"] == "nosniff"
    forbidden = client.post("/api/v1/health/", {"data": "secret"}, format="json")
    assert forbidden.status_code == 405
    assert forbidden.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


@pytest.mark.parametrize("ready,status", [(True, 200), (False, 503)])
def test_readiness_only_exposes_generic_status(ready: bool, status: int) -> None:
    with patch("config.health.dependencies_ready", return_value=ready):
        response = APIClient().get("/api/v1/ready/")
    assert response.status_code == status
    assert response.json() == {"status": "ok" if ready else "unavailable"}


def test_database_outage_does_not_expose_credentials() -> None:
    with patch("config.health.connection.cursor", side_effect=OperationalError("password=secret")):
        assert dependencies_ready() is False


def test_redis_outage_does_not_expose_credentials() -> None:
    with (
        patch("config.health.connection.cursor"),
        patch("config.health.Redis.from_url", side_effect=RedisConnectionError("private URL")),
    ):
        assert dependencies_ready() is False


def test_default_permissions_deny_anonymous_requests() -> None:
    assert api_settings.DEFAULT_PERMISSION_CLASSES == [IsAuthenticated]
    assert api_settings.DEFAULT_AUTHENTICATION_CLASSES == []
    response = APIView.as_view()(APIRequestFactory().get("/private/"))
    assert response.status_code == 403


def test_missing_route_returns_json_without_query_or_identity() -> None:
    response = APIClient().get("/api/v1/missing/?passport=private-value")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "private-value" not in response.content.decode()


def test_internal_and_validation_errors_hide_values() -> None:
    response = api_exception_handler(RuntimeError("password=secret"), {})
    assert response.status_code == 500
    assert "secret" not in json.dumps(response.data)
    response = api_exception_handler(ValidationError({"name": ["private name"]}), {})
    assert response.status_code == 400
    assert response.data["error"]["details"] == {"name": ["invalid"]}
    assert "private name" not in json.dumps(response.data)


def test_json_logs_exclude_message_args_and_traceback() -> None:
    record = logging.LogRecord(
        "application", logging.ERROR, __file__, 1, "secret %s", ("PII",), None
    )
    record.event = "request_completed"
    record.method = "GET"
    record.status = 500
    record.password = "secret"
    serialized = JsonFormatter().format(record)
    assert "secret" not in serialized
    assert "PII" not in serialized
    assert json.loads(serialized)["status"] == 500


@pytest.mark.parametrize(
    "secret,hosts,origins",
    [
        ("short", ["yi.katdpi.uz"], []),
        ("A" * 60, ["yi.katdpi.uz"], []),
        ("valid-secret-" * 8, ["*"], []),
        ("valid-secret-" * 8, [], []),
        ("valid-secret-" * 8, ["yi.katdpi.uz"], ["http://yi.katdpi.uz"]),
    ],
)
def test_deployment_rejects_unsafe_settings(
    secret: str, hosts: list[str], origins: list[str]
) -> None:
    with pytest.raises(ImproperlyConfigured):
        validate_deployment(secret, hosts, origins)


def test_deployment_accepts_explicit_secure_configuration() -> None:
    validate_deployment("valid-secret-" * 8, ["yi.katdpi.uz"], ["https://yi.katdpi.uz"])


@pytest.mark.django_db
@pytest.mark.integration
def test_real_postgresql_connection_and_migrations() -> None:
    assert connection.vendor == "postgresql"
    with connection.cursor() as cursor:
        cursor.execute("SHOW server_version_num")
        assert int(cursor.fetchone()[0]) >= 180000
        cursor.execute("SELECT COUNT(*) FROM django_content_type")
        assert cursor.fetchone()[0] >= 1
