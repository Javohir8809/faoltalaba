"""Minimal request telemetry without PII, URL query strings, or request content."""

import logging
from collections.abc import Callable
from time import perf_counter

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("faol_talaba.requests")


class RequestLogMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        started = perf_counter()
        response = self.get_response(request)
        logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "status": response.status_code,
                "method": request.method,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response
