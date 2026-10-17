import uuid

from django.db import models


class Resource(models.TextChoices):
    FACULTIES = "faculties"
    DEPARTMENTS = "departments"
    GROUPS = "groups"
    SUBJECTS = "subjects"
    STUDENTS = "students"
    STAFF = "staff"


class SyncState(models.Model):
    class Status(models.TextChoices):
        RUNNING = "RUNNING"
        SUCCEEDED = "SUCCEEDED"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.CharField(max_length=16, choices=Resource.choices, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices)
    cursor = models.CharField(max_length=512, blank=True)
    last_attempt_at = models.DateTimeField()
    last_success_at = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=40, blank=True)
    records_processed = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["resource"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(resource__in=Resource.values), name="valid_hemis_resource"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["RUNNING", "SUCCEEDED", "FAILED"]),
                name="valid_hemis_sync_status",
            ),
        ]
