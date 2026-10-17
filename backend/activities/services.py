"""Audited activity writes and explicit lifecycle gates."""

from uuid import UUID

from accounts.models import User
from audit.services import record_event
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Activity, Lifecycle, RegistrationPolicy
from .policies import can_manage, can_review

TRANSITIONS = {
    Lifecycle.DRAFT: {Lifecycle.PENDING_APPROVAL, Lifecycle.ARCHIVED},
    Lifecycle.PENDING_APPROVAL: {
        Lifecycle.PUBLISHED,
        Lifecycle.REJECTED,
        Lifecycle.DRAFT,
        Lifecycle.CANCELLED,
    },
    Lifecycle.REJECTED: {Lifecycle.DRAFT, Lifecycle.ARCHIVED},
    Lifecycle.PUBLISHED: {
        Lifecycle.REGISTRATION_OPEN,
        Lifecycle.ACTIVE,
        Lifecycle.CANCELLED,
        Lifecycle.SUSPENDED,
    },
    Lifecycle.REGISTRATION_OPEN: {Lifecycle.ACTIVE, Lifecycle.CANCELLED, Lifecycle.SUSPENDED},
    Lifecycle.ACTIVE: {Lifecycle.COMPLETED, Lifecycle.CANCELLED, Lifecycle.SUSPENDED},
    Lifecycle.SUSPENDED: {Lifecycle.PUBLISHED, Lifecycle.CANCELLED},
    Lifecycle.COMPLETED: {Lifecycle.ARCHIVED},
    Lifecycle.CANCELLED: {Lifecycle.ARCHIVED},
    Lifecycle.ARCHIVED: set(),
}
CONTENT_FIELDS = {
    "title",
    "description",
    "visibility",
    "audience",
    "audience_faculty",
    "audience_department",
    "audience_group",
    "capacity",
    "starts_at",
    "ends_at",
    "venue",
    "registration_policy",
    "attendance_policy",
    "evidence_required",
    "result_policy",
}


def validate_activity(activity: Activity) -> None:
    try:
        activity.full_clean()
    except ModelValidationError as exc:
        # Preserve field names/codes, never source values or profile details.
        fields = exc.message_dict if hasattr(exc, "message_dict") else {"activity": []}
        raise ValidationError(
            {field: "Noto'g'ri qiymat." for field in fields}, code="invalid_activity"
        ) from None


def current_actor(actor: User) -> User:
    current = User.objects.get(pk=actor.pk)
    if not current.is_active:
        raise PermissionDenied()
    return current


@transaction.atomic
def create_activity(*, actor: User, data: dict) -> Activity:
    actor = current_actor(actor)
    if not data.keys() <= CONTENT_FIELDS | {"type", "faculty", "department"}:
        raise ValidationError({"activity": "Maydon o'zgartirilmaydi."})
    activity = Activity(organizer=actor, **data)
    validate_activity(activity)
    if not can_review(actor, activity):
        raise PermissionDenied()
    activity.save()
    record_event(actor_id=actor.id, action="activity_created", object_id=activity.id)
    return activity


def locked_activity(actor: User, activity_id: UUID) -> Activity:
    activity = Activity.objects.select_for_update().get(pk=activity_id)
    if not can_manage(actor, activity):
        raise PermissionDenied()
    return activity


@transaction.atomic
def update_activity(*, actor: User, activity_id: UUID, data: dict) -> Activity:
    actor = current_actor(actor)
    activity = locked_activity(actor, activity_id)
    if not data.keys() <= CONTENT_FIELDS:
        raise ValidationError({"activity": "Maydon o'zgartirilmaydi."}, code="immutable_field")
    if activity.state not in {Lifecycle.DRAFT, Lifecycle.REJECTED}:
        raise ValidationError(
            {"state": "Faqat qoralamani tahrirlash mumkin."}, code="activity_not_editable"
        )
    for key, value in data.items():
        setattr(activity, key, value)
    validate_activity(activity)
    activity.save()
    record_event(actor_id=actor.id, action="activity_updated", object_id=activity.id)
    return activity


@transaction.atomic
def transition_activity(*, actor: User, activity_id: UUID, state: str) -> Activity:
    actor = current_actor(actor)
    activity = locked_activity(actor, activity_id)
    if state not in TRANSITIONS[activity.state]:
        raise ValidationError(
            {"state": "Holat o'tishi ruxsat etilmagan."}, code="invalid_transition"
        )
    if state in {
        Lifecycle.PUBLISHED,
        Lifecycle.REJECTED,
        Lifecycle.SUSPENDED,
        Lifecycle.ARCHIVED,
    } and not can_review(actor, activity):
        raise PermissionDenied()
    now = timezone.now()
    if state == Lifecycle.PUBLISHED:
        if (
            not activity.starts_at
            or not activity.ends_at
            or activity.ends_at <= now
            or not activity.venue.strip()
        ):
            raise ValidationError(
                {"state": "E'lon qilish uchun vaqt va manzil kerak."}, code="publication_incomplete"
            )
        if activity.published_at is None:
            activity.published_at = now
    if state == Lifecycle.REGISTRATION_OPEN:
        if activity.registration_policy == RegistrationPolicy.NONE or activity.starts_at <= now:
            raise ValidationError(
                {"state": "Ro'yxatdan o'tish ochilmaydi."}, code="registration_unavailable"
            )
    if state == Lifecycle.ACTIVE and not (activity.starts_at <= now < activity.ends_at):
        raise ValidationError(
            {"state": "Faoliyat vaqti boshlanmagan yoki tugagan."}, code="activity_window_closed"
        )
    if state == Lifecycle.COMPLETED and activity.ends_at > now:
        raise ValidationError({"state": "Faoliyat vaqti tugamagan."}, code="activity_not_ended")
    previous = activity.state
    activity.state = state
    validate_activity(activity)
    activity.save()
    record_event(
        actor_id=actor.id,
        action="activity_transitioned",
        object_id=activity.id,
        metadata={"from_state": previous, "to_state": state},
    )
    return activity


@transaction.atomic
def archive_activity(*, actor: User, activity_id: UUID) -> None:
    actor = current_actor(actor)
    activity = locked_activity(actor, activity_id)
    if not can_review(actor, activity):
        raise PermissionDenied()
    if activity.state != Lifecycle.ARCHIVED:
        transition_activity(actor=actor, activity_id=activity_id, state=Lifecycle.ARCHIVED)
