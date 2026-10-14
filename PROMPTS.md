# PROMPTS.md — Codex Prompts

Use these prompts one at a time. Do not paste the whole roadmap as an implementation request.

---

## Prompt 0 — Repository audit

You are working on the `Faol Talaba` project.

First read:
- AGENTS.md
- PRODUCT_SPEC.md
- ARCHITECTURE.md
- TODO.md
- .agent/PLANS.md

Do not write application features yet.

Inspect the repository and report:
1. current structure,
2. existing stack and versions,
3. conflicts with AGENTS.md,
4. missing foundation files,
5. risks,
6. exact recommended next TODO item.

Do not modify files unless needed only to fix an obvious documentation path issue. Do not invent existing code.

---

## Prompt 1 — Bootstrap repository

Read all root project instructions first.

Implement only `PHASE 0 — Repository foundation` from TODO.md.

Requirements:
- follow AGENTS.md exactly,
- do not implement business features,
- create a clean monorepo foundation,
- add documented local startup commands,
- create Docker Compose skeleton,
- create env examples with no secrets,
- create CI skeleton,
- keep changes minimal and production-minded.

Before implementation, create an ExecPlan because this touches multiple top-level areas.

After implementation:
- run relevant validation,
- update TODO.md truthfully,
- summarize files changed,
- list commands run,
- list anything blocked.

---

## Prompt 2 — Backend bootstrap

Implement only `PHASE 1 — Backend bootstrap`.

Do not implement users, HEMIS, clubs or auth yet.

Use the fixed backend stack from AGENTS.md.
Create a production-ready settings structure without overengineering.

Must include:
- Django
- DRF
- PostgreSQL configuration
- Redis configuration
- OpenAPI
- pytest
- ruff
- health endpoint
- structured logging
- local/staging/production settings separation

Run tests and schema generation.
Update TODO.md only for items actually completed.

---

## Prompt 3 — Identity and RBAC

Implement only `PHASE 2 — Identity, users and RBAC`.

Before coding:
- inspect existing backend,
- create an ExecPlan,
- explicitly define permission matrix.

Important:
- UUID internal primary keys,
- external HEMIS IDs are not PK,
- deny by default,
- backend-enforced permissions,
- refresh rotation/revocation,
- audit privileged changes.

Add strong tests for cross-role and cross-faculty access.

Do not add HEMIS network integration yet.

---

## Prompt 4 — HEMIS integration

Implement `PHASE 3 — HEMIS integration foundation`.

Critical:
- do not guess undocumented HEMIS endpoints,
- define adapter interfaces first,
- if real endpoint contract is not present in repository, implement a mock/stub adapter and clearly mark the real adapter as pending contract,
- never hardcode credentials,
- all calls use timeout,
- sync is background and idempotent.

Add tests with fixtures/mocks.
Do not make normal app requests depend on HEMIS availability.

---

## Prompt 5 — Activity core

Implement `PHASE 4 — Activity core`.

Design `Activity` as the shared core without turning it into a giant god model.
Use domain-specific extensions for special behavior.

Implement:
- lifecycle,
- organizers/responsibles,
- audience,
- registration rules,
- roles,
- participant relation,
- CRUD,
- filtering,
- permissions,
- tests,
- OpenAPI.

Do not implement clubs/events behavior yet beyond what Activity core needs.

---

## Prompt 6 — Clubs

Implement `PHASE 5 — Clubs`.

Create an ExecPlan.

User flows:
1. staff creates club,
2. leader assigned,
3. club published,
4. student discovers it,
5. student joins/applies,
6. leader approves if manual policy,
7. leader creates/opens session,
8. session later accepts attendance through attendance engine.

Do not fake NFC in this phase; create clean integration points for Phase 6.

Add E2E-level API integration tests for membership flow.

---

## Prompt 7 — Attendance

Implement `PHASE 6 — Attendance engine`.

Security-critical rules from AGENTS.md are mandatory.

Do not assume NFC card technology.
Implement a token resolver abstraction for NFC and QR/barcode.

The attendance endpoint must:
- validate active session,
- validate responsible user,
- resolve student,
- block duplicate check-ins idempotently,
- use server timestamp,
- write audit data.

Add concurrency/duplicate tests where practical.

Do not build Flutter UI yet.

---

## Prompt 8 — Admin web

Implement `PHASE 7 — Admin web foundation`.

Use:
React + TypeScript + Vite + Tailwind + TanStack Query + React Hook Form + Zod.

Build only pages needed for:
- auth,
- activity management,
- clubs,
- membership approval,
- session attendance overview.

All permissions remain backend-enforced.

Add component tests for critical forms and one Playwright happy path if environment supports it.

---

## Prompt 9 — Flutter mobile

Implement `PHASE 8 — Flutter mobile foundation`.

Use the fixed Flutter stack.

Build:
- login,
- activity feed,
- club list/detail,
- join/apply,
- my activities,
- leader mode,
- session view,
- NFC adapter UI,
- QR/barcode scanning UI,
- resilient API retry.

Do not invent NFC card format.
The scanner layer must return an opaque token to backend.

Ensure duplicate network retries cannot create duplicate attendance.

---

## Prompt 10 — Events

Implement only `PHASE 9 — Events`.

Reuse Activity and Attendance infrastructure.
Do not duplicate club attendance code.

Must distinguish:
- registered,
- checked-in,
- role at event.

Add analytics for registered vs attended and unique participants.

---

## Prompt 11 — Evidence and achievements

Implement `PHASE 10 — Achievements and evidence`.

Use MinIO/S3-compatible storage.
Validate MIME and size.
Never trust user filename as storage path.

External achievements must start as pending verification.
Only an authorized reviewer can verify.

Add secure file access and audit logs.

---

## Prompt 12 — Survey engine

Implement `PHASE 11 — Survey engine`.

Build a reusable engine, not hardcoded teacher feedback.

Support:
- anonymous/identified,
- question types from AGENTS.md,
- target audience,
- time window,
- one-response policy,
- aggregate reporting,
- conditional follow-up foundation.

Privacy tests are required.

Do not implement lesson-schedule triggering yet.

---

## Prompt 13 — Lesson feedback

Implement `PHASE 12 — HEMIS lesson schedule + feedback`.

First inspect whether an actual HEMIS schedule API contract exists in repo.
Do not guess it.

Build:
- lesson occurrence,
- eligibility,
- feedback window,
- sampling,
- FCM job trigger interface,
- anonymous response link,
- minimum aggregation threshold.

Teacher-facing API must never expose respondent identity.

If attendance integration exists, make eligibility configurable.

---

## Prompt 14 — Notifications

Implement `PHASE 13 — Notifications`.

Use FCM.
Add in-app notifications too.

No credentials in repo.
Add device token lifecycle and delivery failure handling.
Add anti-fatigue controls so lesson feedback cannot spam the student.

---

## Prompt 15 — Smart Campus API

Implement `PHASE 20 — Smart Campus read-only API`.

This is service-to-service and read-only.

No POST/PATCH/DELETE endpoints for Smart Campus.

Create:
- summary
- history
- clubs
- achievements
- portfolio

Use:
- service authentication,
- rate limiting,
- stable versioned schema,
- contract tests,
- data minimization.

Document the API clearly.

---

## Prompt 16 — Security review

Perform `PHASE 22 — Security hardening`.

Do not add new features.

Review:
- authorization
- token lifecycle
- upload security
- anonymous survey privacy
- audit logging
- CORS/CSRF
- rate limits
- secrets
- logs/PII
- dependency issues
- backup/restore documentation

Produce:
1. findings ranked Critical/High/Medium/Low,
2. fixes implemented,
3. remaining accepted risks.

Never claim a penetration test was performed unless it actually was.

---

## Prompt 17 — Pilot readiness

Prepare the project for `PHASE 25 — Pilot`.

Do not implement speculative features.

Create:
- pilot checklist,
- seeded demo/pilot configuration,
- responsible staff onboarding notes,
- card registration procedure,
- attendance test procedure,
- feedback privacy verification,
- rollback/incident checklist.

Identify blockers before production rollout.

---

## Universal Codex continuation prompt

Continue the `Faol Talaba` implementation.

Read AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md and any active ExecPlan first.

Work on ONLY the first unchecked item(s) inside the currently assigned phase. Do not jump to future phases.

Before changing code:
- inspect related code,
- preserve existing working behavior,
- identify permission/security implications.

After changing code:
- run relevant tests/lint/type checks,
- update TODO.md only for truly completed work,
- update the active ExecPlan,
- summarize changed files,
- list validation commands and results,
- state remaining blockers.

Do not silently change the fixed technology stack or architecture.

---

## Bug-fix prompt

Investigate and fix this bug:

<PASTE BUG HERE>

Rules:
- read AGENTS.md first,
- reproduce or establish a failing test before changing behavior when practical,
- find root cause, not only symptom,
- do not refactor unrelated areas,
- add regression test,
- run relevant test suite,
- explain root cause, fix, and validation.

---

## Review prompt

Review the current branch against:
- AGENTS.md
- PRODUCT_SPEC.md
- ARCHITECTURE.md
- current ExecPlan

Do not modify code initially.

Report findings by severity:
- Critical
- High
- Medium
- Low

Focus on:
- authorization bypass
- privacy leaks
- anonymous survey identity exposure
- attendance fraud/duplication
- bad transaction boundaries
- N+1 queries
- unsafe uploads
- unstable API contract
- missing tests
- business logic duplicated in clients

After the report, implement fixes only if explicitly requested.
