from uuid import UUID

from accounts.models import User
from activities.models import Activity, Participant, ParticipantState, RegistrationPolicy
from activities.policies import eligible_query
from activities.services import current_actor
from audit.services import record_event
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from students.models import StudentProfile

from .models import Club, ClubMembership, MembershipState
from .queries import OPERATIONAL_STATES
from .services import lock_club, managed_club


def require_enrollment(club: Club, student: User) -> StudentProfile:
    if not Activity.objects.filter(eligible_query(student), pk=club.pk).exists():
        raise PermissionDenied()
    if (
        club.activity.state not in OPERATIONAL_STATES
        or club.activity.ends_at <= timezone.now()
        or club.activity.registration_policy == RegistrationPolicy.NONE
    ):
        raise ValidationError({"club": "A'zolik qabul qilinmayapti."}, code="join_closed")
    return StudentProfile.objects.get(user=student)


def require_capacity(club: Club) -> None:
    count = ClubMembership.objects.filter(
        participant__activity_id=club.pk, status=MembershipState.ACTIVE
    ).count()
    if club.activity.capacity is not None and count >= club.activity.capacity:
        raise ValidationError({"club": "Bo'sh joy qolmadi."}, code="club_full")


def save_state(membership: ClubMembership, *, status: str, actor: User) -> ClubMembership:
    previous = membership.status if not membership._state.adding else None
    membership.status = status
    membership.participant.state = {
        MembershipState.ACTIVE: ParticipantState.ACTIVE,
        MembershipState.PENDING: ParticipantState.PENDING,
    }.get(status, ParticipantState.CANCELLED)
    membership.participant.save(update_fields=["state"])
    membership.save()
    record_event(
        actor_id=actor.id,
        action="club_membership_changed",
        object_id=membership.pk,
        metadata={
            "from_state": previous,
            "to_state": status,
            "scope_id": str(membership.participant.activity_id),
        },
    )
    return membership


@transaction.atomic
def join_club(*, actor: User, club_id: UUID) -> ClubMembership:
    actor = current_actor(actor)
    club = lock_club(club_id)
    student = require_enrollment(club, actor)
    membership = (
        ClubMembership.objects.select_related("participant")
        .filter(participant__activity_id=club.pk, participant__student=student)
        .first()
    )
    if membership and membership.status in {MembershipState.ACTIVE, MembershipState.PENDING}:
        return membership
    if membership and membership.status == MembershipState.REJECTED:
        raise ValidationError({"membership": "Ariza rad etilgan."}, code="membership_rejected")
    status = (
        MembershipState.ACTIVE
        if club.activity.registration_policy == RegistrationPolicy.OPEN
        else MembershipState.PENDING
    )
    if status == MembershipState.ACTIVE:
        require_capacity(club)
    if membership is None:
        participant, _ = Participant.objects.get_or_create(activity=club.activity, student=student)
        membership = ClubMembership(participant=participant)
    membership.reviewer = None
    membership.reviewed_at = None
    membership.reason = ""
    return save_state(membership, status=status, actor=actor)


@transaction.atomic
def leave_club(*, actor: User, club_id: UUID) -> ClubMembership:
    actor = current_actor(actor)
    lock_club(club_id)
    from django.shortcuts import get_object_or_404

    membership = get_object_or_404(
        ClubMembership.objects.select_related("participant"),
        participant__activity_id=club_id,
        participant__student__user=actor,
    )
    if membership.status in {MembershipState.ACTIVE, MembershipState.PENDING}:
        return save_state(membership, status=MembershipState.LEFT, actor=actor)
    return membership


@transaction.atomic
def decide_membership(
    *, actor: User, club_id: UUID, membership_id: UUID, decision: str, reason: str = ""
) -> ClubMembership:
    actor, club = managed_club(actor, club_id)
    from django.shortcuts import get_object_or_404

    membership = get_object_or_404(
        ClubMembership.objects.select_related("participant__student__user"),
        pk=membership_id,
        participant__activity_id=club.pk,
    )
    status = {"APPROVE": MembershipState.ACTIVE, "REJECT": MembershipState.REJECTED}.get(decision)
    if (
        not status
        or (status == MembershipState.REJECTED and not reason.strip())
        or len(reason) > 500
    ):
        raise ValidationError({"decision": "Qaror va rad etish sababi kerak."})
    if membership.status == status:
        return membership
    if membership.status != MembershipState.PENDING:
        raise ValidationError(
            {"membership": "Ariza kutilayotgan holatda emas."}, code="invalid_transition"
        )
    if status == MembershipState.ACTIVE:
        student = current_actor(membership.participant.student.user)
        require_enrollment(club, student)
        require_capacity(club)
    membership.reviewer = actor
    membership.reviewed_at = timezone.now()
    membership.reason = reason if status == MembershipState.REJECTED else ""
    return save_state(membership, status=status, actor=actor)
