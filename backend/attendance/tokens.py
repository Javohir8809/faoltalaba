"""Opaque identifiers only: card sector contents and keys never enter this boundary."""

import hashlib
import hmac
from typing import Protocol

from django.conf import settings
from rest_framework.exceptions import ValidationError


class TokenAdapter(Protocol):
    def digest(self, token: str) -> str: ...


class OpaqueTokenAdapter:
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def digest(self, token: str) -> str:
        if (
            not isinstance(token, str)
            or not 1 <= len(token) <= 256
            or token != token.strip()
            or any(not 32 <= ord(c) <= 126 for c in token)
        ):
            raise ValidationError({"token": "Identifikator noto‘g‘ri."}, code="invalid_card")
        return hmac.new(
            settings.ATTENDANCE_TOKEN_KEY.encode(),
            ("faol-talaba/card/v1/" + self.kind + "/" + token).encode(),
            hashlib.sha256,
        ).hexdigest()


ADAPTERS: dict[str, TokenAdapter] = {kind: OpaqueTokenAdapter(kind) for kind in ["NFC", "QR"]}
