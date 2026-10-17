# Clubs — PHASE 5

## Goal
Students discover/join clubs; leaders review applications, manage sessions and see
club aggregates. Approved members are eligible for a future attendance engine.
All domain writes are authorized, serialized and audited.

## Non-goals
No attendance records/scanners/NFC/QR, UI/mobile, notifications or Phase 6 work.
No live HEMIS calls or Smart Campus write access.

## Existing code inspected
AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md, .agent/PLANS.md, WORK_LOG.md;
Activity models/services/API/policies and tests; accounts grant/revoke; student
profiles and audit/settings. PHASE 4 local 142 tests passed; remote CI was still
running at initial inspection and will be checked separately.

## Assumptions
- Club is a one-to-one specialization of Activity(type=CLUB), sharing its UUID.
  Create through club API atomically; common content/review/publication reuse the
  Activity API. Bare legacy CLUB activities are not silently converted.
- Activity registration_policy is authoritative: OPEN -> ACTIVE membership,
  APPROVAL -> PENDING, NONE -> join disabled. No duplicate policy column.
- Join permitted while a published operational club has not ended, including an
  ongoing term. Student role/profile/audience checks always apply, even for admins.
  Capacity counts ACTIVE memberships; pending applications do not reserve seats.
- Unique Participant(activity,student) is canonical. ClubMembership specializes it
  without duplicate student/activity fields. ACTIVE/PENDING map to corresponding
  Participant state; REJECTED/LEFT map to CANCELLED. Retrying join is idempotent.
  LEFT can rejoin subject to current policy/capacity; rejected requests cannot
  automatically reapply. Leave remains possible when a club becomes hidden.
- Matching activity managers may review members and operate sessions. Institutional
  reviewers may delegate/revoke only CLUB_LEADER in their own club; leaders cannot
  delegate themselves or publish. General access API stays SUPERADMIN-only.
- Weekly schedule: max 21 same-day slots, ISO weekday 1–7, IANA timezone (default
  Asia/Tashkent). Edits restricted to draft/rejected, consistent with Activity review.
  Session datetimes are explicit UTC instants, not automatic schedule generation.
- Sessions are PLANNED/OPEN/CLOSED/CANCELLED. Server time must lie within both
  session and club term when opening; one OPEN session per club. Close uses server
  time even after the window/club closes, so operators can finalize stale sessions.
- Dormant means operational, term started, and no opened session in 30 days (or
  creation older than 30 days when none exists). No attendance/ranking inference.

## Data model
Club(Activity one-to-one PK, timezone); ClubSchedule UUID/weekday/wall times;
ClubMembership(Participant one-to-one PK, status, reviewer/reason/timestamps);
ClubSession UUID/club/planned window/server open-close actor/time/request UUID.
DB enum/date/uniqueness constraints, partial unique OPEN session, PROTECT history.
Membership/sessions lock Activity then Club. Leader delegation serializes with the
existing access-administration advisory lock; a private grant persistence helper
is reused only after explicit authorization to avoid duplicated RBAC persistence.

## API contract
JWT /api/v1/clubs/ GET/POST; /{uuid}/ GET/PATCH timezone; standard activity API for
content, publish and archive. /schedule/ GET/PUT bounded slots; /membership/ GET/POST
own join and DELETE own leave; /members/ GET protected paginated roster;
/members/{membership_uuid}/decision/ POST {decision,reason}; /leaders/ POST {user_id}
and /leaders/{grant_uuid}/ DELETE; /sessions/ GET/POST; /sessions/{uuid}/open/ and
/close/ POST; /analytics/ GET managers only. All list endpoints paginated except
bounded weekly slots. Session create requires idempotency_key; conflicting reuse
is 409. Unknown/unrelated objects 404, denied actions 403, validation 400.

## Permissions
No anonymous actions. Institutional scope required for club creation/delegation;
scoped activity managers can review their own club, edit draft schedule and operate
sessions. Student can inspect/leave their own membership even after visibility
changes, never roster/other membership/management analytics. Public club discovery
uses existing audience rules; roster exposes only required member identity to its
authorized managers. Eligibility helper rechecks live role/profile/membership,
operational club and OPEN server window; no client time accepted.

## UI/mobile impact
Backend endpoints and Uzbek generic errors; no new frontend in this phase.

## External integration impact
Uses local HEMIS affiliation and existing JWT/RBAC. No new network calls.

## Security/privacy
Strict bounded inputs; joins/decisions/leave update Participant and membership in
one transaction with immutable audit. No hard-delete API. Student detail omits
roster/private profiles; aggregates and leader UUIDs only. Rejection requires a
reason, stored under roster authorization and excluded from generic logs/audit.
Session opening ignores client final timestamps and uses server authority.

## Implementation steps
- [x] Inspect contracts/current code, create branch and plan.
- [x] Add specialized models, constraints/migration and role persistence reuse.
- [x] Implement atomic club, schedule, leader, membership and session services.
- [x] Add scoped paginated APIs, annotations/analytics/dormancy and eligibility.
- [x] Test JWT manual/automatic join, approval/session/eligibility and isolation.
- [x] Test races/idempotency/audit rollback; full lint/tests/schema/runtime checks.
- [x] Update TODO/docs/work log; prepare draft PR and record exact CI status.

## Test plan
Real PostgreSQL: capacity race, approval after filled capacity, one membership on
retry, left/rejected behavior, Participant consistency, leader delegation isolation
and revoke, window/one-open session and replay conflicts. API JWT E2E from create
through published club, join, leader approval, session open, eligibility and close.
Cross-faculty/club/student roster isolation, attendance denial for inactive source
or membership, audit failure rollback, bounded schedule validation, dormancy and
aggregate correctness/query count. Full existing backend/foundation suite.

## Rollback
Stop writers/workers; revert code while retaining new tables/history. Revoke scoped
leader grants through audited services before unapplying on a disposable/backup
database. Participant/audit records must not be deleted as cleanup. No destructive
schema change or production migration intended.

## Completion notes
Initial 27 Clubs tests passed after fixing nullable planned-session field validation;
added three race/create-audit cases for a total of 30. Two additive migrations
applied. OpenAPI status enums explicitly named to preserve previous schemas.
Final full backend suite: 163 passed (30 Clubs tests), foundation: 9 passed;
172 total. Ruff lint/format, compileall, pip check, migration drift, OpenAPI and
sample production deployment checks passed. Docker health/readiness 200, clubs
401 without JWT; Docker IANA timezone check passed, backend/worker rebuilt.
Prior API paths/components preserved. Staged secret scan passed.
Draft PR is prepared for push; remote CI has not yet been triggered for this branch. PHASE 4 CI runs 39051891471 and
39051913981 both completed/success. TODO marked after passing local validation. Phase 6 remains unstarted.
