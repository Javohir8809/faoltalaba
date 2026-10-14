import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from .managers import UserManager


class User(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(
        max_length=150, unique=True, validators=[UnicodeUsernameValidator()]
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = UserManager()
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._original_id = self.pk

    @transaction.atomic
    def save(self, *args, **kwargs) -> None:
        if not self._state.adding and self.pk != self._original_id:
            raise ValidationError("User UUID is immutable")
        password_changed = False
        if not self._state.adding:
            previous = type(self).objects.select_for_update().get(pk=self.pk)
            fields = kwargs.get("update_fields")
            password_changed = (
                fields is None or "password" in fields
            ) and previous.password != self.password
        super().save(*args, **kwargs)
        self._original_id = self.pk
        if password_changed:
            from audit.services import record_event
            from django.utils import timezone

            RefreshSession.objects.filter(user=self, revoked_at__isnull=True).update(
                revoked_at=timezone.now()
            )
            record_event(actor_id=None, action="password_changed", object_id=self.id)


class Role(models.TextChoices):
    SUPERADMIN = "SUPERADMIN"
    YOUTH_ADMIN = "YOUTH_ADMIN"
    FACULTY_YOUTH_RESPONSIBLE = "FACULTY_YOUTH_RESPONSIBLE"
    DEPARTMENT_RESPONSIBLE = "DEPARTMENT_RESPONSIBLE"
    CLUB_LEADER = "CLUB_LEADER"
    ACTIVITY_RESPONSIBLE = "ACTIVITY_RESPONSIBLE"
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    SCIENCE_OFFICE = "SCIENCE_OFFICE"
    SPORTS_OFFICE = "SPORTS_OFFICE"
    INTERNATIONAL_OFFICE = "INTERNATIONAL_OFFICE"
    LIBRARY_OPERATOR = "LIBRARY_OPERATOR"
    ANALYTICS_VIEWER = "ANALYTICS_VIEWER"


class ScopeType(models.TextChoices):
    GLOBAL = "GLOBAL"
    FACULTY = "FACULTY"
    DEPARTMENT = "DEPARTMENT"
    ACTIVITY = "ACTIVITY"


GLOBAL_ROLES = [
    Role.SUPERADMIN,
    Role.YOUTH_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.SCIENCE_OFFICE,
    Role.SPORTS_OFFICE,
    Role.INTERNATIONAL_OFFICE,
    Role.LIBRARY_OPERATOR,
    Role.ANALYTICS_VIEWER,
]


class RoleGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="role_grants")
    role = models.CharField(max_length=32, choices=Role.choices)
    scope_type = models.CharField(max_length=16, choices=ScopeType.choices)
    scope_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role", "scope_type", "scope_id"],
                nulls_distinct=False,
                name="unique_user_role_scope",
            ),
            models.CheckConstraint(
                condition=(
                    Q(scope_type=ScopeType.GLOBAL, scope_id__isnull=True, role__in=GLOBAL_ROLES)
                    | Q(
                        scope_type=ScopeType.FACULTY,
                        scope_id__isnull=False,
                        role=Role.FACULTY_YOUTH_RESPONSIBLE,
                    )
                    | Q(
                        scope_type=ScopeType.DEPARTMENT,
                        scope_id__isnull=False,
                        role=Role.DEPARTMENT_RESPONSIBLE,
                    )
                    | Q(
                        scope_type=ScopeType.ACTIVITY,
                        scope_id__isnull=False,
                        role__in=[Role.CLUB_LEADER, Role.ACTIVITY_RESPONSIBLE],
                    )
                ),
                name="valid_role_scope",
            ),
        ]


class ExternalIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="external_identities")
    source = models.CharField(max_length=16, choices=[("HEMIS", "HEMIS"), ("EKT", "EKT")])
    external_id = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="unique_external_identity"
            ),
            models.UniqueConstraint(fields=["source", "user"], name="unique_user_external_source"),
        ]


class RefreshSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="refresh_sessions")
    refresh_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True)
