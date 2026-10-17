"""Structured, allowlisted logging: request bodies and exception text are excluded."""

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", "application_log")
        if event not in {
            "request_completed",
            "dependency_unavailable",
            "application_log",
            "hemis_sync_failed",
        }:
            event = "application_log"
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": event,
        }
        if event == "hemis_sync_failed":
            from integrations.hemis.adapters import HemisError
            from integrations.hemis.models import Resource

            code = getattr(record, "error_code", None)
            resource = getattr(record, "resource", None)
            if code in HemisError.CODES:
                payload["error_code"] = code
            if resource in Resource.values:
                payload["resource"] = resource
        for name in ("status", "duration_ms", "method"):
            value = getattr(record, name, None)
            if isinstance(value, (int, float)) or (
                name == "method"
                and value in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
            ):
                payload[name] = value
        return json.dumps(payload)
