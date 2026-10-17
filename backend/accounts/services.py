"""Transactional and audited access administration."""

from uuid import UUID

from audit.services import record_event
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import connection, transaction
from django.utils import timezone
from organizations.models import Department, Faculty
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import RefreshSession, Role, RoleGrant, ScopeType, User
from .policies import has_capability


def lock_access_administration(actor: User) -> User:
    # Serialize global role/status changes so concurrent last-admin removal cannot race.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(614003)")
    current = User.objects.select_for_update().get(pk=actor.pk)
    if not has_capability(current, "access.manage"):
        raise PermissionDenied()
    return current


def active_superadmins() -> int:
    return RoleGrant.objects.filter(
        role=Role.SUPERADMIN, scope_type=ScopeType.GLOBAL, user__is_active=True
    ).count()


@transaction.atomic
def grant_role(
    *, actor: User, target: User, role: str, scope_type: str, scope_id: UUID | None
) -> RoleGrant:
    lock_access_administration(actor)
    return _persist_role_grant(
        actor=actor, target=target, role=role, scope_type=scope_type, scope_id=scope_id
    )


def _persist_role_grant(
    *, actor: User, target: User, role: str, scope_type: str, scope_id: UUID | None
) -> RoleGrant:
    """Private persistence; caller must authorize and hold a transaction/access lock."""
    if not connection.in_atomic_block:
        raise RuntimeError("Role persistence requires a transaction")
    if scope_type == ScopeType.ACTIVITY:
        from activities.models import Activity, ActivityType, Lifecycle

        activity = Activity.objects.select_for_update().filter(pk=scope_id).first()
        if not activity or activity.state == Lifecycle.ARCHIVED:
            raise ValidationError(
                {"scope_id": "Unknown or archived activity"}, code="invalid_scope"
            )
        if role == Role.CLUB_LEADER and activity.type != ActivityType.CLUB:
            raise ValidationError({"role": "Club leader requires a club"}, code="invalid_scope")
    model = {ScopeType.FACULTY: Faculty, ScopeType.DEPARTMENT: Department}.get(scope_type)
    if model and not model.objects.filter(pk=scope_id).exists():
        raise ValidationError({"scope_id": "Unknown academic scope"}, code="invalid_scope")
    grant = RoleGrant(user=target, role=role, scope_type=scope_type, scope_id=scope_id)
    try:
        grant.full_clean()
    except ModelValidationError as exc:
        raise ValidationError({"role": "Invalid or duplicate role scope"}) from exc
    grant.save()
    if scope_type == ScopeType.ACTIVITY:
        from activities.models import ActivityRole

        ActivityRole.objects.create(activity=activity, grant=grant)
    record_event(
        actor_id=actor.id,
        action="role_granted",
        object_id=target.id,
        metadata={
            "role": role,
            "scope_type": scope_type,
            "scope_id": str(scope_id) if scope_id else None,
        },
    )
    return grant


@transaction.atomic
def revoke_role(*, actor: User, grant: RoleGrant) -> None:
    lock_access_administration(actor)
    current = RoleGrant.objects.select_for_update().select_related("user").get(pk=grant.pk)
    if current.role == Role.SUPERADMIN and current.user.is_active and active_superadmins() <= 1:
        raise ValidationError(
            {"role": "Last active superadmin must remain"}, code="last_superadmin"
        )
    record_event(
        actor_id=actor.id,
        action="role_revoked",
        object_id=current.user_id,
        metadata={
            "role": current.role,
            "scope_type": current.scope_type,
            "scope_id": str(current.scope_id) if current.scope_id else None,
        },
    )
    current.delete()


@transaction.atomic
def set_user_status(*, actor: User, target: User, is_active: bool) -> User:
    lock_access_administration(actor)
    current = User.objects.select_for_update().get(pk=target.id)
    if (
        not is_active
        and current.is_active
        and current.role_grants.filter(role=Role.SUPERADMIN, scope_type=ScopeType.GLOBAL).exists()
        and active_superadmins() <= 1
    ):
        raise ValidationError(
            {"is_active": "Last active superadmin must remain"}, code="last_superadmin"
        )
    if current.is_active != is_active:
        current.is_active = is_active
        current.save(update_fields=["is_active"])
        if not is_active:
            RefreshSession.objects.filter(user=current, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
        record_event(
            actor_id=actor.id,
            action="user_status_changed",
            object_id=current.id,
            metadata={"is_active": is_active},
        )
    return current
