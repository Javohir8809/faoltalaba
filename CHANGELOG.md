# Changelog

## Unreleased
- PHASE 3 normalized HEMIS adapter, synthetic mock, configurable URL/token and bounded GET transport.
- Restartable, audited page imports for academic references/student/staff profiles, with explicit source tombstones and preserved local access rules.
- Celery sync jobs/worker profile, protected sync-status API, additive migrations and integration tests.
- PHASE 2 UUID user, academic profiles and external identity mappings with initial migrations.
- JWT login, rotating refresh sessions, replay/logout/password-change revocation and atomic Redis auth throttling.
- Explicit scoped RBAC, filtered user administration and transactionally audited role/status changes.
- PostgreSQL guards for immutable user UUID and append-only audit history; last-active-superadmin protection.
- Auth API contracts, provisioning guide and permission/privacy/concurrency integration tests.
- PHASE 1 Django 6.1.2 + DRF backend with PostgreSQL 18 and Redis/Celery configuration.
- Public read-only liveness/readiness probes, consistent JSON errors and privacy-safe structured logs.
- Local/staging/production settings, HTTPS security baseline, validated OpenAPI contract.
- Real PostgreSQL integration tests and an optional isolated native development cluster tool.
- Local backend Docker profile and backend checks in CI; Docker/PostgreSQL/Redis readiness verified locally.
- Portable Docker discovery/helper PATH handling, backend profile commands and configurable local ports.
- Pinned MinIO source build replacing unavailable prebuilt images, with non-root runtime and healthcheck.
- Verified local Docker shutdown/restart with PostgreSQL and Redis data preservation.
- Verified GitHub Actions tests, schema, Docker probes and dependency scanning on the implementation branch.
- PHASE 0 monorepo folders, portable development runner, safe local environment generation.
- Local PostgreSQL 18, Redis and MinIO Compose skeleton.
- Foundation tests and GitHub Actions validation/dependency scanning skeleton.
- Central WORK_LOG.md for implementation and validation records.
