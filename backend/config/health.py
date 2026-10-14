"""Public read-only liveness and readiness probes."""

import logging

from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from redis import Redis
from redis.exceptions import RedisError
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("faol_talaba.health")


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "unavailable"])


def dependencies_ready() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        with Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=3, socket_timeout=3
        ) as client:
            return bool(client.ping())
    except (DatabaseError, RedisError, OSError):
        logger.warning("dependency_unavailable", extra={"event": "dependency_unavailable"})
        return False


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ["get", "head", "options"]

    @extend_schema(responses={200: HealthSerializer}, auth=[], tags=["Health"])
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadinessView(HealthView):
    @extend_schema(
        responses={200: HealthSerializer, 503: HealthSerializer}, auth=[], tags=["Health"]
    )
    def get(self, request: Request) -> Response:
        ready = dependencies_ready()
        return Response({"status": "ok" if ready else "unavailable"}, status=200 if ready else 503)
