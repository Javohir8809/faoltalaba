import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StaffProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="staff_profile"
    )
    faculty = models.ForeignKey(
        "organizations.Faculty", on_delete=models.PROTECT, null=True, blank=True
    )
    department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, null=True, blank=True
    )
    hemis_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    hemis_active = models.BooleanField(default=True)
    full_name = models.CharField(max_length=200, blank=True)

    def clean(self) -> None:
        if self.department_id and self.department.faculty_id != self.faculty_id:
            raise ValidationError("Department must belong to the faculty")

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
