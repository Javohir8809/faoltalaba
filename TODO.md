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

- [ ] Create UUID-based User model
- [ ] Create StudentProfile
- [ ] Create StaffProfile
- [ ] Create external identity mapping model
- [ ] Implement roles
- [ ] Implement permission helpers/policies
- [ ] Implement JWT auth
- [ ] Implement refresh token rotation/revocation
- [ ] Implement audit base model/service
- [ ] Add permission test matrix

Acceptance:
- [ ] student cannot access admin endpoints
- [ ] faculty responsible cannot access another faculty unless granted
- [ ] privileged mutations create audit log

---

## PHASE 3 — HEMIS integration foundation

- [ ] Define HEMIS client interface
- [ ] Implement timeout/retry rules
- [ ] Create mock HEMIS adapter
- [ ] Create sync models/state
- [ ] Sync faculties
- [ ] Sync departments
- [ ] Sync groups
- [ ] Sync students
- [ ] Sync staff/teachers
- [ ] Sync subjects
- [ ] Add schedule adapter interface
- [ ] Add Celery sync jobs
- [ ] Add admin sync status page/API
- [ ] Add failure logging

Acceptance:
- [ ] app works with mock HEMIS
- [ ] sync is idempotent
- [ ] deleted/changed external records have defined handling
- [ ] user-facing API does not depend on live HEMIS availability

---

## PHASE 4 — Activity core

- [ ] Create Activity base model
- [ ] Create activity type enum
- [ ] Create lifecycle states
- [ ] Create organizer/responsible relations
- [ ] Create audience rules
- [ ] Create venue/capacity fields
- [ ] Create registration policy
- [ ] Create ActivityRole model
- [ ] Create participant model
- [ ] Add CRUD API
- [ ] Add admin permission rules
- [ ] Add filters/search/pagination
- [ ] Add OpenAPI docs

Acceptance:
- [ ] authorized staff can create/publish activity
- [ ] student sees only published/eligible activity
- [ ] lifecycle transitions validated

---

## PHASE 5 — Clubs

- [ ] Create Club domain model
- [ ] Create ClubMembership
- [ ] Create join policy: auto/manual
- [ ] Create ClubSession
- [ ] Implement club create/edit/publish
- [ ] Implement leader assignment
- [ ] Implement student join/apply
- [ ] Implement approve/reject
- [ ] Implement member list permissions
- [ ] Implement club schedule
- [ ] Implement session open/close
- [ ] Implement dormancy indicators
- [ ] Add club analytics

Acceptance E2E:
- [ ] student joins club
- [ ] leader approves when required
- [ ] leader opens session
- [ ] member is eligible for attendance

---

## PHASE 6 — Attendance engine

- [ ] Create AttendanceRecord
- [ ] Create AttendanceDevice
- [ ] Create StudentCardMapping
- [ ] Add NFC token resolver abstraction
- [ ] Add QR/barcode resolver abstraction
- [ ] Add manual attendance flow with reason
- [ ] Implement active session window
- [ ] Implement idempotent check-in endpoint
- [ ] Use server-side timestamp
- [ ] Add duplicate constraint
- [ ] Add audit trail for corrections
- [ ] Add attendance statistics
- [ ] Add device metadata support
- [ ] Add rate limiting

Acceptance:
- [ ] duplicate scan does not create duplicate attendance
- [ ] closed session rejects check-in
- [ ] unauthorized leader cannot scan for unrelated activity
- [ ] manual correction is auditable

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
