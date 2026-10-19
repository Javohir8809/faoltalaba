import hashlib
import hmac

from accounts.throttling import SCRIPT
from django.conf import settings
from redis import Redis
from redis.exceptions import RedisError
from rest_framework.exceptions import APIException, Throttled
from rest_framework.throttling import BaseThrottle


class AttendanceUnavailable(APIException):
    status_code = 503
    default_detail = "Davomat xizmati vaqtincha mavjud emas."
    default_code = "attendance_unavailable"


class AttendanceThrottle(BaseThrottle):
    def allow_request(self, request, view) -> bool:
        if not settings.ATTENDANCE_THROTTLE_ENABLED:
            return True
        key = hmac.new(
            settings.ATTENDANCE_TOKEN_KEY.encode(),
            b"faol-talaba/attendance-throttle/key/v1",
            hashlib.sha256,
        ).digest()
        scopes = [
            ("actor", str(request.user.pk), settings.ATTENDANCE_ACTOR_LIMIT),
            ("ip", self.get_ident(request), settings.ATTENDANCE_IP_LIMIT),
        ]
        try:
            with Redis.from_url(
                settings.REDIS_URL, socket_connect_timeout=3, socket_timeout=3
            ) as client:
                for kind, value, limit in scopes:
                    digest = hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
                    wait = client.eval(SCRIPT, 1, f"attendance-limit:{kind}:{digest}", 60, limit)
                    if wait:
                        raise Throttled(wait=max(1, wait))
        except (RedisError, OSError) as exc:
            raise AttendanceUnavailable() from exc
        return True
