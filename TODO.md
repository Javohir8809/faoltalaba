# TODO.md — Faol Talaba Implementation Roadmap

> Rule: Codex must not attempt all phases in one run.
> Work phase-by-phase. Every phase needs tests and a short completion report.

## PHASE 0 — Repository foundation

- [x] Create monorepo folders: `backend/`, `admin-web/`, `mobile/`, `infra/`, `docs/`
- [x] Add root `.gitignore`
- [x] Add `.editorconfig`
- [x] Add `.env.example`
- [x] Add root development README
- [x] Add Docker Compose local development skeleton
- [x] Add Makefile or task runner with common commands
- [x] Add CI skeleton
- [x] Ensure AGENTS.md applies from repo root

Acceptance:
- [x] New developer can clone and start local dependencies with documented commands
- [x] No secrets committed

---

## PHASE 1 — Backend bootstrap

- [x] Initialize Django project
- [x] Configure PostgreSQL
- [x] Configure Redis
- [x] Configure environment settings
- [x] Add DRF
- [x] Add drf-spectacular
- [x] Add pytest/pytest-django
- [x] Add ruff
- [x] Add health endpoint
- [x] Add structured logging
- [x] Add settings split for local/staging/production

Acceptance:
- [x] `/api/v1/health/` works
- [x] tests pass
- [x] OpenAPI schema generated
- [x] database migration runs from clean DB

---

## PHASE 2 — Identity, users and RBAC

- [x] Create UUID-based User model
- [x] Create StudentProfile
- [x] Create StaffProfile
- [x] Create external identity mapping model
- [x] Implement roles
- [x] Implement permission helpers/policies
- [x] Implement JWT auth
- [x] Implement refresh token rotation/revocation
- [x] Implement audit base model/service
- [x] Add permission test matrix

Acceptance:
- [x] student cannot access admin endpoints
- [x] faculty responsible cannot access another faculty unless granted
- [x] privileged mutations create audit log

---

## PHASE 3 — HEMIS integration foundation

- [x] Define HEMIS client interface
- [x] Implement timeout/retry rules
- [x] Create mock HEMIS adapter
- [x] Create sync models/state
- [x] Sync faculties
- [x] Sync departments
- [x] Sync groups
- [x] Sync students
- [x] Sync staff/teachers
- [x] Sync subjects
- [x] Add schedule adapter interface
- [x] Add Celery sync jobs
- [x] Add admin sync status page/API
- [x] Add failure logging

Acceptance:
- [x] app works with mock HEMIS
- [x] sync is idempotent
- [x] deleted/changed external records have defined handling
- [x] user-facing API does not depend on live HEMIS availability

Foundation mock adapter bilan tekshirildi. Haqiqiy HEMIS wire adapteri uchun
API contract va ishlaydigan endpointlar hali kerak; URL/token sozlash mavjud.
Tafsilotlar: `docs/hemis-integration.md`.

---

## PHASE 4 — Activity core

- [x] Create Activity base model
- [x] Create activity type enum
- [x] Create lifecycle states
- [x] Create organizer/responsible relations
- [x] Create audience rules
- [x] Create venue/capacity fields
- [x] Create registration policy
- [x] Create ActivityRole model
- [x] Create participant model
- [x] Add CRUD API
- [x] Add admin permission rules
- [x] Add filters/search/pagination
- [x] Add OpenAPI docs

Acceptance:
- [x] authorized staff can create/publish activity
- [x] student sees only published/eligible activity
- [x] lifecycle transitions validated

---

## PHASE 5 — Clubs

- [x] Create Club domain model
- [x] Create ClubMembership
- [x] Create join policy: auto/manual
- [x] Create ClubSession
- [x] Implement club create/edit/publish
- [x] Implement leader assignment
- [x] Implement student join/apply
- [x] Implement approve/reject
- [x] Implement member list permissions
- [x] Implement club schedule
- [x] Implement session open/close
- [x] Implement dormancy indicators
- [x] Add club analytics

Acceptance E2E:
- [x] student joins club
- [x] leader approves when required
- [x] leader opens session
- [x] member is eligible for attendance

---

## PHASE 6 — Attendance engine

- [x] Create AttendanceRecord
- [x] Create AttendanceDevice
- [x] Create StudentCardMapping
- [x] Add NFC token resolver abstraction
- [x] Add QR/barcode resolver abstraction
- [x] Add manual attendance flow with reason
- [x] Implement active session window
- [x] Implement idempotent check-in endpoint
- [x] Use server-side timestamp
- [x] Add duplicate constraint
- [x] Add audit trail for corrections
- [x] Add attendance statistics
- [x] Add device metadata support
- [x] Add rate limiting

Acceptance:
- [x] duplicate scan does not create duplicate attendance
- [x] closed session rejects check-in
- [x] unauthorized leader cannot scan for unrelated activity
- [x] manual correction is auditable

---

## PHASE 7 — Admin web foundation

- [ ] Initialize React + TypeScript + Vite
- [ ] Configure Tailwind
- [ ] Configure component system
- [ ] Configure TanStack Query
- [ ] Configure React Hook Form + Zod
- [ ] Build auth flow
- [ ] Build role-aware navigation
- [ ] Build generic table/filter components carefully
- [ ] Build dashboard shell
- [ ] Build activity CRUD
- [ ] Build clubs pages
- [ ] Build membership approval
- [ ] Build session/attendance view
- [ ] Add error/loading/empty states

Acceptance:
- [ ] no business authorization depends solely on frontend
- [ ] staff can manage club flow end-to-end

---

## PHASE 8 — Flutter mobile foundation

- [ ] Initialize Flutter app
- [ ] Configure Riverpod
- [ ] Configure go_router
- [ ] Configure Dio
- [ ] Configure secure token storage
- [ ] Build login
- [ ] Build activity home/feed
- [ ] Build club list/details
- [ ] Build join/apply
- [ ] Build "My activities"
- [ ] Build leader mode visibility
- [ ] Build session screen
- [ ] Add NFC scanner abstraction
- [ ] Add QR/barcode scanner
- [ ] Handle hardware permission/error states
- [ ] Add offline-safe retry for idempotent scan submission

Acceptance:
- [ ] student can browse/join
- [ ] leader can open session and scan
- [ ] network retry cannot duplicate attendance

---

## PHASE 9 — Events

- [ ] Event model/domain fields
- [ ] event publication
- [ ] target audience
- [ ] registration
- [ ] capacity/waitlist decision
- [ ] event roles
- [ ] event attendance session
- [ ] registered vs attended analytics
- [ ] mobile event feed
- [ ] admin event management

Acceptance:
- [ ] real attendance separated from registration
- [ ] role recorded

---

## PHASE 10 — Achievements and evidence

- [ ] Configure MinIO
- [ ] Create upload service
- [ ] MIME/size validation
- [ ] Create Achievement
- [ ] Create Evidence
- [ ] Create verification workflow
- [ ] Add external activity submission
- [ ] Add responsible office approval
- [ ] Add rejection reason
- [ ] Add portfolio projection
- [ ] Add secure file access

Acceptance:
- [ ] user upload never becomes VERIFIED automatically
- [ ] verifier identity/timestamp logged
- [ ] verified achievement appears in portfolio

---

## PHASE 11 — Survey engine

- [ ] Survey model
- [ ] Question model
- [ ] Option model
- [ ] target audience model
- [ ] anonymous/identified mode
- [ ] question types
- [ ] publication window
- [ ] one-response policy
- [ ] conditional follow-up foundation
- [ ] response submission
- [ ] aggregate analytics
- [ ] admin survey builder
- [ ] mobile survey UI

Acceptance:
- [ ] anonymous results do not expose respondent through normal analytics API
- [ ] permissions tested
- [ ] response limits enforced

---

## PHASE 12 — HEMIS lesson schedule + feedback

- [ ] Implement schedule sync using actual available HEMIS contract
- [ ] Create LessonOccurrence model
- [ ] Create feedback eligibility service
- [ ] Create sampling configuration
- [ ] Create feedback window
- [ ] Create lesson feedback template
- [ ] Create Celery scheduling flow
- [ ] Add push invitation
- [ ] Add attendance-based eligibility option
- [ ] Add minimum aggregate threshold
- [ ] Add teacher aggregate API
- [ ] Add management analytics
- [ ] Add mobile short feedback flow

Acceptance:
- [ ] teacher cannot identify individual respondent
- [ ] expired feedback cannot be submitted
- [ ] non-eligible student cannot submit
- [ ] aggregate threshold enforced

---

## PHASE 13 — Notifications

- [ ] Configure Firebase project integration via env
- [ ] DeviceToken model
- [ ] notification preferences
- [ ] in-app notification model
- [ ] FCM service
- [ ] Celery notification jobs
- [ ] activity notification
- [ ] approval notification
- [ ] lesson feedback notification
- [ ] anti-spam/anti-fatigue rules
- [ ] delivery failure handling

---

## PHASE 14 — Volunteering

- [ ] volunteer activity subtype
- [ ] task/role
- [ ] verified hours
- [ ] attendance integration
- [ ] responsible approval
- [ ] portfolio projection
- [ ] analytics

---

## PHASE 15 — Competitions

- [ ] competition subtype
- [ ] institutional/external distinction
- [ ] application workflow
- [ ] level enum
- [ ] result enum
- [ ] evidence verification
- [ ] achievements integration
- [ ] portfolio projection

---

## PHASE 16 — Additional activity domains

Implement one by one, reusing Activity core:
- [ ] Science
- [ ] Sport
- [ ] Culture
- [ ] Innovation/startup
- [ ] International
- [ ] Mentoring
- [ ] Professional development
- [ ] Media/IT
- [ ] Eco/social

For each:
- [ ] define only domain-specific fields
- [ ] define responsible office
- [ ] define application rules
- [ ] define attendance/result rules
- [ ] define portfolio projection
- [ ] tests

---

## PHASE 17 — Student initiatives

- [ ] Initiative model
- [ ] submission UI
- [ ] review workflow
- [ ] resource request
- [ ] team members
- [ ] approved initiative → project/activity conversion
- [ ] progress states
- [ ] completion result

---

## PHASE 18 — EKT integration

- [ ] Define EKT contract/adaptor
- [ ] Map student identity
- [ ] Define which library activities are imported
- [ ] Sync provenance
- [ ] idempotent import
- [ ] error/retry handling
- [ ] activity/portfolio projection
- [ ] analytics

---

## PHASE 19 — Portfolio

- [ ] Define verified activity projection rules
- [ ] Create activity timeline
- [ ] leadership section
- [ ] achievements section
- [ ] volunteer section
- [ ] certificates section
- [ ] filter by academic year
- [ ] correction request workflow
- [ ] export decision deferred until approved

---

## PHASE 20 — Smart Campus read-only API

- [ ] service account authentication
- [ ] API versioning
- [ ] activity summary endpoint
- [ ] activity history endpoint
- [ ] clubs endpoint
- [ ] achievements endpoint
- [ ] portfolio endpoint
- [ ] rate limiting
- [ ] audit requests
- [ ] OpenAPI contract
- [ ] contract tests
- [ ] data minimization review

Acceptance:
- [ ] no Smart Campus write endpoint exists
- [ ] API does not expose survey identities/private evidence

---

## PHASE 21 — Analytics dashboard

- [ ] active students
- [ ] participation trend
- [ ] unique reach
- [ ] faculty breakdown
- [ ] club health
- [ ] dormant clubs
- [ ] registered vs attended
- [ ] volunteer hours
- [ ] achievements
- [ ] survey response rate
- [ ] lesson feedback aggregate trend
- [ ] export permissions/audit

---

## PHASE 22 — Security hardening

- [ ] threat model
- [ ] permission matrix review
- [ ] CORS review
- [ ] CSRF review
- [ ] rate limiting review
- [ ] file upload review
- [ ] JWT lifecycle review
- [ ] secrets review
- [ ] logging/PII review
- [ ] dependency scan
- [ ] backup/restore test
- [ ] audit immutability review
- [ ] anonymous survey privacy test

---

## PHASE 23 — Performance and reliability

- [ ] query profiling
- [ ] eliminate N+1
- [ ] indexes
- [ ] pagination limits
- [ ] Celery retry policies
- [ ] HEMIS outage simulation
- [ ] EKT outage simulation
- [ ] mobile network retry tests
- [ ] attendance concurrency test
- [ ] load test key endpoints

---

## PHASE 24 — Staging

- [ ] staging Docker deployment
- [ ] staging DB
- [ ] staging MinIO
- [ ] staging FCM
- [ ] mock/sandbox HEMIS or controlled real integration
- [ ] smoke test checklist
- [ ] migration rehearsal
- [ ] monitoring
- [ ] backup

---

## PHASE 25 — Pilot

Pilot one faculty / controlled group first.

- [ ] select pilot users
- [ ] register test cards
- [ ] create real clubs/events
- [ ] train responsible staff
- [ ] collect bugs
- [ ] measure scan reliability
- [ ] measure survey fatigue
- [ ] review privacy issues
- [ ] fix before institute-wide rollout

---

## PHASE 26 — Production rollout

- [ ] production deployment checklist
- [ ] DB backup before migration
- [ ] TLS/domain
- [ ] production secrets
- [ ] object storage backup
- [ ] FCM production config
- [ ] HEMIS production sync
- [ ] EKT production sync
- [ ] Smart Campus service account
- [ ] admin onboarding
- [ ] incident procedure
- [ ] rollback plan
- [ ] post-launch monitoring

---

## DEFERRED / DO NOT IMPLEMENT WITHOUT APPROVAL

- [ ] activity scoring formula
- [ ] student leaderboard
- [ ] AI recommendation engine
- [ ] face recognition attendance
- [ ] microservices
- [ ] Kafka
- [ ] Kubernetes
- [ ] ClickHouse
- [ ] automated disciplinary decisions
- [ ] high-stakes decisions from survey results
