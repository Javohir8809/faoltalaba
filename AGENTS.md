# AGENTS.md — Faol Talaba

## 1. Project identity

Project name: `Faol Talaba`

Purpose: Kattaqo'rg'on davlat pedagogika institutida talabalar faolligini boshqarish, ishtirokni ishonchli qayd etish, yutuqlar va faoliyat tarixini yig'ish, so'rovnomalarni o'tkazish va Smart Campus uchun read-only activity API taqdim etish.

This file is a mandatory engineering contract for Codex. Do not silently deviate from it.

## 2. Fixed technology stack

Do not replace these technologies unless the user explicitly requests a stack change.

### Backend
- Python 3.13+
- Django 6.x
- Django REST Framework
- PostgreSQL 18+
- Redis
- Celery
- django-filter
- drf-spectacular for OpenAPI
- PyJWT / SimpleJWT-style JWT auth implementation suitable for DRF
- MinIO/S3-compatible object storage for uploads
- pytest + pytest-django
- ruff
- mypy where practical

### Admin web (`yi.katdpi.uz`)
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui where suitable
- TanStack Query
- React Hook Form
- Zod
- Vitest
- Playwright for critical E2E paths

### Mobile (`Faol Talaba`)
- Flutter
- Dart
- Riverpod for state management
- go_router
- Dio
- Freezed/json_serializable when helpful
- Firebase Cloud Messaging
- Native NFC support through a maintained Flutter plugin
- QR/barcode scanning through a maintained camera scanning plugin
- flutter_secure_storage
- local cache via Isar or Drift; prefer Drift when relational offline data is needed

### Infrastructure
- Docker
- Docker Compose for dev/staging
- Nginx
- GitHub Actions or GitLab CI; use the one already present in repository
- Sentry
- Prometheus/Grafana may be added after MVP
- HTTPS required in non-local environments

## 3. Architecture rules

1. Start as a **modular monolith**, not microservices.
2. Backend business logic lives in Django domain modules.
3. React and Flutter are API clients only; business rules must not be duplicated in UI.
4. PostgreSQL is the application source of truth for Faol Talaba-owned data.
5. HEMIS remains source of truth for:
   - students
   - employees/teachers
   - faculties
   - departments
   - groups
   - subjects
   - schedules when available
6. EKT remains source of truth for library-owned activity.
7. Smart Campus is a **read-only consumer** of Faol Talaba activity APIs.
8. Smart Campus must not be used for:
   - joining clubs
   - submitting applications
   - uploading achievements
   - taking surveys
   - recording attendance
9. Do not introduce Kafka, RabbitMQ, ClickHouse, Elasticsearch, Kubernetes or microservices during MVP unless a demonstrated requirement exists.
10. Prefer boring, maintainable solutions over architectural novelty.

## 4. Core backend modules

Create domain modules with clear ownership:

- accounts
- integrations.hemis
- integrations.ekt
- integrations.smart_campus
- organizations
- students
- staff
- activities
- clubs
- events
- competitions
- volunteering
- science
- sports
- culture
- innovation
- international
- mentoring
- professional_development
- media_activity
- eco_social
- initiatives
- applications
- attendance
- achievements
- files
- surveys
- lesson_feedback
- notifications
- portfolio
- analytics
- audit

Shared abstractions must stay minimal. Do not build a giant `utils.py`.

## 5. Core domain model

The system must model a generic concept of `Activity`.

Activity types include but are not limited to:
- CLUB
- EVENT
- VOLUNTEERING
- COMPETITION
- SCIENCE
- SPORT
- CULTURE
- INNOVATION
- INTERNATIONAL
- MENTORING
- PROFESSIONAL_DEVELOPMENT
- MEDIA
- ECO_SOCIAL
- INITIATIVE
- OTHER

Every activity may have:
- title
- description
- type
- organizer
- responsible users
- target audience
- capacity
- start/end datetime
- venue
- registration rules
- attendance policy
- lifecycle state
- visibility
- evidence requirements
- result rules

Do not force all special behavior into one huge Activity table. Use an Activity base plus domain-specific models where required.

## 6. Roles and permissions

Use explicit RBAC.

Minimum roles:
- SUPERADMIN
- YOUTH_ADMIN
- FACULTY_YOUTH_RESPONSIBLE
- DEPARTMENT_RESPONSIBLE
- CLUB_LEADER
- ACTIVITY_RESPONSIBLE
- TEACHER
- STUDENT
- SCIENCE_OFFICE
- SPORTS_OFFICE
- INTERNATIONAL_OFFICE
- LIBRARY_OPERATOR
- ANALYTICS_VIEWER

Rules:
- deny by default
- permissions enforced on backend, never only in frontend
- object-level access for faculty/department/activity ownership
- all privileged changes logged in audit log

## 7. Authentication and identity

- Internal application user must have immutable UUID primary key.
- Store external identifiers such as HEMIS ID separately.
- Do not use passport number or phone number as primary key.
- JWT access + refresh token flow for mobile/web API clients.
- Refresh token rotation and revocation required.
- Admin web may use secure HttpOnly cookie-based token transport if implemented consistently.
- Secrets must never be committed.
- Use `.env.example`; actual `.env` must be ignored.

## 8. Attendance rules

Attendance is a high-value domain and must be auditable.

Supported methods:
- NFC
- QR/barcode
- MANUAL with reason and audit trail

Attendance must reference:
- activity/session
- student
- check-in timestamp
- method
- recorded_by
- device identifier when available
- status
- optional note

Rules:
- attendance only during an active session/window
- duplicate check-in blocked idempotently
- leader must have permission for the activity/session
- server time is authoritative
- do not trust client-provided final attendance time
- manual overrides require reason
- manual modifications create immutable audit entries

NFC:
- Do not assume card type.
- Build an adapter abstraction.
- During hardware discovery, record whether card is ISO 14443 / MIFARE variant / UID-readable.
- Never store sensitive card sectors or keys unless explicitly required.
- Prefer mapping a safe card identifier/token to internal student UUID.

## 9. Surveys and lesson feedback

Build a reusable Survey Engine.

Question types:
- RATING_1_5
- YES_NO
- SINGLE_CHOICE
- MULTIPLE_CHOICE
- TEXT
- SLIDER
- NPS

Survey features:
- anonymous or identified mode
- audience targeting
- start/end time
- optional one-response limit
- conditional follow-up questions
- response analytics

Lesson feedback is a specialized flow:
- derive lesson context from HEMIS schedule
- trigger after lesson end
- if attendance data is available, only eligible attendees should receive/respond
- teacher must never receive student identity in lesson-feedback analytics
- expose aggregate results only after a minimum response threshold
- configurable sampling to avoid survey fatigue

Corruption-related reporting/surveys require stricter access controls and privacy review. Do not casually mix them with standard teacher feedback tables.

## 10. Smart Campus API rules

Smart Campus integration is read-only.

Provide versioned endpoints such as:
- GET /api/v1/external/students/{id}/activity-summary/
- GET /api/v1/external/students/{id}/activity-history/
- GET /api/v1/external/students/{id}/clubs/
- GET /api/v1/external/students/{id}/achievements/
- GET /api/v1/external/students/{id}/portfolio/

Requirements:
- service-to-service authentication
- rate limiting
- versioning
- stable schemas
- no write actions
- no unnecessary private data
- API contract tests

## 11. HEMIS integration rules

- Treat HEMIS as external and unreliable.
- All requests need timeout.
- Retries only for safe/idempotent operations.
- Never block user-facing request on a slow full HEMIS sync.
- Sync through background jobs.
- Keep sync cursor/state and last_success_at.
- Keep external raw ID mapping.
- Do not overwrite local Faol Talaba-owned fields with null/invalid HEMIS values.
- Log integration failures without leaking secrets.
- Build mock fixtures for development/test.

## 12. EKT integration rules

- EKT is source of truth for library-owned activity.
- Do not duplicate full EKT functionality.
- Import only fields needed for activity/portfolio/analytics.
- Prefer event/sync strategy over live blocking calls where practical.
- Keep provenance: every imported record must indicate source=`EKT`.

## 13. Files and evidence

All evidence files:
- go to MinIO/S3-compatible storage
- have MIME/type/size validation
- have server-generated object keys
- never trust user filename as path
- optional malware scanning hook must be architecturally possible
- access controlled through signed/proxied URLs
- achievements should support evidence verification state

## 14. Security requirements

Mandatory:
- HTTPS outside local development
- secure headers
- CSRF protection where cookies are used
- CORS allowlist
- rate limiting for authentication and public-like endpoints
- object-level authorization
- audit logging
- input validation
- file validation
- database backups
- structured logs
- dependency scanning in CI
- no secrets in logs
- no PII in generic error responses

Never implement a "temporary" insecure bypass without explicit TODO and development-only guard.

## 15. Data/privacy rules

- Collect minimum necessary data.
- Separate public profile data from restricted internal data.
- Survey anonymity must be real at the application layer.
- Do not expose respondent identity to teachers for anonymous lesson feedback.
- Access to corruption-related data must be restricted to specifically authorized roles.
- Create retention configuration for logs, survey raw responses and uploaded files.
- All data export endpoints require authorization and audit logging.

## 16. Coding standards

Backend:
- type hints for service/public functions
- small focused services
- explicit serializers
- transactions for multi-write business operations
- select_related/prefetch_related on list endpoints
- no N+1 queries in critical endpoints
- timezone-aware datetimes only
- UUIDs for internal entities
- database constraints for integrity

Frontend:
- strict TypeScript
- no `any` unless justified
- API layer separated from UI
- loading/empty/error states
- accessible forms
- Uzbek Latin UI first
- avoid hardcoded permission logic scattered across components

Flutter:
- feature-first folders
- immutable state
- domain/API models separated where useful
- secure token storage
- graceful offline/error handling
- permission prompts only when needed
- NFC/camera hardware failures must not crash app

## 17. Language rules

- Code, identifiers, commit messages: English.
- User-facing primary language: Uzbek Latin.
- Architecture/docs may be Uzbek with English technical terms.
- Do not use Russian identifiers in source code.

## 18. Database and migrations

- Every schema change must have migration.
- Never edit an already-applied production migration.
- Add indexes based on real query patterns.
- Use unique constraints for idempotency.
- Seed/demo data must be separated from production data.
- Provide rollback notes for destructive migrations.

## 19. API standards

- Prefix: `/api/v1/`
- JSON
- UTC timestamps in transport; render local timezone in client
- pagination on list endpoints
- machine-readable error codes
- consistent validation error structure
- OpenAPI generated and validated
- idempotency where duplicate mobile requests are plausible

## 20. Test requirements

No feature is complete without tests.

Minimum:
- unit tests for business rules
- API permission tests
- integration tests for critical flows
- contract tests for external-facing API
- E2E tests for the highest-value flows

Critical E2E:
1. student logs in
2. student joins club
3. leader approves if required
4. leader opens session
5. student attendance recorded
6. attendance appears in student activity history
7. Smart Campus read-only API reflects summary

Also:
- lesson feedback eligibility
- anonymous result protection
- achievement upload/approval
- role permission isolation

## 21. Definition of Done

A TODO item can be marked DONE only if:
- implementation complete
- tests added and passing
- lint/format passing
- migrations created
- API docs updated
- permission checks verified
- audit requirements implemented
- no secrets committed
- TODO/CHANGELOG updated
- Codex summarizes changed files and commands run

## 22. Codex behavior

For every non-trivial task:
1. Read `AGENTS.md`, `PRODUCT_SPEC.md`, `ARCHITECTURE.md`, relevant `TODO.md`.
2. Inspect existing code before proposing new architecture.
3. For multi-file/complex work, create/update an ExecPlan according to `.agent/PLANS.md`.
4. State assumptions in plan, not silently in code.
5. Implement one coherent milestone at a time.
6. Run relevant tests and checks.
7. Fix failures caused by the change.
8. Do not refactor unrelated code.
9. Do not upgrade dependencies unless required by task.
10. Do not mark a task complete if tests were not run; say why if environment prevents them.
11. Never fabricate successful command output.
12. Keep TODO checkboxes truthful.

## 23. Hard prohibitions

Do NOT:
- convert project to microservices during MVP
- let Smart Campus mutate Faol Talaba data
- put business logic only in React/Flutter
- expose anonymous survey respondent identities
- allow unbounded file uploads
- accept client timestamps as authoritative attendance time
- silently auto-approve external achievements
- hard-delete audit logs
- use production credentials in development
- skip authorization because UI hides a button
