# ARCHITECTURE.md — Faol Talaba

## 1. System context

```text
                         ┌────────────────────┐
                         │       HEMIS        │
                         │ students/schedule  │
                         └─────────┬──────────┘
                                   │ sync/API
                                   ▼
┌────────────────────┐    ┌─────────────────────────┐
│       EKT          │───▶│ Faol Talaba Backend    │◀──── yi.katdpi.uz
│ library activity   │    │ Django + DRF           │      React Admin
└────────────────────┘    │ Modular Monolith       │
                          └───────┬─────────┬───────┘
                                  │         │
                                  │         └──────────────▶ Smart Campus
                                  │                          READ ONLY API
                                  ▼
                          Faol Talaba Mobile
                          Flutter
                          NFC / QR / Push
```

## 2. Ownership

### HEMIS owns
- student identity source data
- academic groups
- faculty/department mappings
- teachers/employees where available
- subjects
- lesson schedule

### Faol Talaba owns
- clubs
- activities
- applications
- activity roles
- activity sessions
- attendance
- achievements/evidence
- surveys
- lesson feedback responses
- initiatives
- volunteer hours
- activity portfolio
- application workflow
- audit history

### EKT owns
- library-specific source activity

### Smart Campus
- consumes selected summary/history
- cannot write into Faol Talaba

## 3. Main user surfaces

### yi.katdpi.uz
Actors:
- youth office
- faculty youth responsible
- science office
- sports office
- international office
- club/activity responsible
- analytics viewers
- superadmin

Responsibilities:
- create/configure activities
- approve workflows
- view analytics
- moderate evidence
- manage surveys
- manage access/roles
- inspect audit logs

### Faol Talaba mobile
Actors:
- student
- club leader
- activity responsible
- teacher when granted activity responsibility

Student actions:
- discover activities
- join/apply
- upload evidence/results
- participate in surveys
- submit initiatives
- see own activity/portfolio
- receive notifications

Responsible actions:
- open attendance session
- scan NFC or QR/barcode
- review participants where allowed
- record activity result
- close session

### Smart Campus
- display profile summary
- show activity indicators
- show verified achievements/history
- no application/action workflows

## 4. Generic lifecycle

```text
DRAFT
  ↓
PENDING_APPROVAL
  ↓
PUBLISHED
  ↓
REGISTRATION_OPEN
  ↓
ACTIVE
  ↓
COMPLETED
  ↓
ARCHIVED
```

Additional:
- REJECTED
- CANCELLED
- SUSPENDED

## 5. Activity participation lifecycle

```text
DISCOVERED
  ↓
APPLICATION_SUBMITTED
  ↓
APPROVED / REJECTED
  ↓
ACTIVE_PARTICIPANT
  ↓
COMPLETED
```

Some activities can use auto-approval.

## 6. Club lifecycle

1. Authorized staff creates club.
2. Club leader assigned.
3. Schedule/capacity/membership policy configured.
4. Club published to mobile.
5. Student applies/joins.
6. Leader approves if required.
7. Each meeting creates a `ClubSession`.
8. Attendance recorded by NFC/QR/manual.
9. Session closed.
10. Statistics update asynchronously.
11. Inactivity rules flag dormant clubs.
12. Club may be suspended or archived.

## 7. Event lifecycle

1. Event created in admin.
2. Target audience selected.
3. Published.
4. Students register in mobile if registration is required.
5. Event attendance session opens.
6. Check-in by NFC/QR.
7. Role may be participant/organizer/volunteer/speaker/moderator.
8. Event closes.
9. Analytics and portfolio records generated.

## 8. Competition lifecycle

1. Competition created or external opportunity published.
2. Student applies in mobile.
3. Responsible office reviews if needed.
4. Participation occurs.
5. Student uploads result/evidence.
6. Responsible office verifies.
7. Verified result enters achievement/portfolio.
8. Smart Campus summary updates.

## 9. External achievement flow

```text
Mobile
  ↓
Create external activity/achievement
  ↓
Upload evidence
  ↓
PENDING_VERIFICATION
  ↓
Responsible office review
  ↓
VERIFIED / REJECTED
  ↓
Portfolio
```

Never auto-verify user-uploaded evidence.

## 10. Attendance architecture

Entities:
- ActivitySession
- AttendanceRecord
- AttendanceDevice
- StudentCardMapping
- AttendanceAudit

Check-in:
1. Responsible user opens session.
2. Backend validates permission and time window.
3. Scanner reads card/QR token.
4. Mobile sends token + session ID.
5. Backend resolves student.
6. Backend checks eligibility.
7. Database unique constraint prevents duplicate.
8. Backend uses server timestamp.
9. Record returned to client.
10. Async analytics update.

Suggested uniqueness:
`(session_id, student_id)`

## 11. Lesson feedback flow

```text
HEMIS schedule sync
       ↓
Lesson occurrence
       ↓
Lesson end reached
       ↓
Eligibility calculation
       ↓
FCM notification
       ↓
Student answers short feedback
       ↓
Anonymous response storage
       ↓
Aggregate analytics
       ↓
Teacher/management dashboard
```

Rules:
- sampling configurable
- feedback window configurable
- attendance eligibility optional/configurable
- minimum response threshold before teacher aggregate
- teacher never sees respondent identity

## 12. Survey engine architecture

Survey:
- mode: ANONYMOUS / IDENTIFIED
- audience rules
- publication window
- question tree
- conditional logic
- response policy

Do not model IQ/diagnostic tests as "official psychological diagnosis" unless formally approved and validated. The engine may technically host tests, but interpretation rules must be a separate approved concern.

## 13. Notification architecture

Notification types:
- activity published
- application approved/rejected
- session reminder
- lesson feedback invitation
- achievement verification result
- survey invitation
- deadline reminder

Delivery:
- in-app record
- FCM push

Do not send every possible event as push. Support notification preference and anti-fatigue rules.

## 14. Analytics

MVP analytics in PostgreSQL:
- active students
- activity participation
- unique reach
- club activity health
- attendance rate
- faculty/group breakdown
- volunteer hours
- achievements
- survey response rates
- teacher feedback aggregates

Do not introduce analytical DB in MVP.

## 15. Recommended deployment units

Docker Compose services:
- backend
- admin-web
- postgres
- redis
- celery-worker
- celery-beat
- minio
- nginx

Optional later:
- prometheus
- grafana
- sentry self-hosted only if required

## 16. Environments

- local
- staging
- production

Never connect local dev directly to production HEMIS/EKT unless explicitly approved. Provide mocks/sandbox adapters.

## 17. Backup

At minimum:
- PostgreSQL scheduled backup
- MinIO backup strategy
- restore procedure documented and tested
- configuration/secrets backup through secure institutional process

## 18. Non-functional targets for MVP

- API p95 for normal local DB requests: target < 500 ms under expected load
- attendance endpoint: idempotent and responsive
- graceful degradation if HEMIS/EKT unavailable
- mobile app must remain usable for cached browsing when network is temporarily unavailable
- no loss of submitted attendance due to double tap/retry
