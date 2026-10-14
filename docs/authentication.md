# Identity and access — PHASE 2

Internal User, profiles, organization references, role grants and token sessions use
UUIDs. HEMIS/EKT identity values live separately in ExternalIdentity with unique
source/external_id and source/user constraints. Academic reference names are HEMIS-owned;
this phase provides no faculty/department edit API or network integration.

## Provisioning

```sh
python backend/manage.py migrate --noinput
python backend/manage.py createsuperuser
```

Provision locally through the interactive command; never place real passwords in
shell arguments, source, commits or logs. The command creates the explicit global
SUPERADMIN grant and audit events. Password policy requires 12+ characters and
rejects common or entirely numeric passwords. There is no public registration API.

## JWT flow

POST `/api/v1/auth/login/` with username/password returns access and refresh.
Send `Authorization: Bearer <access>` to protected endpoints. Access lasts at most
5 minutes; the session has a fixed 7-day maximum lifetime. Refresh rotates without
extending that lifetime. POST `/api/v1/auth/refresh/` with refresh returns a new pair;
POST `/api/v1/auth/logout/` revokes the session and returns 204.

Tokens contain UUID identity/session and required JWT claims; no role or profile-data snapshot.
The signing key is distinct from Django SECRET_KEY. The database stores a SHA-256
refresh digest, never the raw token. A reused refresh token revokes its session and
all of its access tokens; concurrent refresh requests therefore cannot leave two
usable sessions. Clients must serialize refresh requests and log in after replay
revocation. Logout may revoke a session using an older unexpired refresh token.
Password change and deactivation revoke existing sessions. Requests check current
user/session state; role changes take effect through database permissions immediately.

Login/refresh/logout are Redis-throttled. Redis failure returns generic 503;
bad credentials return identical 401 regardless of account existence. IP limits use
socket REMOTE_ADDR, ignoring untrusted forwarded headers. A deployment proxy boundary
must be configured separately. Tokens use JSON/Bearer transport, not auth cookies.

## Role policy

- SUPERADMIN global: user read, role assignment/revocation and account activation.
- YOUTH_ADMIN global: institution-wide user read; no access management.
- FACULTY_YOUTH_RESPONSIBLE: matching faculty users only.
- DEPARTMENT_RESPONSIBLE: matching department users only.
- CLUB_LEADER and ACTIVITY_RESPONSIBLE: helpers require the matching activity UUID.
  Activity-scoped grants cannot be created through this API before PHASE 4 supplies
  real Activity records and ownership validation.
- TEACHER, STUDENT, SCIENCE_OFFICE, SPORTS_OFFICE, INTERNATIONAL_OFFICE,
  LIBRARY_OPERATOR and ANALYTICS_VIEWER: authenticated own identity only in this
  phase; their domain-specific capabilities arrive with those modules.

Django staff/superuser flags do not bypass explicit API roles. Unknown capabilities
deny. Scoped list endpoints filter in SQL and hide unrelated detail records with 404.
There is no unrestricted profile or evidence export.

## Auditing and database boundary

Role grant/revoke, status change, provisioning, password change and session lifecycle
are audited without passwords, tokens, raw external identifiers or request content.
Multi-write operations are transactional. Last active SUPERADMIN cannot be removed
or deactivated; access administration uses a PostgreSQL transaction lock.

PostgreSQL triggers reject audit UPDATE/DELETE/TRUNCATE and user UUID UPDATE.
Runtime DB access must not have permission to disable/drop these triggers; use a
separate migration owner in production. Local development uses an isolated database.
Rollback must preserve audit history; never blanket-unapply data-bearing migrations
in production. Authentication code/settings may be reverted while keeping the schema.

The pytest disposable `test_` database fixture enables the guards before tests and
allows TRUNCATE only during Django test flush teardown. No application or production
guard exception is introduced.

References: [Django custom user](https://docs.djangoproject.com/en/6.1/topics/auth/customizing/),
[PyJWT claim validation](https://pyjwt.readthedocs.io/en/latest/api.html).
