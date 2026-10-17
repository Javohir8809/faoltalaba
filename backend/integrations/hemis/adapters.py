"""Our normalized contract; it is deliberately independent of HEMIS wire formats."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from django.conf import settings

from .models import Resource


class HemisError(Exception):
    """Only fixed codes may cross the integration boundary."""

    CODES = {
        "NOT_CONFIGURED",
        "INVALID_PAGE",
        "INVALID_RECORD",
        "MISSING_REFERENCE",
        "IDENTITY_CONFLICT",
        "UNAVAILABLE",
        "HTTP_ERROR",
        "INVALID_RESPONSE",
        "SYNC_BUSY",
        "SYNC_FAILED",
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self.CODES else "SYNC_FAILED"
        super().__init__(self.code)


@dataclass(frozen=True)
class Page:
    records: tuple[dict, ...]
    next_cursor: str = ""

    def validate(self) -> None:
        if (
            not isinstance(self.records, tuple)
            or len(self.records) > 500
            or not all(isinstance(row, dict) for row in self.records)
            or not isinstance(self.next_cursor, str)
            or len(self.next_cursor) > 512
        ):
            raise HemisError("INVALID_PAGE")


@dataclass(frozen=True)
class Lesson:
    external_id: str
    subject_id: str
    group_id: str
    teacher_id: str
    starts_at: datetime
    ends_at: datetime


class HemisAdapter(Protocol):
    def fetch_page(self, resource: Resource, cursor: str) -> Page: ...

    def schedule(self, *, starts_at: datetime, ends_at: datetime) -> tuple[Lesson, ...]: ...


class MockHemisAdapter:
    """Synthetic fixture, never a fallback for a failed live integration."""

    def __init__(self) -> None:
        if not settings.HEMIS_ALLOW_MOCK:
            raise HemisError("NOT_CONFIGURED")
        self.data = json.loads(
            Path(__file__).with_name("mock_data.json").read_text(encoding="utf-8")
        )

    def fetch_page(self, resource: Resource, cursor: str) -> Page:
        if cursor:
            raise HemisError("INVALID_PAGE")
        return Page(tuple(dict(row) for row in self.data[resource]))

    def schedule(self, *, starts_at: datetime, ends_at: datetime) -> tuple[Lesson, ...]:
        if starts_at.utcoffset() is None or ends_at.utcoffset() is None or ends_at <= starts_at:
            raise HemisError("INVALID_RECORD")
        # No invented real lesson timetable. Schedule persistence belongs to feedback.
        return ()


def get_adapter() -> HemisAdapter:
    if settings.HEMIS_ADAPTER == "mock" and settings.HEMIS_ALLOW_MOCK:
        return MockHemisAdapter()
    raise HemisError("NOT_CONFIGURED")
