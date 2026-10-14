import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StudentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="student_profile"
    )
    faculty = models.ForeignKey("organizations.Faculty", on_delete=models.PROTECT)
    department = models.ForeignKey(
        "organizations.Department", on_delete=models.PROTECT, null=True, blank=True
    )

    def clean(self) -> None:
        if self.department_id and self.department.faculty_id != self.faculty_id:
            raise ValidationError("Department must belong to the faculty")

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)
