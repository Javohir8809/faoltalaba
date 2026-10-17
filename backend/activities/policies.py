"""Local object scope and student discovery; RoleGrant remains the RBAC authority."""

from accounts.models import Role, ScopeType, User
from accounts.policies import has_capability
from django.db.models import Q, QuerySet
from students.models import StudentProfile

from .models import Activity, ActivityType, Audience, Lifecycle, Visibility


def managed_query(actor: User) -> Q:
    if has_capability(actor, "activities.manage"):
        return Q()
    grants = actor.role_grants.all()
    return (
        Q(
            faculty_id__in=grants.filter(
                role=Role.FACULTY_YOUTH_RESPONSIBLE, scope_type=ScopeType.FACULTY
            ).values("scope_id")
        )
        | Q(
            department_id__in=grants.filter(
                role=Role.DEPARTMENT_RESPONSIBLE, scope_type=ScopeType.DEPARTMENT
            ).values("scope_id")
        )
        | Q(
            id__in=grants.filter(
                role=Role.ACTIVITY_RESPONSIBLE, scope_type=ScopeType.ACTIVITY
            ).values("scope_id")
        )
        | Q(
            type=ActivityType.CLUB,
            id__in=grants.filter(role=Role.CLUB_LEADER, scope_type=ScopeType.ACTIVITY).values(
                "scope_id"
            ),
        )
    )


def can_manage(actor: User, activity: Activity) -> bool:
    return bool(
        actor
        and actor.is_active
        and Activity.objects.filter(managed_query(actor), pk=activity.id).exists()
    )


def can_review(actor: User, activity: Activity) -> bool:
    scopes = {}
    if activity.faculty_id:
        scopes[ScopeType.FACULTY] = activity.faculty_id
    if activity.department_id:
        scopes[ScopeType.DEPARTMENT] = activity.department_id
    return has_capability(actor, "activities.manage", scopes=scopes)


def eligible_query(actor: User) -> Q:
    deny = Q(pk__in=[])
    if not actor.role_grants.filter(role=Role.STUDENT, scope_type=ScopeType.GLOBAL).exists():
        return deny
    profile = (
        StudentProfile.objects.select_related("faculty", "department", "group")
        .filter(user=actor)
        .first()
    )
    if not profile or not profile.hemis_active or not profile.faculty.hemis_active:
        return deny
    if profile.department_id and (
        not profile.department.hemis_active or profile.department.faculty_id != profile.faculty_id
    ):
        return deny
    if profile.group_id and (
        not profile.group.hemis_active or profile.group.faculty_id != profile.faculty_id
    ):
        return deny
    audience = Q(audience=Audience.ALL_STUDENTS) | Q(
        audience=Audience.FACULTY, audience_faculty_id=profile.faculty_id
    )
    if profile.department_id:
        audience |= Q(audience=Audience.DEPARTMENT, audience_department_id=profile.department_id)
    if profile.group_id:
        audience |= Q(audience=Audience.GROUP, audience_group_id=profile.group_id)
    return audience & Q(
        visibility=Visibility.INSTITUTION,
        published_at__isnull=False,
        state__in=[
            Lifecycle.PUBLISHED,
            Lifecycle.REGISTRATION_OPEN,
            Lifecycle.ACTIVE,
            Lifecycle.COMPLETED,
            Lifecycle.CANCELLED,
        ],
    )


def visible_activities(actor: User) -> QuerySet[Activity]:
    queryset = Activity.objects.select_related("faculty", "department")
    if not actor or not actor.is_active:
        return queryset.none()
    if has_capability(actor, "activities.manage"):
        return queryset
    return queryset.filter(managed_query(actor) | eligible_query(actor))
