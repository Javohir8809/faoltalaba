import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class ActivityType(models.TextChoices):
    CLUB = "CLUB"
    EVENT = "EVENT"
    VOLUNTEERING = "VOLUNTEERING"
    COMPETITION = "COMPETITION"
    SCIENCE = "SCIENCE"
    SPORT = "SPORT"
    CULTURE = "CULTURE"
    INNOVATION = "INNOVATION"
    INTERNATIONAL = "INTERNATIONAL"
    MENTORING = "MENTORING"
    PROFESSIONAL_DEVELOPMENT = "PROFESSIONAL_DEVELOPMENT"
    MEDIA = "MEDIA"
    ECO_SOCIAL = "ECO_SOCIAL"
    INITIATIVE = "INITIATIVE"
    OTHER = "OTHER"


class Lifecycle(models.TextChoices):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PUBLISHED = "PUBLISHED"
    REGISTRATION_OPEN = "REGISTRATION_OPEN"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"


class Audience(models.TextChoices):
    ALL_STUDENTS = "ALL_STUDENTS"
    FACULTY = "FACULTY"
    DEPARTMENT = "DEPARTMENT"
    GROUP = "GROUP"


class Visibility(models.TextChoices):
    INSTITUTION = "INSTITUTION"
    MANAGERS_ONLY = "MANAGERS_ONLY"


class RegistrationPolicy(models.TextChoices):
    NONE = "NONE"
    OPEN = "OPEN"
    APPROVAL = "APPROVAL"


class AttendancePolicy(models.TextChoices):
    NONE = "NONE"
    REQUIRED = "REQUIRED"


class ResultPolicy(models.TextChoices):
    NONE = "NONE"
    VERIFIED_PARTICIPATION = "VERIFIED_PARTICIPATION"


class Activity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, max_length=10000)
    type = models.CharField(max_length=32, choices=ActivityType.choices)
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    faculty = models.ForeignKey(
        "organizations.Faculty", null=True, blank=True, on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        "organizations.Department", null=True, blank=True, on_delete=models.PROTECT
    )
    state = models.CharField(max_length=24, choices=Lifecycle.choices, default=Lifecycle.DRAFT)
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.INSTITUTION
    )
    audience = models.CharField(
        max_length=16, choices=Audience.choices, default=Audience.ALL_STUDENTS
    )
    audience_faculty = models.ForeignKey(
        "organizations.Faculty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="targeted_activities",
    )
    audience_department = models.ForeignKey(
        "organizations.Department",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="targeted_activities",
    )
    audience_group = models.ForeignKey(
        "organizations.Group", null=True, blank=True, on_delete=models.PROTECT
    )
    capacity = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    venue = models.CharField(max_length=250, blank=True)
    registration_policy = models.CharField(
        max_length=16, choices=RegistrationPolicy.choices, default=RegistrationPolicy.NONE
    )
    attendance_policy = models.CharField(
        max_length=16, choices=AttendancePolicy.choices, default=AttendancePolicy.REQUIRED
    )
    evidence_required = models.BooleanField(default=False)
    result_policy = models.CharField(
        max_length=24, choices=ResultPolicy.choices, default=ResultPolicy.NONE
    )
    published_at = models.DateTimeField(null=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self) -> None:
        if (self.starts_at and timezone.is_naive(self.starts_at)) or (
            self.ends_at and timezone.is_naive(self.ends_at)
        ):
            raise ValidationError({"starts_at": "Timezone-aware dates required"})
        if self.department_id and (
            not self.faculty_id or self.department.faculty_id != self.faculty_id
        ):
            raise ValidationError({"department": "Department must belong to owning faculty"})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "End must follow start"})

    class Meta:
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["state", "starts_at"]),
            models.Index(fields=["faculty", "department"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~Q(
                        state__in=[
                            Lifecycle.PUBLISHED,
                            Lifecycle.REGISTRATION_OPEN,
                            Lifecycle.ACTIVE,
                            Lifecycle.COMPLETED,
                            Lifecycle.SUSPENDED,
                        ]
                    )
                    | Q(published_at__isnull=False, starts_at__isnull=False, ends_at__isnull=False)
                ),
                name="published_activity_needs_dates",
            ),
            models.CheckConstraint(
                condition=Q(type__in=ActivityType.values), name="valid_activity_type"
            ),
            models.CheckConstraint(
                condition=Q(state__in=Lifecycle.values), name="valid_activity_state"
            ),
            models.CheckConstraint(
                condition=Q(visibility__in=Visibility.values), name="valid_activity_visibility"
            ),
            models.CheckConstraint(
                condition=Q(registration_policy__in=RegistrationPolicy.values),
                name="valid_registration_policy",
            ),
            models.CheckConstraint(
                condition=Q(attendance_policy__in=AttendancePolicy.values),
                name="valid_attendance_policy",
            ),
            models.CheckConstraint(
                condition=Q(result_policy__in=ResultPolicy.values), name="valid_result_policy"
            ),
            models.CheckConstraint(
                condition=Q(capacity__isnull=True) | Q(capacity__gt=0),
                name="positive_activity_capacity",
            ),
            models.CheckConstraint(
                condition=Q(department__isnull=True) | Q(faculty__isnull=False),
                name="activity_department_needs_faculty",
            ),
            models.CheckConstraint(
                condition=Q(starts_at__isnull=True, ends_at__isnull=True)
                | Q(starts_at__isnull=False, ends_at__isnull=False, ends_at__gt=F("starts_at")),
                name="valid_activity_dates",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        audience=Audience.ALL_STUDENTS,
                        audience_faculty__isnull=True,
                        audience_department__isnull=True,
                        audience_group__isnull=True,
                    )
                    | Q(
                        audience=Audience.FACULTY,
                        audience_faculty__isnull=False,
                        audience_department__isnull=True,
                        audience_group__isnull=True,
                    )
                    | Q(
                        audience=Audience.DEPARTMENT,
                        audience_faculty__isnull=True,
                        audience_department__isnull=False,
                        audience_group__isnull=True,
                    )
                    | Q(
                        audience=Audience.GROUP,
                        audience_faculty__isnull=True,
                        audience_department__isnull=True,
                        audience_group__isnull=False,
                    )
                ),
                name="valid_activity_audience",
            ),
        ]


class ActivityRole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT, related_name="roles")
    grant = models.OneToOneField(
        "accounts.RoleGrant", on_delete=models.CASCADE, related_name="activity_assignment"
    )

    def clean(self) -> None:
        from accounts.models import Role, ScopeType

        if (
            self.grant.scope_type != ScopeType.ACTIVITY
            or self.grant.scope_id != self.activity_id
            or self.grant.role not in {Role.ACTIVITY_RESPONSIBLE, Role.CLUB_LEADER}
        ):
            raise ValidationError("Assignment must match an activity-scoped grant")
        if self.grant.role == Role.CLUB_LEADER and self.activity.type != ActivityType.CLUB:
            raise ValidationError("Club leader requires a club activity")

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ParticipantState(models.TextChoices):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Participant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT, related_name="participants")
    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT)
    state = models.CharField(
        max_length=16, choices=ParticipantState.choices, default=ParticipantState.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "student"], name="unique_activity_participant"
            ),
            models.CheckConstraint(
                condition=Q(state__in=ParticipantState.values), name="valid_participant_state"
            ),
        ]
