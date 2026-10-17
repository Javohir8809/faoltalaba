from datetime import datetime
from uuid import UUID

from accounts.models import User
from activities.models import Activity, ParticipantState
from activities.policies import eligible_query
from audit.services import record_event
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .models import ClubMembership, ClubSession, MembershipState, SessionState
from .queries import OPERATIONAL_STATES
from .services import managed_club, validate_model


class IdempotencyConflict(APIException):
    status_code = 409
    default_code = "idempotency_conflict"
    default_detail = "So'rov kaliti boshqa ma'lumot bilan ishlatilgan."


@transaction.atomic
def create_session(
    *, actor: User, club_id: UUID, starts_at: datetime, ends_at: datetime, idempotency_key: UUID
) -> ClubSession:
    actor, club = managed_club(actor, club_id)
    previous = ClubSession.objects.filter(club=club, idempotency_key=idempotency_key).first()
    if previous:
        if previous.starts_at != starts_at or previous.ends_at != ends_at:
            raise IdempotencyConflict()
        return previous
    if club.activity.state not in OPERATIONAL_STATES:
        raise ValidationError({"club": "To'garak faol emas."}, code="session_unavailable")
    if (
        timezone.is_naive(starts_at)
        or timezone.is_naive(ends_at)
        or not (club.activity.starts_at <= starts_at < ends_at <= club.activity.ends_at)
        or ends_at <= timezone.now()
    ):
        raise ValidationError(
            {"starts_at": "Sessiya vaqti noto'g'ri."}, code="session_window_invalid"
        )
    session = ClubSession(
        club=club, starts_at=starts_at, ends_at=ends_at, idempotency_key=idempotency_key
    )
    validate_model(session)
    session.save()
    record_event(
        actor_id=actor.id,
        action="club_session_created",
        object_id=session.id,
        metadata={"scope_id": str(club.pk)},
    )
    return session


@transaction.atomic
def change_session(*, actor: User, club_id: UUID, session_id: UUID, opening: bool) -> ClubSession:
    actor, club = managed_club(actor, club_id)
    from django.shortcuts import get_object_or_404

    session = get_object_or_404(ClubSession.objects.select_for_update(), pk=session_id, club=club)
    now = timezone.now()
    if opening:
        if session.status == SessionState.OPEN:
            return session
        if session.status != SessionState.PLANNED or club.activity.state not in OPERATIONAL_STATES:
            raise ValidationError({"status": "Sessiya ochilmaydi."}, code="invalid_transition")
        if not (
            session.starts_at <= now < session.ends_at
            and club.activity.starts_at <= now < club.activity.ends_at
        ):
            raise ValidationError({"status": "Sessiya oynasi yopiq."}, code="session_window_closed")
        if ClubSession.objects.filter(club=club, status=SessionState.OPEN).exists():
            raise ValidationError({"status": "Boshqa sessiya ochiq."}, code="session_already_open")
        session.status = SessionState.OPEN
        session.opened_at = now
        session.opened_by = actor
    else:
        if session.status == SessionState.CLOSED:
            return session
        if session.status != SessionState.OPEN:
            raise ValidationError(
                {"status": "Faqat ochiq sessiya yopiladi."}, code="invalid_transition"
            )
        session.status = SessionState.CLOSED
        session.closed_at = now
        session.closed_by = actor
    validate_model(session)
    session.save()
    record_event(
        actor_id=actor.id,
        action="club_session_opened" if opening else "club_session_closed",
        object_id=session.id,
        metadata={"scope_id": str(club.pk)},
    )
    return session


def eligible_for_attendance(*, session: ClubSession, student: User) -> bool:
    """Read-only eligibility foundation. Phase 6 must lock/recheck inside check-in."""
    if not student or not User.objects.filter(pk=student.pk, is_active=True).exists():
        return False
    current = ClubSession.objects.select_related("club__activity").get(pk=session.pk)
    now = timezone.now()
    if (
        current.status != SessionState.OPEN
        or current.club.activity.state not in OPERATIONAL_STATES
        or not (
            current.starts_at <= now < current.ends_at
            and current.club.activity.starts_at <= now < current.club.activity.ends_at
        )
    ):
        return False
    # Never trust a caller's prefetched grants when evaluating eligibility.
    student = User.objects.get(pk=student.pk)
    return (
        Activity.objects.filter(eligible_query(student), pk=current.club_id).exists()
        and ClubMembership.objects.filter(
            participant__activity_id=current.club_id,
            participant__student__user=student,
            participant__state=ParticipantState.ACTIVE,
            status=MembershipState.ACTIVE,
        ).exists()
    )
