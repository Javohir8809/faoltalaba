# Clubs — PHASE 5

Club specializes a generic Activity with type CLUB and shares its UUID. The backend
supports discovery, automatic/manual membership, leadership, weekly schedule,
sessions and limited management aggregates. Attendance/scanning and UI are later
phases; a successful eligibility check is not an attendance record.

## Create, configure and publish

All routes require JWT. `POST /api/v1/clubs/` takes:

```json
{
  "activity": {
    "title": "Kitobxonlik to'garagi",
    "venue": "Kutubxona",
    "starts_at": "2027-01-01T00:00:00Z",
    "ends_at": "2027-06-30T18:00:00Z",
    "capacity": 30,
    "registration_policy": "APPROVAL",
    "audience": "ALL_STUDENTS"
  },
  "timezone_name": "Asia/Tashkent"
}
```

Type is assigned server-side. Common fields and owner scope follow `activities.md`.
Creation is atomic with its Activity and audit. Use this endpoint for new clubs;
existing bare CLUB activities are not automatically materialized into Club records.
Institutional reviewers (global SUPERADMIN/YOUTH_ADMIN or matching faculty/
department responsible) may create. Activity assignment alone does not authorize it.

`GET /api/v1/clubs/` and `GET /{club_uuid}/` inherit Activity scope/audience visibility.
Lists are paginated (25), searchable by `search`, filterable by `activity__state`,
`activity__faculty`, `activity__department`. Responses contain Activity, timezone,
active member count, last opened session, dormancy flag and active leader UUIDs.
They expose no member roster or private profile names. Leader display profiles
are deferred; source HEMIS names are not automatically made public.

Edit common fields through `PATCH /api/v1/activities/{club_uuid}/`; submit/review/
publish through its `/transitions/` endpoint. Club timezone uses
`PATCH /api/v1/clubs/{club_uuid}/` with `timezone_name`. These edits are allowed
only in DRAFT/REJECTED, consistent with publication review. No hard-delete club API;
Activity DELETE archives only from its allowed states and retains history.

## Weekly schedule

`GET /clubs/{uuid}/schedule/` returns a bounded list (max 21 slots). Managers may
replace it with PUT `{ "slots": [{"weekday": 2, "starts_at": "14:00:00",
"ends_at": "15:00:00"}] }` while the activity is draft/rejected. ISO weekdays 1–7,
same-day ordered local wall times and a valid IANA timezone are required. Duplicate
or overlapping slots are rejected. Identical retries preserve existing slot UUIDs.
Replacing the schedule and its audit commit together. Schedule slots do not generate
session records automatically; sessions accept explicit UTC-aware instants.

## Leadership and authorization

`POST /clubs/{uuid}/leaders/` accepts only `{ "user_id": "<active user UUID>" }`.
`DELETE /clubs/{uuid}/leaders/{grant_uuid}/` revokes that club's CLUB_LEADER grant.
Only institutional reviewers with authority over that club may delegate/revoke.
This narrow permission implements youth/faculty administration without granting
general access administration. Club leaders and activity-scoped responsible users
cannot delegate, publish, or create clubs through their assignment alone. Unknown
input fields such as `role` or `scope_id` are rejected. Duplicate assignment returns
the existing grant without creating another assignment/audit change.

General `/admin/users/{uuid}/roles/` API remains SUPERADMIN-only. Both paths use the
same validated persistence and ActivityRole linkage, serialized with access changes;
revocation immediately removes the role link and next-request permission. Managers
can use the existing `/activities/{uuid}/roles/` to inspect assignments.

## Membership

`POST /clubs/{uuid}/membership/` with `{}` joins/applies. Registration policy is the
single source of truth: OPEN immediately activates; APPROVAL creates pending request;
NONE disables enrollment. Student role, active source profile/affiliations and
target audience are rechecked independently from management visibility. Join accepts
PUBLISHED/REGISTRATION_OPEN/ACTIVE clubs until term end, including after term start.

`GET /clubs/{uuid}/membership/` reads only the authenticated user's membership;
`DELETE` leaves it (204). These self operations still work if the club is hidden/
suspended or academic audience changes, so a person can inspect/leave their record.
PENDING/ACTIVE duplicate join returns the same UUID. LEFT may rejoin under current
policy/capacity using the same Participant; REJECTED cannot automatically reapply
or turn rejection into LEFT to bypass review. No history is deleted.

Participant(activity, student) is unique and authoritative. ClubMembership is its
one-to-one specialization; it does not duplicate student/activity IDs. ACTIVE maps
to Participant ACTIVE, PENDING to PENDING, REJECTED/LEFT to CANCELLED. Every status
change updates both and immutable audit together under the activity/club lock.

Capacity counts ACTIVE memberships only. Pending requests do not reserve seats.
Automatic join and approval both check capacity under the same club lock; concurrent
last-seat requests cannot overbook. Leaving frees a seat. Approval rechecks current
student eligibility and open enrollment, so stale/inactive applicants cannot be
approved merely because they applied earlier.

`GET /clubs/{uuid}/members/` is a paginated manager-only roster, with membership
state, necessary student UUID/full name and review result. Ordinary students cannot
read another membership, roster or private management analytics. Cross-scope club
objects are hidden with 404. Authorized managers review using
`POST /clubs/{uuid}/members/{membership_uuid}/decision/`:

```json
{ "decision": "REJECT", "reason": "Ariza shartlari bajarilmadi." }
```

APPROVE/REJECT apply only to PENDING; repeated same decision is idempotent. Rejection
requires a nonblank reason (max 500), available only to owner/authorized managers.
Raw reason/name/profile values are not copied into generic errors, logs or audit.

## Sessions and attendance eligibility

`GET /clubs/{uuid}/sessions/` is a paginated visible schedule/session list. Managers
create a planned session via POST with `starts_at`, `ends_at`, `idempotency_key`
(UUID). Window must be ordered, within an operational published club term, and not
already ended. Equal key/payload returns the original session; changed payload with
the same key returns 409 `IDEMPOTENCY_CONFLICT`. Duplicate starts are rejected.

POST `{}` to `/clubs/{uuid}/sessions/{session_uuid}/open/` or `/close/`. Opening
requires PLANNED, an operational club, server time within both windows and no other
OPEN session for that club. One-open state is also enforced by a partial unique
database constraint. Server writes opened_at/opened_by and closed_at/closed_by;
client final timestamps are rejected. Replays do not extend the window or change
timestamps. CLOSED cannot reopen. Close is permitted after expiry or club suspension
so authorized staff can finalize a stale OPEN record. Expiry alone never grants
attendance eligibility even if status still says OPEN. No automatic state scheduler
is installed. CANCELLED is reserved in schema; there is no cancel write API yet.

`clubs.sessions.eligible_for_attendance(session, student)` is read-only foundation:
it reloads current session/user, checks OPEN and server windows, operational club,
current student role/source/audience, ACTIVE membership and ACTIVE Participant.
It returns false for pending/rejected/left/inactive/out-of-window cases. Phase 6
must lock/recheck those rules inside its attendance write transaction; callers must
not treat a previously computed boolean as final authorization. This phase creates
no AttendanceRecord, device/card mapping, QR token or client check-in timestamp.

## Analytics and dormancy

`GET /clubs/{uuid}/analytics/` requires club management permission and returns active/
pending memberships, closed session count, last opened session and dormancy. Counts
use distinct aggregation to avoid membership/session join multiplication; catalog
query count stays bounded as club count grows. Dormant means a published operational
club whose term is currently running and last opened session was >30 days ago; if
none opened, creation time is used. Future/ended terms are not marked dormant.
These are operational indicators, not verified attendance or an activity score.

## Validation and rollback

Errors use shared stable JSON/code structure. Important field codes include
`club_full`, `join_closed`, `membership_rejected`, `session_window_invalid`,
`session_window_closed`, `session_already_open`, `session_unavailable`,
`club_not_editable`, `invalid_transition` and `invalid_club`. UUIDs and relation
history are retained. DB constraints enforce session states/windows and uniqueness,
membership status, weekly day/time ordering; domain operations enforce affiliation,
capacity and scope. All writes fail atomically if audit cannot be recorded.

Run backend pytest, foundation tests, Ruff, migration drift and OpenAPI validation
as documented in `backend/README.md`. Tests include real PostgreSQL concurrency
and a JWT student -> application -> leader approval -> session open -> eligibility
flow. Stop writers/workers before code rollback. Retain additive tables/Participant/
audit data; reverse migrations only after backup/review and audited revocation of
club-scoped grants. No production credentials, deployment or external data sync
is needed for this milestone.
