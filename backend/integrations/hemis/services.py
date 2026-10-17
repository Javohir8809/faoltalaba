"""Restartable page imports. No external call is made inside a DB transaction."""

import logging

from audit.services import record_event
from django.db import connection, transaction
from django.utils import timezone

from .adapters import HemisAdapter, HemisError, get_adapter
from .importers import apply_record
from .models import Resource, SyncState

logger = logging.getLogger(__name__)
LOCK_ID = 614004
MAX_PAGES = 1000


def sync_resource(resource: str, *, adapter: HemisAdapter | None = None) -> SyncState:
    resource = Resource(resource)
    # One shared lock protects references/profile consistency across resources too.
    # Session lock is outside transactions so network waits do not hold row locks.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_ID])
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise HemisError("SYNC_BUSY")
    try:
        return _sync(resource, adapter=adapter)
    except HemisError:
        raise
    except Exception:
        raise HemisError("SYNC_FAILED") from None
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_ID])


def _sync(resource: Resource, *, adapter: HemisAdapter | None) -> SyncState:
    with transaction.atomic():
        state, _ = SyncState.objects.get_or_create(
            resource=resource,
            defaults={"status": SyncState.Status.RUNNING, "last_attempt_at": timezone.now()},
        )
        if not state.cursor:
            state.records_processed = 0
        state.status = SyncState.Status.RUNNING
        state.last_attempt_at = timezone.now()
        state.error_code = ""
        state.save()
        record_event(actor_id=None, action="hemis_sync_started", object_id=state.id)
    try:
        adapter = adapter or get_adapter()
        seen = {state.cursor}
        for _ in range(MAX_PAGES):
            page = adapter.fetch_page(resource, state.cursor)
            page.validate()
            if page.next_cursor and page.next_cursor in seen:
                raise HemisError("INVALID_PAGE")
            seen.add(page.next_cursor)
            with transaction.atomic():
                for row in page.records:
                    apply_record(resource, row)
                state.cursor = page.next_cursor
                state.records_processed += len(page.records)
                if not state.cursor:
                    state.status = SyncState.Status.SUCCEEDED
                    state.last_success_at = timezone.now()
                state.save()
                record_event(
                    actor_id=None,
                    action="hemis_page_imported",
                    object_id=state.id,
                    metadata={"resource": resource.value, "count": len(page.records)},
                )
            if not state.cursor:
                return state
        raise HemisError("INVALID_PAGE")
    except Exception as exc:
        code = exc.code if isinstance(exc, HemisError) else "SYNC_FAILED"
        # Re-read committed state: a failed transaction may have advanced Python
        # fields, but its DB cursor and imported records were rolled back together.
        with transaction.atomic():
            state.refresh_from_db()
            state.status = SyncState.Status.FAILED
            state.error_code = code
            state.save(update_fields=["status", "error_code"])
            record_event(actor_id=None, action="hemis_sync_failed", object_id=state.id)
        logger.warning(
            "HEMIS sync failed",
            extra={"event": "hemis_sync_failed", "error_code": code, "resource": resource.value},
        )
        raise HemisError(code) from None
