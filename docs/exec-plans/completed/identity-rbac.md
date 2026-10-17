# PHASE 2 — Identity, users and RBAC

## Goal
UUID users, student/staff profiles, external identity mapping, JWT login/refresh/logout,
explicit scoped RBAC and immutable audit for privileged operations.

## Non-goals
HEMIS network sync, public signup, UI, clubs/activities and production deployment.

## Existing code inspected
Root instructions, PRODUCT_SPEC, ARCHITECTURE, TODO, PLANS; Django settings,
health, error handler, routes, tests, requirements, Compose and CI.

## Assumptions
- Phase 0/1 branch is not merged. New feat/identity-rbac branch is stacked on it.
- Login uses a local username/password until HEMIS identity contract is supplied.
- Organization UUID reference models are needed now for real cross-faculty tests;
  their imported fields remain HEMIS-owned. No academic data edit API is provided.
- Use PyJWT with explicit HS256/issuer/audience/required claims and database-backed
  refresh sessions. JWT carries UUID identity/session only, never role or profile-data snapshots.
- Access 5 minutes, refresh session maximum 7 days. Refresh rotates jti/hash under
  a row lock. Replay revokes that session (including access tokens), forcing login.
- Privileged role changes lock the acting user's row; cannot remove the last active
  global SUPERADMIN. Django staff/superuser flags never bypass explicit API RBAC.

## Data model
accounts.User UUID in 0001; UUID ExternalIdentity, RoleGrant, RefreshSession.
organizations.Faculty/Department UUID; students.StudentProfile and staff.StaffProfile
UUID with user and academic scope references. audit.AuditEvent actor/object UUID
snapshots, minimal allowlisted metadata. PostgreSQL triggers prohibit audit
UPDATE/DELETE/TRUNCATE and user UUID mutation. No raw refresh token is stored.

## API contract
POST /api/v1/auth/login/ {username,password}; refresh/logout {refresh}.
GET /api/v1/auth/me/; GET /api/v1/admin/users/ and /{uuid}/.
PATCH /api/v1/admin/users/{uuid}/status/ {is_active}.
GET/POST /api/v1/admin/users/{uuid}/roles/; DELETE .../roles/{grant_uuid}/.
Errors use existing {error:{code,message,details}}; lists paginated.

## Permissions
- All roles: authenticated own /me only by default.
- SUPERADMIN global: user read, role grant/revoke, activation, audit-backed operations.
- YOUTH_ADMIN global: user read institution-wide; cannot grant roles.
- FACULTY_YOUTH_RESPONSIBLE: user read only matching Student/StaffProfile faculty.
- DEPARTMENT_RESPONSIBLE: user read only matching department.
- CLUB_LEADER / ACTIVITY_RESPONSIBLE: activity-scoped permission helper only;
  scope creation API pending real Activity model in PHASE 4, deny creation now.
- SCIENCE/SPORTS/INTERNATIONAL/LIBRARY/ANALYTICS roles: future domain capabilities;
  no institution-wide user read or access administration.
- TEACHER/STUDENT: no admin user endpoint. Unmatched roles/actions/scopes deny.

## UI/mobile impact
Bearer JSON API only; no cookie token transport and no UI this phase.

## External integration impact
HEMIS IDs stored separately under unique source/external_id mapping. No network calls.

## Security/privacy
Dedicated random JWT signing key; no token/password log or audit metadata.
Login/refresh throttled via Redis; Redis outage fails authentication endpoints closed
with generic 503. Login errors do not reveal account existence. PostgreSQL transactions
and constraints; audit immutable at DB level. No hard-delete user/API.

## Implementation steps
- [x] Models, managers, constraints and initial migrations.
- [x] Explicit role policy and audited status/grant/revoke services.
- [x] JWT sessions, rotation/replay/revocation, authentication, throttling.
- [x] Serializers/routes/OpenAPI and provisioning CLI.
- [x] Unit/API/privacy/concurrency/integration tests.
- [x] Migrate, lint, schema/deploy check, audit and CI; update WORK_LOG/TODO/CHANGELOG.

## Test plan
Real PostgreSQL/Redis: login→me→refresh→logout; malformed/expired/wrong-type JWT;
refresh replay/concurrent rotation; inactive/deactivated user; last-superadmin guard;
role/scope matrix, cross-faculty/department filtering and role grant escalation;
immutable audit and user UUID at SQL layer; audit transaction rollback.

## Rollback
Additive schema only; preserve existing contenttypes migrations. Stop application
before reversing accounts/profile/org migrations. Reverse immutability triggers only
through the documented migration operation; never delete audit records for rollback.
Production rollback requires backup and a data-preservation migration, not blanket unapply.

## Completion notes
55 backend tests and 9 foundation tests verified through local runs and complete
remote CI; real PostgreSQL/Redis migrations, refresh/last-admin concurrency,
scope isolation, audit SQL guards and rollback validated.
Ruff/schema/deployment checks passed; pinned Python dependencies audit clean.
Docker API health/ready 200 and unauthenticated me/login 401/no-store verified.
Self-review added a domain-separated limiter key and its regression test.
Latest commit 4f717d4 push run 38627915792 and PR run 38627926034 both succeeded.
Draft PR #2 is stacked on #1; no merge/production deployment performed.
