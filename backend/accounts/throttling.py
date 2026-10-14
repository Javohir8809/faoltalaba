"""Atomic Redis rate limits, failing closed if the limiter is unavailable."""

import hashlib
import hmac

from django.conf import settings
from redis import Redis
from redis.exceptions import RedisError
from rest_framework.exceptions import APIException, Throttled
from rest_framework.throttling import BaseThrottle

SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
if count > tonumber(ARGV[2]) then return redis.call('TTL', KEYS[1]) end
return 0
"""


class AuthenticationUnavailable(APIException):
    status_code = 503
    default_detail = "Kirish xizmati vaqtincha mavjud emas."
    default_code = "authentication_unavailable"


class AuthThrottle(BaseThrottle):
    def allow_request(self, request, view) -> bool:
        if not settings.AUTH_THROTTLE_ENABLED:
            return True
        scopes = [("ip", self.get_ident(request), settings.AUTH_IP_LIMIT)]
        if getattr(view, "throttle_account", False):
            # Store an HMAC key, never the raw username or IP in Redis keys.
            username = request.data.get("username", "") if isinstance(request.data, dict) else ""
            scopes.append(("account", str(username), settings.AUTH_ACCOUNT_LIMIT))
        try:
            # Redis-visible limiter digests must never be JWT signing MACs.
            limiter_key = hmac.new(
                settings.JWT_SIGNING_KEY.encode(),
                b"faol-talaba/auth-throttle/key/v1",
                hashlib.sha256,
            ).digest()
            with Redis.from_url(
                settings.REDIS_URL, socket_connect_timeout=3, socket_timeout=3
            ) as client:
                for kind, value, limit in scopes:
                    hashed = hmac.new(limiter_key, value.encode(), hashlib.sha256).hexdigest()
                    wait = client.eval(SCRIPT, 1, f"auth-limit:{kind}:{hashed}", 60, limit)
                    if wait:
                        raise Throttled(wait=max(1, wait))
        except (RedisError, OSError) as exc:
            raise AuthenticationUnavailable() from exc
        return True
