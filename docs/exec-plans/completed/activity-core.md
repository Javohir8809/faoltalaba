# Activity core — PHASE 4

## Goal
Authorized staff create, review and publish generic activities. Students discover
only previously published, eligible activities. Changes are audited and lifecycle
transitions run on the backend. Domain-specific clubs/events follow in later phases.

## Non-goals
No club membership, registration/attendance/session API, scoring, React/Flutter UI,
live HEMIS integration, or Smart Campus write paths. Participant is schema only.

## Existing code inspected
AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md, WORK_LOG.md, .agent/PLANS.md;
accounts models/policies/services/serializers, organizations and profiles, audit,
settings/URLs/OpenAPI, HEMIS plan and existing tests. PHASE 3 CI runs 39050400440
and 39050420433 both succeeded before starting this milestone.

## Assumptions
- Authenticated institutional visibility only; no anonymous activity catalog.
- Organizer is creator UUID, separate from optional owning faculty/department;
  ownership/type are immutable after creation to prevent scope escalation.
- Content/policies can change only in DRAFT/REJECTED; publication requires a review
  transition, dates, venue and end time in the future. No silent auto-publication.
- Global SUPERADMIN/YOUTH_ADMIN and matching faculty/department responsible can
  create/review. Activity-scoped leaders may edit their draft and submit, not approve.
- Existing access management remains SUPERADMIN-only. ActivityRole links one
  authoritative RoleGrant; no duplicated user/role fields or independent privileges.
  Existing accounts role APIs gain validation for real activity UUIDs and link/unlink
  ActivityRole transactionally. CLUB_LEADER is valid only for CLUB activities.
- Audience ALL_STUDENTS/FACULTY/DEPARTMENT/GROUP is separate from organizer scope.
  Eligibility requires STUDENT role and active source profile/references. Missing or
  inactive HEMIS data denies student discovery; admin scope stays locally controlled.
- DELETE archives only draft/rejected/completed/cancelled activities, preserving
  history. Published/active items require explicit lifecycle transitions first.

## Data model
Activity UUID, type/state enums, creator, owner scope, title/description, timing,
venue/capacity, audience reference, visibility and explicit registration/attendance/
evidence/result policies. DB constraints cover dates, positive capacity, enum values,
audience shape, owner shape; cross-table affiliation validated by service/model.
ActivityRole(activity, unique grant); Participant UUID with unique activity/student,
state enum and timestamps; PROTECT on history links. Additive initial migration,
indexes for state/start and owner/student/activity queries.

## API contract
JWT /api/v1/activities/: GET paginated/filtered/searchable; POST draft.
/{uuid}/: GET, PUT/PATCH draft content, DELETE archive.
/{uuid}/transitions/: POST {state}; invalid lifecycle -> 400 coded error.
/{uuid}/roles/: GET paginated assignments for managers only; writes through the
existing /admin/users/{uuid}/roles/ and revoke endpoints (SUPERADMIN).
State, UUID, creator, owner/type updates and arbitrary input fields are rejected.
No join/participant writes in this phase.

## Permissions
Deny by default. Staff see own managed objects, students eligible published objects.
Unrelated object detail gives 404; read-only student mutations give 403. Backend
services recheck live authorization under activity row locks. Existing RBAC grants
remain the authority; no Django staff flag bypass. Managers-only visibility hides
objects from student discovery. Scoped assignments never confer publication power.

## UI/mobile impact
API foundation only; Uzbek errors and loading/empty pagination contract for clients.

## External integration impact
Only local HEMIS-synced affiliation is used. No external/broker calls in catalog.
Smart Campus receives no new write endpoints or credentials.

## Security/privacy
No participant or private profile data in discovery. Bound strings, JSON shape and
relations; no free-form business-rule JSON. Audit create/update/transition/archive
without title/body snapshots. Transactions roll back on audit failure. Terminal
states cannot be reopened. No hard-delete API.

## Implementation steps
- [x] Inspect requirements/code; record PHASE 3 CI success and create plan.
- [x] Add Activity/ActivityRole/Participant models, constraints and migration.
- [x] Centralize scope/eligibility and transactional lifecycle/content services.
- [x] Add strict CRUD/filter/search/role API; bind accounts activity role grants.
- [x] Test scope isolation, discovery, lifecycle, validation, constraints and audit.
- [x] Validate full suite/lint/migrations/OpenAPI/runtime; update docs/TODO/log.

## Test plan
Creation/publication/discovery end-to-end via JWT; faculty/department and activity
scope separation; students/unrelated/anonymous/flags deny; audience profile changes
take effect; lifecycle matrix and time gates; invalid fields/affiliations/dates;
duplicate participants and invalid DB enums; transaction rollback when audit fails;
real activity role grant/revoke with immediate access changes; list query count
bounded independently of number of assignments. Existing tests remain passing.

## Rollback
Stop writers, revert code, retain additive tables and audit. Reverse migration only
on disposable data or after backup: activity/participant/assignment data would be
lost. Never remove audit rows. Before removing app, revoke activity grants through
the audited access service; do not leave orphan scope UUIDs in active deployments.

## Completion notes
36 initial activity tests passed after correcting global-manager query composition
and UUID test comparison; four further lifecycle/audit tests added. Two additive
migrations applied; no migration drift. OpenAPI validates and all prior paths/schema
components compare unchanged against PHASE 3. Docker health/readiness 200, activities
401 without JWT; deployment check zero issues. Final full backend suite:
133 passed (40 Activity tests), plus 9 foundation tests: 142 total.
Ruff check/format, compileall, pip check, migration drift and OpenAPI validation
passed. Existing API paths/schema components remain unchanged. Staged secret
scan passed. Remote CI pending after push.
No Phase 5 implementation and no production deployment.
