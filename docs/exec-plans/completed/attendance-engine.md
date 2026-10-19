# Attendance engine — PHASE 6

## Goal
Authorized operators record NFC/QR/manual attendance during an open club session,
duplicates return the original record, and reasoned corrections produce immutable
history. Students see their own activity history; managers see scoped totals.

## Non-goals
No physical card assumptions, NFC sector/key storage, Flutter hardware/QR imaging,
event sessions, UI, retrospective/backdated attendance creation or Smart Campus API.

## Existing code inspected
AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md, WORK_LOG.md and .agent/PLANS.md;
ClubSession/lock/membership/eligibility, Activity RBAC, auth throttle, error contract,
audit immutability migrations/test teardown, env generation and current API schemas.
PHASE 5 CI was still running at initial inspection; do not claim success until verified.

## Assumptions
- Current session adapter targets ClubSession UUIDs. Activity is derived through
  the session; future event session adapters can extend the same policy boundary.
- Only activity managers scan/manual-check-in/correct. Students do not self-attest.
  All methods require an active server window and current eligible ACTIVE membership.
- Static NFC/QR/barcode identifiers are lookup tokens, not authentication. Operator
  JWT/scope, session and eligibility are authoritative. Opaque exact printable token
  adapters do not guess UID/MIFARE formats; hardware discovery stays UNKNOWN unless
  recorded. No physical reader/card was available to test in this milestone.
- SUPERADMIN enrolls/revokes card mappings. Raw tokens never persist or appear in
  responses/logs; a separate random environment HMAC key derives purpose-bound
  NFC/QR digests. Revoked tokens cannot be silently rebound/reactivated.
- Devices are operator-owned installations with bounded metadata; optional on scan
  when identifier is unavailable. Ownership/active state checked if supplied;
  hardware metadata is descriptive, not proof of a genuine device.
- Duplicate check-ins are unique(session,student), return original method/time/
  operator/note/status. Closed/out-of-window attempts reject even duplicate retries.
  Re-scanning a voided record does not restore it.
- Manual initial check-in and all corrections require a reason. Corrections may
  void/restore or change a note after session closure; original check-in time,
  method, student, operator and device never change. No late attendance additions.
- Corrections use expected_version plus idempotency UUID; conflicting reuse/stale
  version -> 409. Replays return current record without applying the old edit again.

## Data model
AttendanceRecord UUID/FK session/student/device/operator, server checked_in_at,
method NFC/QR/MANUAL, status PRESENT/VOIDED, note, version; unique session/student.
AttendanceDevice UUID/owner/installation UUID/platform/support flags/active/last_seen.
StudentCardMapping UUID/student/kind/HMAC digest/discovery metadata/enrolled and
revoked actor/time/reason; unique kind/digest including revoked records.
AttendanceChange UUID/record/version/actor/reason/old-new state+note/request UUID
and request digest, server timestamp. Append-only SQL guards include TRUNCATE.
Record SQL guard protects original fields and requires a matching next-version
change entry for any correction. Additive migrations and query indexes only.

## API contract
JWT /api/v1/attendance/devices/ GET/POST and /{uuid}/ PATCH owned metadata/active.
/card-mappings/ GET/POST and /{uuid}/revoke/ POST {reason}, SUPERADMIN only.
/sessions/{uuid}/check-in/ POST method-specific token or student_id/manual reason,
optional device_id/note; response 200 for original or duplicate.
/sessions/{uuid}/records/ and /stats/ GET scoped/paginated or aggregates.
/records/{uuid}/ GET; /corrections/ POST; /changes/ GET immutable paginated history.
GET /api/v1/students/me/activity-history/ paginated own records, no internal notes/
device/token/other student identities. Strict inputs reject client final timestamps.

## Permissions
Explicit manager role plus activity scope for session/record endpoints; unrelated
objects hidden with 404. Only SUPERADMIN enrolls/revokes card bindings. Operator
device list/edit is owner-scoped. Students may only read their own history.
Manual correction privilege is the same explicit activity-management scope; every
change is recorded, including reason, before/after state and server actor/time.

## UI/mobile impact
JSON/OpenAPI foundation, Uzbek errors. Hardware adapters consume safe identifiers
from future maintained client plugins; hardware failures are not simulated as scans.

## External integration impact
PostgreSQL + Redis only; current local HEMIS role/profile eligibility is reused.
No live identity sync or external writes.

## Security/privacy
Token key separate from JWT with domain separation; token/rate-limit digests have
separate derivation purposes. No raw tokens/card sectors/keys in DB/logs/Redis keys.
Rate limits per actor/IP fail closed with 503 on Redis outage; test-only disable.
Same Activity->Club->Session lock order as close/leave; then card/profile/record,
preventing check-in races with session close or membership leave. Source eligibility
is rechecked in the write transaction. Audit failure rolls back every domain write.
Change reasons/notes visible only to scoped operators; student history is minimal.

## Implementation steps
- [x] Inspect contracts/current code, create branch and plan.
- [x] Add models, additive migrations, immutable history and record guards.
- [x] Add purpose-bound token adapters, enrollment/devices and locked check-in.
- [x] Add versioned idempotent corrections, scoped API/history/stats and Redis limit.
- [x] Test NFC/QR/manual flows, privacy, races, SQL guards and audit rollback.
- [x] Run full tests/lint/migration/schema/runtime checks, update TODO/docs/log.
- [ ] Prepare draft PR and report exact CI state; no merge/production deployment.

## Test plan
Real PostgreSQL + Redis. JWT operator flow resolves mapped token into active member,
server timestamp, duplicate stable UUID, student history and totals. Both methods,
unknown/revoked tokens, owner/inactive devices, manual reason/unknown input rejection,
scope/role isolation, pending/left/inactive source and closed/expired windows.
Concurrent duplicate scans/close/leave; correction version/replay conflicts;
immutable audit SQL UPDATE/DELETE/TRUNCATE guards, record mutation guard; audit
rollback; rate limit/outage and hashed Redis keys. Existing suites must remain green.

## Rollback
Stop writers/workers; keep additive tables and immutable history. Reverse guard/
schema migrations only after backup/review on disposable data; never delete audit
rows for cleanup. Preserve HMAC key securely: changing it invalidates lookups and
requires explicit re-enrollment; do not rotate it silently or derive it from JWT.

## Completion notes
Completed locally on 2026-10-19: full backend 211 passed (48 new attendance cases),
foundation 9 passed; total 220. Full run reported 160399.12 s wall-clock across
the date boundary. Ruff check/format, compileall, pip check, migrations/no drift,
OpenAPI validate/fail-on-warn and sample production deploy check passed. Previous
OpenAPI paths/components preserved. Docker backend/worker rebuilt; health/ready
200, protected attendance/history 401 anonymously; independent key verified inside
the backend without exposing its value. See WORK_LOG.md for commands and fixes.
Physical NFC/card format remains undiscovered; API fixtures only.
