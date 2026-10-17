import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Club(models.Model):
    activity = models.OneToOneField(
        "activities.Activity", primary_key=True, on_delete=models.PROTECT, related_name="club"
    )
    timezone_name = models.CharField(max_length=64, default="Asia/Tashkent")

    def clean(self) -> None:
        if self.activity.type != "CLUB":
            raise ValidationError("Club requires a CLUB activity")
        try:
            ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationError({"timezone_name": "Unknown timezone"}) from None


class ClubSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="schedule")
    weekday = models.PositiveSmallIntegerField()
    starts_at = models.TimeField()
    ends_at = models.TimeField()

    class Meta:
        ordering = ["weekday", "starts_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(weekday__gte=1, weekday__lte=7), name="valid_club_weekday"
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="ordered_club_schedule"
            ),
            models.UniqueConstraint(
                fields=["club", "weekday", "starts_at"], name="unique_club_schedule_slot"
            ),
        ]


class MembershipState(models.TextChoices):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    LEFT = "LEFT"


class ClubMembership(models.Model):
    participant = models.OneToOneField(
        "activities.Participant",
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="club_membership",
    )
    status = models.CharField(max_length=16, choices=MembershipState.choices)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    reviewed_at = models.DateTimeField(null=True)
    reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "participant_id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=MembershipState.values), name="valid_club_membership_status"
            )
        ]


class SessionState(models.TextChoices):
    PLANNED = "PLANNED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class ClubSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.PROTECT, related_name="sessions")
    idempotency_key = models.UUIDField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=SessionState.choices, default=SessionState.PLANNED
    )
    opened_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="opened_club_sessions",
        blank=True,
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        related_name="closed_club_sessions",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["club", "idempotency_key"], name="unique_club_session_request"
            ),
            models.UniqueConstraint(fields=["club", "starts_at"], name="unique_club_session_start"),
            models.UniqueConstraint(
                fields=["club"],
                condition=Q(status=SessionState.OPEN),
                name="one_open_session_per_club",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="ordered_club_session"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status__in=[SessionState.PLANNED, SessionState.CANCELLED],
                        opened_at__isnull=True,
                        closed_at__isnull=True,
                        opened_by__isnull=True,
                        closed_by__isnull=True,
                    )
                    | Q(
                        status=SessionState.OPEN,
                        opened_at__isnull=False,
                        opened_by__isnull=False,
                        closed_at__isnull=True,
                        closed_by__isnull=True,
                    )
                    | Q(
                        status=SessionState.CLOSED,
                        opened_at__isnull=False,
                        opened_by__isnull=False,
                        closed_at__isnull=False,
                        closed_by__isnull=False,
                        closed_at__gte=F("opened_at"),
                    )
                ),
                name="valid_club_session_state",
            ),
        ]
