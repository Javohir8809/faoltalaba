"""Bounded GET-only transport for a future, explicitly configured wire adapter."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .adapters import HemisError

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl) -> None:
        return None


class JsonGetTransport:
    @classmethod
    def from_settings(cls) -> "JsonGetTransport":
        from django.conf import settings

        return cls(
            origin=settings.HEMIS_BASE_URL,
            token=settings.HEMIS_API_TOKEN,
            timeout=settings.HEMIS_HTTP_TIMEOUT,
            attempts=settings.HEMIS_HTTP_ATTEMPTS,
        )

    def __init__(self, *, origin: str, token: str, timeout: float = 5, attempts: int = 3) -> None:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or "\\" in origin
            or any(ord(c) < 32 for c in origin)
            or any(part in {".", ".."} for part in unquote(parsed.path).split("/"))
            or parsed.query
            or parsed.fragment
            or not token
            or "\r" in token
            or "\n" in token
            or not 0 < timeout <= 15
            or not 1 <= attempts <= 3
        ):
            raise HemisError("NOT_CONFIGURED")
        self.origin = origin.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.attempts = attempts
        self.opener = build_opener(NoRedirect())

    def get(self, path: str) -> dict:
        # Neither pagination cursors nor payloads may change credential destination.
        parsed = urlsplit(path)
        if (
            not path.startswith("/")
            or path.startswith("//")
            or parsed.scheme
            or parsed.netloc
            or parsed.fragment
            or "\\" in path
            or any(ord(c) < 32 for c in path)
            or any(part in {".", ".."} for part in unquote(parsed.path).split("/"))
        ):
            raise HemisError("INVALID_RESPONSE")
        request = Request(
            self.origin + path,
            headers={"Authorization": "Bearer " + self.token, "Accept": "application/json"},
            method="GET",
        )
        for attempt in range(self.attempts):
            try:
                with self.opener.open(request, timeout=self.timeout) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise HemisError("INVALID_RESPONSE")
                try:
                    result = json.loads(raw)
                except (ValueError, UnicodeError, RecursionError):
                    raise HemisError("INVALID_RESPONSE") from None
                if not isinstance(result, dict):
                    raise HemisError("INVALID_RESPONSE")
                return result
            except HTTPError as exc:
                retry = exc.code in {429, 500, 502, 503, 504}
                exc.close()
                if not retry:
                    raise HemisError("HTTP_ERROR") from None
            except (URLError, TimeoutError, OSError):
                pass
            if attempt + 1 < self.attempts:
                time.sleep(0.25 * (2**attempt))
        raise HemisError("UNAVAILABLE")
