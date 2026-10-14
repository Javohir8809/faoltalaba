from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from .models import RefreshSession
from .tokens import decode_token, invalid_token


class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b"bearer":
            raise invalid_token()
        try:
            token = header[1].decode("ascii")
        except UnicodeDecodeError as exc:
            raise invalid_token() from exc
        claims = decode_token(token, "access")
        session = (
            RefreshSession.objects.select_related("user")
            .filter(
                pk=claims["sid"],
                user_id=claims["sub"],
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
                user__is_active=True,
            )
            .first()
        )
        if session is None:
            raise invalid_token()
        return session.user, claims

    def authenticate_header(self, request) -> str:
        return "Bearer"


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = JWTAuthentication
    name = "bearerAuth"

    def get_security_definition(self, auto_schema) -> dict:
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
