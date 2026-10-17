# HEMIS integration foundation

PHASE 3 imports HEMIS-owned faculties, departments, groups, subjects, students and
employees through background jobs. Public/student requests only read PostgreSQL;
an unavailable HEMIS does not interrupt login or existing activity APIs.

## Configuration

Local `.env` is ignored by Git. These keys are also listed without credentials in
`.env.example`:

```dotenv
HEMIS_ADAPTER=disabled
HEMIS_BASE_URL=https://student.samdukf.uz/rest
HEMIS_API_TOKEN=
HEMIS_HTTP_TIMEOUT=5
HEMIS_HTTP_ATTEMPTS=3
```

Enter the token locally, never in chat, a command argument, commit or screenshot.
The provided `/rest` URL returned HTTP 404 during unauthenticated discovery on
2026-10-17. URL/token configuration alone does not enable live synchronization.
The institution must provide API documentation or a sanitized response sample:
endpoints, authentication scheme, pagination/cursor semantics, student/employee ID
namespaces, inactive/deleted records and schedule timezone. `get_adapter()` fails
closed until a real adapter using that confirmed contract is implemented.

`JsonGetTransport.from_settings()` consumes these settings for that future adapter.
It requires HTTPS, fixed origin/base prefix and a token, refuses redirects and path
escapes, limits responses to 2 MiB, uses a 5-second socket timeout (maximum 15), and
makes at most 3 GET attempts. Only connection/timeouts and 429/500/502/503/504 retry,
with bounded backoff. 401/403, invalid JSON and redirects fail immediately. It does
not invent endpoint paths or claim our normalized JSON is the HEMIS wire schema.

## Local mock workflow

Use only a local disposable/development database. The fictional fixture contains
one faculty, department, group, subject, student and employee. Importing it creates
two accounts with unusable passwords and no role grants. No demo login is enabled.

```sh
python tools/dev.py up
python backend/manage.py migrate --noinput
```

Set `HEMIS_ADAPTER=mock` in local `.env`, then:

```sh
python tools/dev.py up-worker
python backend/manage.py sync_hemis
# Or one resource after its references already exist:
python backend/manage.py sync_hemis --resource students
```

The command only queues work; success means queued, not synchronized. Inspect the
status endpoint afterwards. Restart/recreate the worker after changing `.env`.
Mock is explicitly forbidden in staging/production even if selected in environment.
Leave `HEMIS_ADAPTER=disabled` when not using synthetic data. No automatic periodic
schedule is installed; cadence needs the real institution's limits/data contract.

For a host worker on Windows (development only):

```sh
python -m celery -A config.celery worker --pool=solo --loglevel=WARNING
```

Run from `backend/` with `DJANGO_SETTINGS_MODULE=config.settings.local`. Linux
Compose workers use prefork, two processes and task soft/hard limits of 900/960s;
solo cannot enforce those time limits. Redis visibility timeout is 3600s and tasks
acknowledge after execution, allowing idempotent replay after worker loss.

## Internal adapter contract

`HemisAdapter.fetch_page(resource, cursor)` returns immutable `Page(records,
next_cursor)`. Records use `id` (exact nonempty raw string, max 128), `name` (max
200), and related `faculty_id` / optional `department_id` / optional `group_id`.
Staff records in this foundation require a faculty; non-faculty employee semantics
must be confirmed before a live adapter is enabled. Pages have at most 500 records,
cursors at most 512 characters. An empty next cursor ends a scan. Repeated cursors
and more than 1000 pages per job fail safely. The future wire adapter must treat
all remote payloads as untrusted and normalize/validate them before returning pages.

`schedule(starts_at, ends_at)` is a typed interface for timezone-aware lesson
occurrences. The mock returns no lessons. Actual timetable parsing/persistence and
lesson feedback are outside this milestone.

## Identity and ownership

Academic entities/profiles retain unique raw `hemis_id`; UUID remains their internal
key. `ExternalIdentity` uses `student:<raw>` and `staff:<raw>` because numeric IDs may
overlap across source resources. Its max length increased additively to 160.
Legacy unnamespaced identity mappings cause `IDENTITY_CONFLICT`; operators must
explicitly reconcile them rather than guessing who an imported record belongs to.

Imports never change usernames, passwords, API roles, sessions or local `is_active`.
No username/phone/passport matching is attempted. Academic full names and affiliation
are separate profile fields. Invalid required fields roll back the whole page;
missing/null optional affiliations preserve prior values. A contradictory faculty/
department/group mapping fails rather than clearing existing data.

`{"id": "source-id", "deleted": true}` is an explicit tombstone. It marks
`hemis_active=False` on an existing source entity/profile without deleting history
or changing local account access. Missing records are never implicitly deleted.
An active record restores the source flag on a later import. HEMIS source status is
separate from local login/RBAC; any eligibility rule based on it belongs to its
future domain service. No automatic local role revocation is performed.

## Transactions, recovery and observability

A shared PostgreSQL session advisory lock rejects concurrent imports with
`SYNC_BUSY`, including different resources. Use a direct connection or session
pooling, not PgBouncer transaction pooling. Each page commits imported changes,
cursor, processed count and append-only audit entry together. External reads run
outside row-locking transactions. Reference resources precede dependants in `all`;
the job stops at the first failure. Multi-resource sync is eventually consistent,
not a single global snapshot. Requeue after remediation to resume its last committed
page; completed resources safely reimport. A restart after a finished scan starts
from the beginning, using unique source IDs to preserve UUIDs.

`SyncState` records attempt/success time, RUNNING/SUCCEEDED/FAILED, cursor, safe error
code and committed count. Last success survives failures. A hard-killed worker may
leave RUNNING until redelivery/requeue; PostgreSQL releases its connection lock.
`NOT_CONFIGURED`, `INVALID_RECORD`, `INVALID_PAGE`, `MISSING_REFERENCE`,
`IDENTITY_CONFLICT`, `HTTP_ERROR`, `INVALID_RESPONSE`, `UNAVAILABLE`, `SYNC_BUSY`,
`SYNC_FAILED` contain no upstream exception text or record data. Fix the adapter or
source issue and requeue. Audit failure prevents page commit.

Structured logs include only a fixed error code and resource; raw source bodies,
IDs, names and credentials are excluded. Audit actions record start/page/failure,
state UUID and per-page resource/count. Existing audit DB immutability remains.

## Status API

`GET /api/v1/admin/integrations/hemis/sync-status/` requires JWT and an active global
SUPERADMIN grant. Django staff flags and other roles do not authorize it. Results
are paginated, with id, resource, status, last_attempt_at, last_success_at,
error_code and records_processed. Cursors and source payloads are not exposed.
The endpoint reads local state and makes no HEMIS or broker call. Before the first
attempt it returns an empty list. React/mobile screens are deferred.

## Validation and rollback

```sh
python -m pytest -c backend/pytest.ini backend/tests
python tools/dev.py test
python -m ruff check backend tools tests
python -m ruff format --check backend tools tests
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py spectacular --file docs/api/openapi.yaml --validate --fail-on-warn
```

Tests require PostgreSQL and Redis. One integration test runs a real solo Celery
worker against Redis using an isolated queue and the disposable test database.
Stop workers before rollback. Revert code while keeping additive schema/data;
reverse migrations only after backup/review because profile links/imports may be
lost. Never delete audit history to clean up imports.
