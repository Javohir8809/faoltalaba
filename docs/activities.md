# Activity core — PHASE 4

Generic Activity is the shared parent for upcoming clubs, events and other domains.
It does not implement membership, check-in or institutional scoring. Specialized
workflows belong in their domain models in later phases.

## API

All endpoints require an active JWT session:

- `GET /api/v1/activities/` — paginated visible catalog (25 per page).
- `POST /api/v1/activities/` — create a draft, 201.
- `GET /api/v1/activities/{uuid}/` — visible detail.
- `PATCH` / `PUT` on the detail — draft/rejected content changes.
- `DELETE` on the detail — archive, 204; preserves the record/history.
- `POST /api/v1/activities/{uuid}/transitions/` — `{ "state": "PENDING_APPROVAL" }`.
- `GET /api/v1/activities/{uuid}/roles/` — paginated responsible assignments,
  visible only to that activity's managers; never participant/identity profiles.

Filters: `type`, `state`, owning `faculty`/`department` UUID, `audience`.
`search` matches title, description or venue. `ordering` accepts `created_at`,
`starts_at`, `title` (prefix `-` for reverse). Filtering never broadens visibility.
Unknown detail is 404, unauthenticated requests 401, denied writes 403, validation
400. Error codes follow the shared `{error:{code,message,details}}` contract;
field details include `invalid_transition`, `publication_incomplete`,
`activity_window_closed`, `activity_not_ended`, `registration_unavailable`,
`activity_not_editable`, `immutable_field` or `invalid_activity`.

Example draft input:

```json
{
  "title": "Sport uchrashuvi",
  "type": "SPORT",
  "description": "Talabalar uchun sport uchrashuvi.",
  "starts_at": "2027-01-10T09:00:00Z",
  "ends_at": "2027-01-10T11:00:00Z",
  "venue": "Sport zali",
  "capacity": 40,
  "registration_policy": "OPEN",
  "audience": "ALL_STUDENTS"
}
```

UUID, organizer (the authenticated creator), state and timestamps are server-owned.
Optional owning faculty/department and type are set only at creation; later changes
are rejected. `state` is changed only through transitions. Unknown input fields and
read-only fields are rejected rather than silently ignored. Dates must be paired
and ordered, capacity positive if present. Description <=10000, title <=200, venue
<=250. UTC-aware dates are stored/returned; clients render local time.

## Ownership and permissions

Global SUPERADMIN/YOUTH_ADMIN create and review all activities. Faculty responsible
may do so within their faculty, department responsible within their department.
A department must belong to the owning faculty. Object creator is historical
provenance, not a permanent permission: revoking their current roles removes access.
Django staff/superuser flags alone do not authorize the API.

Activity-scoped ACTIVITY_RESPONSIBLE and CLUB_LEADER can read their assignment's
activity, edit its draft/rejected content, submit it for review and perform permitted
operational transitions. They cannot publish/reject/suspend/archive or create new
activities merely through that assignment. CLUB_LEADER requires type CLUB.
Role delegation remains SUPERADMIN-only through the existing access API:

```json
{
  "role": "ACTIVITY_RESPONSIBLE",
  "scope_type": "ACTIVITY",
  "scope_id": "<existing activity UUID>"
}
```

POST to `/api/v1/admin/users/{user_uuid}/roles/`; revoke with its existing DELETE
grant endpoint. Unknown/archived scopes are rejected. ActivityRole is a one-to-one
link to the authoritative RoleGrant; it does not duplicate roles/user fields.
Grant creation/link/audit are atomic; revoke cascades the assignment and changes
permission on the next request. There is no independent role write endpoint.

## Student discovery

The user needs an explicit STUDENT grant and a local StudentProfile with active
source profile and affiliation references. Faculty/department/group mismatch or
inactive source rows fail closed. All checks use local PostgreSQL; no live HEMIS
or broker request occurs. Missing optional department/group is allowed only for
audiences it does not need.

`INSTITUTION` visibility is discoverable; `MANAGERS_ONLY` is hidden from students.
The activity must have a publication timestamp and be PUBLISHED, REGISTRATION_OPEN,
ACTIVE, COMPLETED or CANCELLED. Draft/rejected/pending/suspended/archived objects
remain hidden; cancelling an unpublished draft never makes it discoverable.
Audience is exactly one of:

- ALL_STUDENTS: no target reference.
- FACULTY: audience_faculty UUID only.
- DEPARTMENT: audience_department UUID only.
- GROUP: audience_group UUID only.

Owning organization and target audience are distinct. An owning faculty may invite
another faculty; this does not grant its staff access to the owning draft.
Discovery is not enrollment or attendance eligibility; those services will add
their domain rules later. A student who also has a management grant sees the union
of managed and student-eligible activities.

## Lifecycle

Allowed transitions:

- DRAFT -> PENDING_APPROVAL, ARCHIVED.
- PENDING_APPROVAL -> PUBLISHED, REJECTED, DRAFT, CANCELLED.
- REJECTED -> DRAFT, ARCHIVED.
- PUBLISHED -> REGISTRATION_OPEN, ACTIVE, CANCELLED, SUSPENDED.
- REGISTRATION_OPEN -> ACTIVE, CANCELLED, SUSPENDED.
- ACTIVE -> COMPLETED, CANCELLED, SUSPENDED.
- SUSPENDED -> PUBLISHED, CANCELLED.
- COMPLETED / CANCELLED -> ARCHIVED.
- ARCHIVED is terminal.

Publication requires start/end, a venue and future end; the server sets first
published_at once. Registration requires OPEN/APPROVAL policy and a future start.
ACTIVE requires `start <= server now < end`; COMPLETED requires end reached.
These transitions are explicit; no scheduler silently changes state. Content may
only change in DRAFT/REJECTED, including target audience and policies. Published
content is immutable in this foundation; reviewed amendments are a future workflow.
DELETE archives only when an ARCHIVED transition is allowed; repeating DELETE on
an archived item is idempotent. Archive requires review authority.

## Data and operational notes

Activity UUID and PROTECT relations retain history. Participant schema has a unique
(activity, student) pair with PENDING/APPROVED/ACTIVE/COMPLETED/CANCELLED state; it
has no API yet. Capacity reservation, join approval and attendance rules are not
implemented here. Registration/attendance/evidence/result policies are explicit
configuration, not a promise those specialized workflows exist in this milestone.

All content/lifecycle writes recheck current scope and lock the activity row.
Audit create/update/transition entries commit with the change; transitions record
only old/new state, not descriptions or profile snapshots. Parallel publication
allows one transition; its competing request gets a validation error. Queries use
ownership/affiliation subqueries and related loading; list query count is tested
against increasing catalog size. No participant roster is returned by discovery.

Additive migrations create activity/assignment/participant tables and database
checks for enums, dates, audience, publication fields and capacity. Rollback by
reverting code and retaining tables; before unapplying, stop writers, back up and
revoke activity scope grants through audited services. Never delete audit history.
