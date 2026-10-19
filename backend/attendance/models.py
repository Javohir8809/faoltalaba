import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Method(models.TextChoices):
    NFC = "NFC"
    QR = "QR"
    MANUAL = "MANUAL"


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT"
    VOIDED = "VOIDED"


class AttendanceDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    installation_id = models.UUIDField()
    label = models.CharField(max_length=80)
    platform = models.CharField(
        max_length=16,
        choices=[(v, v) for v in ["UNKNOWN", "ANDROID", "IOS", "WEB", "SCANNER"]],
        default="UNKNOWN",
    )
    nfc_supported = models.BooleanField(null=True, blank=True)
    camera_supported = models.BooleanField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "installation_id"], name="attendance_device_installation_unique"
            )
        ]


class StudentCardMapping(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=[("NFC", "NFC"), ("QR", "QR")])
    token_digest = models.CharField(max_length=64, editable=False)
    protocol = models.CharField(
        max_length=16,
        choices=[(v, v) for v in ["UNKNOWN", "ISO14443", "ISO15693", "OTHER"]],
        default="UNKNOWN",
    )
    variant = models.CharField(max_length=64, blank=True)
    uid_readable = models.BooleanField(null=True, blank=True)
    enrolled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrolled_cards"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="revoked_cards",
        null=True,
        blank=True,
    )
    revocation_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "token_digest"], name="attendance_token_unique"
            ),
            models.CheckConstraint(
                condition=Q(kind__in=["NFC", "QR"]), name="attendance_card_kind_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(revoked_at__isnull=True, revoked_by__isnull=True, revocation_reason="")
                    | (
                        Q(revoked_at__isnull=False, revoked_by__isnull=False)
                        & ~Q(revocation_reason="")
                    )
                ),
                name="attendance_card_revocation_shape",
            ),
        ]


class AttendanceRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey("clubs.ClubSession", on_delete=models.PROTECT)
    student = models.ForeignKey("students.StudentProfile", on_delete=models.PROTECT)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    device = models.ForeignKey(AttendanceDevice, on_delete=models.PROTECT, null=True, blank=True)
    checked_in_at = models.DateTimeField(editable=False)
    method = models.CharField(max_length=8, choices=Method.choices)
    status = models.CharField(
        max_length=8, choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT
    )
    note = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-checked_in_at", "id"]
        indexes = [models.Index(fields=["student", "-checked_in_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"], name="attendance_session_student_unique"
            ),
            models.CheckConstraint(
                condition=Q(method__in=Method.values), name="attendance_method_valid"
            ),
            models.CheckConstraint(
                condition=Q(status__in=AttendanceStatus.values), name="attendance_status_valid"
            ),
            models.CheckConstraint(condition=Q(version__gte=1), name="attendance_version_positive"),
        ]


class AttendanceChange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(AttendanceRecord, on_delete=models.PROTECT, related_name="changes")
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(
        max_length=20, choices=[(v, v) for v in ["CHECK_IN", "MANUAL_CHECK_IN", "CORRECTION"]]
    )
    reason = models.CharField(max_length=500, blank=True)
    previous_status = models.CharField(max_length=8, blank=True)
    new_status = models.CharField(max_length=8, choices=AttendanceStatus.choices)
    previous_note = models.CharField(max_length=500, blank=True)
    new_note = models.CharField(max_length=500, blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    request_digest = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(
                fields=["record", "version"], name="attendance_change_version_unique"
            ),
            models.UniqueConstraint(
                fields=["record", "request_id"], name="attendance_change_request_unique"
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        version=1,
                        action="CHECK_IN",
                        previous_status="",
                        reason="",
                        request_id__isnull=True,
                    )
                    | (
                        Q(
                            version=1,
                            action="MANUAL_CHECK_IN",
                            previous_status="",
                            request_id__isnull=True,
                        )
                        & ~Q(reason="")
                    )
                    | (
                        Q(
                            version__gt=1,
                            action="CORRECTION",
                            previous_status__in=AttendanceStatus.values,
                            request_id__isnull=False,
                        )
                        & ~Q(reason="")
                    )
                ),
                name="attendance_change_shape",
            ),
        ]

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise ValueError("Attendance changes are immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        raise ValueError("Attendance changes are immutable")
