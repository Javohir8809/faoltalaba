"""JWT identity tokens with row-locked, rotating refresh sessions."""

import hashlib
import hmac
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
from audit.services import record_event
from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from .models import RefreshSession, User


def invalid_token() -> AuthenticationFailed:
    return AuthenticationFailed("Token yaroqsiz.", code="invalid_token")


def decode_token(token: str, expected_type: str) -> dict:
    if not isinstance(token, str) or len(token) > 4096:
        raise invalid_token()
    try:
        claims = jwt.decode(
            token,
            settings.JWT_SIGNING_KEY,
            algorithms=["HS256"],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require": ["exp", "iat", "sub", "sid", "jti", "type", "iss", "aud"],
                "strict_aud": True,
            },
        )
        if claims["type"] != expected_type:
            raise invalid_token()
        for key in ("sub", "sid", "jti"):
            UUID(claims[key])
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError) as exc:
        raise invalid_token() from exc


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_pair(session: RefreshSession) -> dict[str, str]:
    now = timezone.now()
    common = {
        "sub": str(session.user_id),
        "sid": str(session.id),
        "iat": now,
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    access = jwt.encode(
        {
            **common,
            "type": "access",
            "jti": str(uuid4()),
            "exp": min(now + timedelta(seconds=settings.JWT_ACCESS_SECONDS), session.expires_at),
        },
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    refresh = jwt.encode(
        {**common, "type": "refresh", "jti": str(uuid4()), "exp": session.expires_at},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    session.refresh_digest = digest(refresh)
    session.save(update_fields=["refresh_digest"])
    return {"access": access, "refresh": refresh}


@transaction.atomic
def login(*, username: str, password: str) -> dict[str, str]:
    user = authenticate(username=username, password=password)
    if user is None:
        raise AuthenticationFailed("Kirish ma'lumotlari yaroqsiz.", code="invalid_credentials")
    verified_password = user.password
    # Concurrent deactivation/password changes must serialize with session creation.
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active or not hmac.compare_digest(user.password, verified_password):
        raise AuthenticationFailed("Kirish ma'lumotlari yaroqsiz.", code="invalid_credentials")
    session = RefreshSession.objects.create(
        user=user,
        expires_at=timezone.now() + timedelta(seconds=settings.JWT_REFRESH_SECONDS),
        refresh_digest="",
    )
    pair = issue_pair(session)
    record_event(actor_id=user.id, action="auth_login", object_id=session.id)
    return pair


def refresh(token: str) -> dict[str, str]:
    claims = decode_token(token, "refresh")
    pair = None
    with transaction.atomic():
        session = (
            RefreshSession.objects.select_for_update()
            .filter(pk=claims["sid"], user_id=claims["sub"])
            .first()
        )
        if session is None or session.revoked_at or session.expires_at <= timezone.now():
            raise invalid_token()
        if not session.user.is_active or not hmac.compare_digest(
            session.refresh_digest, digest(token)
        ):
            session.revoked_at = timezone.now()
            session.save(update_fields=["revoked_at"])
            record_event(
                actor_id=session.user_id, action="refresh_replay_revoked", object_id=session.id
            )
        else:
            pair = issue_pair(session)
            record_event(actor_id=session.user_id, action="refresh_rotated", object_id=session.id)
    # Raise after committing replay revocation, not inside the transaction.
    if pair is None:
        raise invalid_token()
    return pair


@transaction.atomic
def logout(token: str) -> None:
    claims = decode_token(token, "refresh")
    session = (
        RefreshSession.objects.select_for_update()
        .filter(pk=claims["sid"], user_id=claims["sub"])
        .first()
    )
    if session is None:
        raise invalid_token()
    if session.revoked_at is None:
        session.revoked_at = timezone.now()
        session.save(update_fields=["revoked_at"])
        record_event(actor_id=session.user_id, action="auth_logout", object_id=session.id)
