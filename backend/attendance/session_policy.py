"""Current session provider: clubs; all attendance writes share club lock order."""

from uuid import UUID

from accounts.models import User
from activities.models import Activity
from activities.policies import managed_query
from clubs.models import ClubSession
from clubs.services import managed_club
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404


def visible_sessions(actor: User) -> QuerySet[ClubSession]:
    return ClubSession.objects.filter(
        club_id__in=Activity.objects.filter(managed_query(actor)).values("pk")
    ).select_related("club__activity")


def lock_session(actor: User, session_id: UUID) -> tuple[User, ClubSession]:
    reference = get_object_or_404(visible_sessions(actor), pk=session_id)
    actor, club = managed_club(actor, reference.club_id)
    session = get_object_or_404(ClubSession.objects.select_for_update(), pk=session_id, club=club)
    session.club = club
    return actor, session
