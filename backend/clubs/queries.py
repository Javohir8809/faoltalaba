from datetime import timedelta

from accounts.models import Role, User
from activities.models import ActivityRole, Lifecycle
from activities.policies import visible_activities
from django.db.models import BooleanField, Case, Count, Max, Prefetch, Q, QuerySet, When
from django.utils import timezone

from .models import Club, MembershipState, SessionState

OPERATIONAL_STATES = [Lifecycle.PUBLISHED, Lifecycle.REGISTRATION_OPEN, Lifecycle.ACTIVE]


def with_statistics(queryset: QuerySet[Club]) -> QuerySet[Club]:
    now = timezone.now()
    cutoff = now - timedelta(days=30)
    return queryset.annotate(
        active_members=Count(
            "activity__participants__club_membership",
            filter=Q(activity__participants__club_membership__status=MembershipState.ACTIVE),
            distinct=True,
        ),
        pending_members=Count(
            "activity__participants__club_membership",
            filter=Q(activity__participants__club_membership__status=MembershipState.PENDING),
            distinct=True,
        ),
        closed_sessions=Count(
            "sessions", filter=Q(sessions__status=SessionState.CLOSED), distinct=True
        ),
        last_session_at=Max("sessions__opened_at"),
    ).annotate(
        dormant=Case(
            When(
                Q(
                    activity__state__in=OPERATIONAL_STATES,
                    activity__starts_at__lte=now,
                    activity__ends_at__gt=now,
                )
                & (
                    Q(last_session_at__lt=cutoff)
                    | Q(last_session_at__isnull=True, activity__created_at__lt=cutoff)
                ),
                then=True,
            ),
            default=False,
            output_field=BooleanField(),
        )
    )


def visible_clubs(actor: User) -> QuerySet[Club]:
    return with_statistics(
        Club.objects.filter(activity_id__in=visible_activities(actor).values("id"))
        .select_related("activity")
        .prefetch_related(
            Prefetch(
                "activity__roles",
                queryset=ActivityRole.objects.filter(
                    grant__role=Role.CLUB_LEADER, grant__user__is_active=True
                ).select_related("grant"),
                to_attr="club_leader_assignments",
            )
        )
        .order_by("-activity__created_at", "activity_id")
    )
