"""Explicit capabilities and ownership scope; Django flags do not grant API access."""

from uuid import UUID

from django.db.models import Q, QuerySet
from rest_framework.permissions import BasePermission

from .models import Role, ScopeType, User

CAPABILITIES = {
    Role.SUPERADMIN: {"users.read", "access.manage", "activities.manage"},
    Role.YOUTH_ADMIN: {"users.read", "activities.manage"},
    Role.FACULTY_YOUTH_RESPONSIBLE: {"users.read", "activities.manage"},
    Role.DEPARTMENT_RESPONSIBLE: {"users.read", "activities.manage"},
    Role.CLUB_LEADER: {"activities.manage"},
    Role.ACTIVITY_RESPONSIBLE: {"activities.manage"},
}


def has_capability(user: User, action: str, *, scopes: dict[str, UUID] | None = None) -> bool:
    if not user or not user.is_active:
        return False
    for grant in user.role_grants.all():
        if action not in CAPABILITIES.get(grant.role, set()):
            continue
        if grant.scope_type == ScopeType.GLOBAL:
            return True
        if scopes and scopes.get(grant.scope_type) == grant.scope_id:
            return True
    return False


def can_read_users(user: User) -> bool:
    return bool(
        user
        and user.is_active
        and user.role_grants.filter(
            role__in=[
                Role.SUPERADMIN,
                Role.YOUTH_ADMIN,
                Role.FACULTY_YOUTH_RESPONSIBLE,
                Role.DEPARTMENT_RESPONSIBLE,
            ]
        ).exists()
    )


def visible_users(actor: User) -> QuerySet[User]:
    queryset = User.objects.select_related("student_profile", "staff_profile").prefetch_related(
        "role_grants"
    )
    if has_capability(actor, "users.read"):
        return queryset.order_by("created_at", "id")
    faculty_ids = actor.role_grants.filter(
        role=Role.FACULTY_YOUTH_RESPONSIBLE, scope_type=ScopeType.FACULTY
    ).values_list("scope_id", flat=True)
    department_ids = actor.role_grants.filter(
        role=Role.DEPARTMENT_RESPONSIBLE, scope_type=ScopeType.DEPARTMENT
    ).values_list("scope_id", flat=True)
    return queryset.filter(
        Q(student_profile__faculty_id__in=faculty_ids)
        | Q(staff_profile__faculty_id__in=faculty_ids)
        | Q(student_profile__department_id__in=department_ids)
        | Q(staff_profile__department_id__in=department_ids)
    ).order_by("created_at", "id")


class CanReadUsers(BasePermission):
    def has_permission(self, request, view) -> bool:
        return can_read_users(request.user)


class CanManageAccess(BasePermission):
    def has_permission(self, request, view) -> bool:
        return has_capability(request.user, "access.manage")
