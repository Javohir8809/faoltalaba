# HEMIS integration foundation

## Goal
PHASE 3: HEMIS-owned academic references and profiles synchronize through Celery,
with restartable state and a protected local status API. Existing APIs work offline.

## Non-goals
No guessed HEMIS endpoints, production connections, credential provisioning, React
screens, schedule persistence, or Phase 4 activity work.

## Existing code inspected
AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md, .agent/PLANS.md,
WORK_LOG.md; accounts models/managers/policies/views; organizations, students,
staff and audit models/services; settings, Celery, error/logging, tests and Compose.

## Assumptions
- Real HEMIS contract is unavailable. Normalized adapter records are our internal
  contract, not a claim about HEMIS wire format. Live adapter remains unconfigured.
- Mock uses fictional fixture data and is permitted only in local/test settings.
- External student and employee IDs may overlap: ExternalIdentity uses explicit
  `student:<id>` / `staff:<id>` namespaces; profiles retain the exact raw ID.
  Existing unnamespaced mappings are not guessed or automatically reassigned.
- Imports never grant roles or modify local password, username, or is_active.
  New imported accounts have random UUID usernames and unusable passwords.
- Explicit tombstones mark source records inactive; absence from a page does not
  imply deletion. Relationships/history stay intact; no hard deletes.

## Data model
Nullable unique raw hemis_id and hemis_active on academic entities; Group, Subject;
profile academic name/group/source fields. SyncState per resource holds cursor,
status, last attempt/success, safe error code and count. UUID internal keys.
Additive migrations only. One PostgreSQL advisory lock serializes all resources; page
changes, cursor advancement and immutable audit entries share a transaction.

## API contract
GET /api/v1/admin/integrations/hemis/sync-status/ — paginated local SyncState.
JWT required; SUPERADMIN only. No raw source payloads or cursor values returned.
Queue jobs through `manage.py sync_hemis`; it never performs a full sync in HTTP.

## Permissions
Global SUPERADMIN may inspect status. No new identity or role administration API.
Imports run as system actor, audit each page. Workers cannot confer role grants.

## UI/mobile impact
Admin status API foundation only; React/mobile UI deferred to their phases.

## External integration impact
Typed page/schedule adapter interfaces; synthetic mock; bounded JSON GET transport
with timeout, safe retries, no redirects and size limit. Real wire adapter deferred
until endpoint, auth, pagination and identity semantics are supplied.

## Security/privacy
No secrets/raw payloads/exceptions logged. Bounded pages, cursor and record fields;
invalid records fail whole page without clearing existing values. Imports cannot
adopt existing users by username/phone. Production mock forbidden. No raw ID in
generic error output. Audit must succeed or page rolls back.

## Implementation steps
- [x] Inspect repository and create plan; retain previous documentation changes.
- [x] Add academic models/migrations and typed adapter/mock/GET transport.
- [x] Add transactional import, lock/cursor/failure state and Celery jobs.
- [x] Add status API, worker configuration and operator documentation.
- [x] Test business rules, failures, permissions and background workflow.
- [x] Validate migrations, lint/format, OpenAPI, runtime; update TODO/work log.

## Test plan
Real PostgreSQL: repeated sync and stable UUIDs, dependency order, preserved local
fields, changed/tombstoned records, page rollback/cursor resume, concurrent lock,
audit failure rollback. Adapter/transport tests: timeout, bounded retry, invalid JSON,
redirect and origin controls, fixture isolation. API: anonymous/student/admin,
pagination and zero network access. Celery task workflow tested with worker/Redis
where available; all prior auth tests must remain passing.

## Rollback
Stop workers first. Revert code and leave additive columns/tables intact; no data
deletion required. Reverse migrations only on disposable databases or after backup
and review, as imported rows/profile associations would be lost. Audit retained.

## Completion notes
Local validation complete: 93 backend + 9 foundation tests passed (102 total).
Ruff lint/format, compileall, pip check, additive migrations/no drift, OpenAPI
validation and sample production deployment checks passed. Real Redis/Celery test
and Docker worker task registration verified; HTTP health/ready 200, status 401
without JWT. CI now checks migration/schema drift too. Commit fc08c94 push CI
39050400440 and PR CI 39050420433 both completed successfully (confirmed 2026-10-17).
No authenticated HEMIS data sync.
The user-provided public /rest URL returned HTTP 404. URL/token configuration was
added on request; local URL was stored, token remains private/unset.

Design refinements: widened ExternalIdentity.external_id from 128 to 160 so
namespaced mappings preserve all 128 raw ID characters. A shared integration lock
also prevents two resources mutating related entities concurrently. Legacy raw-ID
mappings fail for explicit reconciliation instead of silently creating duplicates.
