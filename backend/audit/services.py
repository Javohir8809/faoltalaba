from uuid import UUID

from .models import AuditEvent


def record_event(
    *, actor_id: UUID | None, action: str, object_id: UUID, metadata: dict | None = None
) -> AuditEvent:
    allowed = {"role", "scope_type", "scope_id", "is_active"}
    values = metadata or {}
    if not values.keys() <= allowed:
        raise ValueError("Audit metadata is not allowlisted")
    return AuditEvent.objects.create(
        actor_id=actor_id, action=action, object_id=object_id, metadata=values
    )
