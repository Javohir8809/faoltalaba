import uuid

from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor_id = models.UUIDField(null=True)
    action = models.CharField(max_length=64)
    object_id = models.UUIDField()
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [models.Index(fields=["object_id", "created_at"])]

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise ValueError("Audit events are immutable")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs) -> None:
        raise ValueError("Audit events cannot be deleted")
