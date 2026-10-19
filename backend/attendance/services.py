import hashlib
import json
from uuid import UUID

from accounts.models import User
from accounts.policies import CAPABILITIES, has_capability
from activities.services import current_actor
from audit.services import record_event
from clubs.sessions import IdempotencyConflict, eligible_for_attendance
from django.db import connection, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from students.models import StudentProfile

from .models import AttendanceChange, AttendanceDevice, AttendanceRecord, StudentCardMapping
from .session_policy import lock_session
from .tokens import ADAPTERS


def manager(actor: User) -> User:
    actor = current_actor(actor)
    roles = [
        role for role, capabilities in CAPABILITIES.items() if "activities.manage" in capabilities
    ]
    if not actor.role_grants.filter(role__in=roles).exists():
        raise PermissionDenied()
    return actor


def require_reason(reason: str) -> str:
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise ValidationError({"reason": "Sabab majburiy."}, code="reason_required")
    return reason.strip()


def audit(actor: User, action: str, object_id: UUID) -> None:
    record_event(actor_id=actor.id, action=action, object_id=object_id)


@transaction.atomic
def save_device(*, actor: User, device_id: UUID | None = None, **data) -> AttendanceDevice:
    actor = manager(actor)
    if device_id:
        device = get_object_or_404(
            AttendanceDevice.objects.select_for_update(), pk=device_id, owner=actor
        )
    else:
        # Serialize first registration per operator as well as repeated installations.
        User.objects.select_for_update().get(pk=actor.pk)
        device = AttendanceDevice.objects.filter(
            owner=actor, installation_id=data["installation_id"]
        ).first()
        if device:
            return device
        device = AttendanceDevice(owner=actor)
    for name, value in data.items():
        setattr(device, name, value)
    device.full_clean()
    device.save()
    audit(actor, "attendance_device_saved", device.id)
    return device


@transaction.atomic
def enroll_card(
    *, actor: User, student_id: UUID, kind: str, token: str, **metadata
) -> StudentCardMapping:
    actor = current_actor(actor)
    if not has_capability(actor, "access.manage"):
        raise PermissionDenied()
    if kind not in ADAPTERS:
        raise ValidationError({"kind": "Usul noto‘g‘ri."})
    digest = ADAPTERS[kind].digest(token)
    # Serialize enrollment of absent rows without locking profiles before mappings.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int(digest[:15], 16)])
    student = get_object_or_404(StudentProfile, pk=student_id)
    previous = (
        StudentCardMapping.objects.select_for_update()
        .filter(kind=kind, token_digest=digest)
        .first()
    )
    if previous:
        if previous.student_id != student.id or previous.revoked_at:
            raise IdempotencyConflict()
        return previous
    card = StudentCardMapping(
        student=student, kind=kind, token_digest=digest, enrolled_by=actor, **metadata
    )
    card.full_clean()
    card.save()
    audit(actor, "attendance_card_enrolled", card.id)
    return card


@transaction.atomic
def revoke_card(*, actor: User, card_id: UUID, reason: str) -> StudentCardMapping:
    actor = current_actor(actor)
    if not has_capability(actor, "access.manage"):
        raise PermissionDenied()
    reason = require_reason(reason)
    card = get_object_or_404(StudentCardMapping.objects.select_for_update(), pk=card_id)
    if card.revoked_at:
        return card
    card.revoked_at, card.revoked_by, card.revocation_reason = timezone.now(), actor, reason
    card.save(update_fields=["revoked_at", "revoked_by", "revocation_reason"])
    audit(actor, "attendance_card_revoked", card.id)
    return card


@transaction.atomic
def check_in(
    *,
    actor: User,
    session_id: UUID,
    method: str,
    token: str | None = None,
    student_id: UUID | None = None,
    reason: str = "",
    device_id: UUID | None = None,
    note: str = "",
) -> AttendanceRecord:
    actor = manager(actor)
    actor, session = lock_session(actor, session_id)
    if method == "MANUAL":
        reason = require_reason(reason)
        if token is not None or student_id is None:
            raise ValidationError({"method": "Qo‘lda qayd uchun talaba kerak."})
    elif method in ADAPTERS and student_id is None and not reason:
        card = (
            StudentCardMapping.objects.select_for_update()
            .filter(
                kind=method, token_digest=ADAPTERS[method].digest(token), revoked_at__isnull=True
            )
            .first()
        )
        if card is None:
            raise ValidationError({"token": "Identifikator yaroqsiz."}, code="invalid_card")
        student_id = card.student_id
    else:
        raise ValidationError({"method": "Usul ma’lumotlari noto‘g‘ri."})
    student = get_object_or_404(StudentProfile.objects.select_for_update(), pk=student_id)
    device = None
    if device_id:
        device = get_object_or_404(
            AttendanceDevice.objects.select_for_update(), pk=device_id, owner=actor, is_active=True
        )
    if not isinstance(note, str) or len(note) > 500:
        raise ValidationError({"note": "Izoh juda uzun."})
    previous = AttendanceRecord.objects.filter(session=session, student=student).first()
    # Check the server window after every potentially blocking row lock.
    now = timezone.now()
    if not eligible_for_attendance(session=session, student=student.user) or not (
        session.starts_at <= now < session.ends_at
        and session.club.activity.starts_at <= now < session.club.activity.ends_at
    ):
        raise ValidationError(
            {"student": "Davomat qaydi uchun ruxsat yo‘q."}, code="attendance_ineligible"
        )
    if previous:
        return previous
    record = AttendanceRecord.objects.create(
        session=session,
        student=student,
        method=method,
        recorded_by=actor,
        device=device,
        checked_in_at=now,
        note=note,
    )
    AttendanceChange.objects.create(
        record=record,
        version=1,
        actor=actor,
        action="MANUAL_CHECK_IN" if method == "MANUAL" else "CHECK_IN",
        reason=reason,
        new_status=record.status,
        new_note=note,
    )
    if device:
        AttendanceDevice.objects.filter(pk=device.pk).update(last_seen_at=record.checked_in_at)
    audit(actor, "attendance_checked_in", record.id)
    return record


@transaction.atomic
def correct_record(
    *,
    actor: User,
    record_id: UUID,
    status: str,
    reason: str,
    expected_version: int,
    idempotency_key: UUID,
    note: str | None = None,
) -> AttendanceRecord:
    actor = manager(actor)
    reference = get_object_or_404(AttendanceRecord, pk=record_id)
    actor, _ = lock_session(actor, reference.session_id)
    record = AttendanceRecord.objects.select_for_update().get(pk=record_id)
    reason = require_reason(reason)
    if status not in ["PRESENT", "VOIDED"] or (
        note is not None and (not isinstance(note, str) or len(note) > 500)
    ):
        raise ValidationError({"status": "Tuzatish noto‘g‘ri."})
    digest = hashlib.sha256(
        json.dumps(
            [status, note, reason, expected_version], ensure_ascii=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    previous = record.changes.filter(request_id=idempotency_key).first()
    if previous:
        if previous.actor_id != actor.id or previous.request_digest != digest:
            raise IdempotencyConflict()
        return record
    if record.version != expected_version:
        raise IdempotencyConflict()
    next_note = record.note if note is None else note
    AttendanceChange.objects.create(
        record=record,
        version=record.version + 1,
        actor=actor,
        action="CORRECTION",
        reason=reason,
        previous_status=record.status,
        new_status=status,
        previous_note=record.note,
        new_note=next_note,
        request_id=idempotency_key,
        request_digest=digest,
    )
    record.status, record.note, record.version = status, next_note, record.version + 1
    record.save(update_fields=["status", "note", "version"])
    audit(actor, "attendance_corrected", record.id)
    return record
