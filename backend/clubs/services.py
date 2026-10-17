"""Club configuration and narrowly scoped leadership delegation."""

from uuid import UUID

from accounts.models import Role, RoleGrant, ScopeType, User
from accounts.services import _persist_role_grant
from activities import services as activities
from activities.models import Activity, Lifecycle
from activities.policies import can_manage, can_review
from audit.services import record_event
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import connection, transaction
from django.db.models import Model
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Club, ClubSchedule


def validate_model(instance: Model) -> None:
    try:
        instance.full_clean()
    except ModelValidationError:
        raise ValidationError({"club": "Noto'g'ri qiymat."}, code="invalid_club") from None


def lock_club(club_id: UUID) -> Club:
    activity = Activity.objects.select_for_update().get(pk=club_id)
    club = Club.objects.select_for_update().get(pk=club_id)
    club.activity = activity
    return club


def managed_club(actor: User, club_id: UUID, *, review: bool = False) -> tuple[User, Club]:
    actor = activities.current_actor(actor)
    club = lock_club(club_id)
    if not (can_review(actor, club.activity) if review else can_manage(actor, club.activity)):
        raise PermissionDenied()
    return actor, club


@transaction.atomic
def create_club(*, actor: User, activity: dict, timezone_name: str = "Asia/Tashkent") -> Club:
    parent = activities.create_activity(actor=actor, data={**activity, "type": "CLUB"})
    club = Club(activity=parent, timezone_name=timezone_name)
    validate_model(club)
    club.save()
    record_event(actor_id=actor.id, action="club_created", object_id=club.pk)
    return club


@transaction.atomic
def update_timezone(*, actor: User, club_id: UUID, timezone_name: str) -> Club:
    actor, club = managed_club(actor, club_id)
    if club.activity.state not in {Lifecycle.DRAFT, Lifecycle.REJECTED}:
        raise ValidationError({"state": "Faqat qoralama tahrirlanadi."}, code="club_not_editable")
    club.timezone_name = timezone_name
    validate_model(club)
    club.save(update_fields=["timezone_name"])
    record_event(actor_id=actor.id, action="club_updated", object_id=club.pk)
    return club


@transaction.atomic
def replace_schedule(*, actor: User, club_id: UUID, slots: list[dict]) -> None:
    actor, club = managed_club(actor, club_id)
    if club.activity.state not in {Lifecycle.DRAFT, Lifecycle.REJECTED}:
        raise ValidationError(
            {"state": "Faqat qoralama jadvali o'zgaradi."}, code="club_not_editable"
        )
    if len(slots) > 21:
        raise ValidationError({"slots": "Jadval hajmi oshib ketdi."})
    seen = set()
    rows = []
    for slot in slots:
        row = ClubSchedule(club=club, **slot)
        if row.starts_at.utcoffset() is not None or row.ends_at.utcoffset() is not None:
            raise ValidationError({"slots": "Mahalliy soat kerak."})
        # Validate in-memory duplicates; the old schedule is replaced atomically.
        if (row.weekday, row.starts_at) in seen:
            raise ValidationError({"slots": "Takroriy vaqt."})
        seen.add((row.weekday, row.starts_at))
        try:
            row.full_clean(validate_unique=False, validate_constraints=False)
        except ModelValidationError:
            raise ValidationError({"slots": "Noto'g'ri jadval."}) from None
        if not 1 <= row.weekday <= 7 or row.ends_at <= row.starts_at:
            raise ValidationError({"slots": "Noto'g'ri jadval."})
        if any(
            r.weekday == row.weekday and r.starts_at < row.ends_at and row.starts_at < r.ends_at
            for r in rows
        ):
            raise ValidationError({"slots": "Jadval vaqtlari kesishadi."})
        rows.append(row)
    current = list(club.schedule.values_list("weekday", "starts_at", "ends_at"))
    desired = sorted((row.weekday, row.starts_at, row.ends_at) for row in rows)
    if current == desired:
        return
    club.schedule.all().delete()
    ClubSchedule.objects.bulk_create(rows)
    record_event(
        actor_id=actor.id,
        action="club_schedule_updated",
        object_id=club.pk,
        metadata={"count": len(rows)},
    )


def lock_delegation() -> None:
    # Match accounts' role/status serialization before taking any activity lock.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(614003)")


@transaction.atomic
def assign_leader(*, actor: User, club_id: UUID, user_id: UUID) -> RoleGrant:
    lock_delegation()
    actor, club = managed_club(actor, club_id, review=True)
    if club.activity.state == Lifecycle.ARCHIVED:
        raise ValidationError({"club": "To'garak arxivlangan."})
    target = User.objects.filter(pk=user_id, is_active=True).first()
    if not target:
        raise ValidationError({"user_id": "Foydalanuvchi mavjud emas yoki nofaol."})
    existing = RoleGrant.objects.filter(
        user=target, role=Role.CLUB_LEADER, scope_type=ScopeType.ACTIVITY, scope_id=club.pk
    ).first()
    if existing:
        return existing
    return _persist_role_grant(
        actor=actor,
        target=target,
        role=Role.CLUB_LEADER,
        scope_type=ScopeType.ACTIVITY,
        scope_id=club.pk,
    )


@transaction.atomic
def revoke_leader(*, actor: User, club_id: UUID, grant_id: UUID) -> None:
    lock_delegation()
    actor, club = managed_club(actor, club_id, review=True)
    grant = (
        RoleGrant.objects.select_for_update()
        .filter(pk=grant_id, role=Role.CLUB_LEADER, scope_type=ScopeType.ACTIVITY, scope_id=club.pk)
        .first()
    )
    if not grant:
        from rest_framework.exceptions import NotFound

        raise NotFound()
    record_event(
        actor_id=actor.id,
        action="role_revoked",
        object_id=grant.user_id,
        metadata={"role": grant.role, "scope_type": grant.scope_type, "scope_id": str(club.pk)},
    )
    grant.delete()
