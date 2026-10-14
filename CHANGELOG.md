# Changelog

## Unreleased
- PHASE 1 Django 6.1.2 + DRF backend with PostgreSQL 18 and Redis/Celery configuration.
- Public read-only liveness/readiness probes, consistent JSON errors and privacy-safe structured logs.
- Local/staging/production settings, HTTPS security baseline, validated OpenAPI contract.
- Real PostgreSQL integration tests and an optional isolated native development cluster tool.
- Local backend Docker profile and backend checks in CI; Docker/PostgreSQL/Redis readiness verified locally.
- Portable Docker discovery/helper PATH handling, backend profile commands and configurable local ports.
- Pinned MinIO source build replacing unavailable prebuilt images, with non-root runtime and healthcheck.
- PHASE 0 monorepo folders, portable development runner, safe local environment generation.
- Local PostgreSQL 18, Redis and MinIO Compose skeleton.
- Foundation tests and GitHub Actions validation/dependency scanning skeleton.
- Central WORK_LOG.md for implementation and validation records.
