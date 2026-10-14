"""Stable JSON errors without internal exception messages."""

from typing import Any

from django.http import HttpRequest, JsonResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    response = exception_handler(exc, context)
    if response is None:
        return Response(
            {"error": {"code": "INTERNAL_ERROR", "message": "Ichki xatolik.", "details": {}}},
            status=500,
        )
    code = str(getattr(exc, "default_code", "request_error")).upper()
    details = exc.get_codes() if isinstance(exc, ValidationError) else {}
    response.data = {
        "error": {"code": code, "message": "So'rovni bajarib bo'lmadi.", "details": details}
    }
    return response


def not_found(request: HttpRequest, exception: Exception) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "NOT_FOUND", "message": "Manzil topilmadi.", "details": {}}}, status=404
    )


def server_error(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "INTERNAL_ERROR", "message": "Ichki xatolik.", "details": {}}},
        status=500,
    )
