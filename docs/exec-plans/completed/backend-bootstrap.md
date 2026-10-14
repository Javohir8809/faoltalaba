# Backend bootstrap — PHASE 1

## Goal
Django 6 backend, environment settings, PostgreSQL/Redis konfiguratsiyasi,
health endpoint, OpenAPI va testlar bilan ishlaydigan poydevor yaratish.

## Non-goals
Auth, foydalanuvchi modeli, RBAC biznes qoidalari, HEMIS va faoliyatlar PHASE 2+.

## Existing code inspected
AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md, .agent/PLANS.md,
tools/dev.py, infra/compose.yaml, CI, backend/README.md va WORK_LOG.md.

## Assumptions
- Foydalanuvchi davom etishga ruxsat berdi. PHASE 0 Docker/CI runtime acceptance
  ochiq qoladi; bu mustaqil backend bosqichini yaratishga to'sqinlik qilmaydi.
- Windowsda PostgreSQL 18 binarlari mavjud. Mavjud institut/umumiy bazaga tegmay,
  .local ichida yangi cluster 55432 portda test qilinadi.
- Django auth/admin hozir o'rnatilmaydi: UUID user PHASE 2 da birinchi auth
  migratsiyasidan oldin kiritiladi. API default deny; health ochiq.
- Health liveness infrastruktura talab qilmaydi; readiness DB va Redisga bog'liq.
- Lokal .env yangi secret uchun mavjud credentiallarni saqlab yangilanadi.
- Runtime davomida Docker Desktop o'rnatildi. Compose portlari lokal .envda
  PostgreSQL 55433 va backend 8001 qilib band portlardan ajratildi.
- Compose yangi baza migratsiyalari va Redis cache/readiness testlari o'tdi.

## Data model
Faqat Django contenttypes migratsiyalari; application jadvali hali yo'q.

## API contract
GET /api/v1/health/ → 200 {status: ok};
GET /api/v1/ready/ → 200 yoki 503, dependency detallarini ochmasdan.
GET /api/v1/schema/ lokal OpenAPI; deployda ochiq schema endpoint yo'q.
Xatolar {error: {code, message, details}}.

## Permissions
Default IsAuthenticated; JWT PHASE 2 da. POST health 405. Health/ready read-only.

## UI/mobile impact
UI yaratilmaydi.

## External integration impact
HEMIS/EKT/FCM ulanmaydi. Redis cache va Celery broker konfiguratsiyasi.

## Security/privacy
Nonlocal debug o'chiriladi; secret va host allowlist majburiy, HTTPS redirect,
secure cookies, CORS allowlist va CSRF middleware. Loglar URL query, body,
credential va exception matnini yozmaydi. Public readiness dependency sirlarini yashiradi.

## Implementation steps
- [x] Dependencies va Django/settings yaratish.
- [x] Health/ready/error/OpenAPI/logging yaratish.
- [x] Unit/API/config/PostgreSQL testlari, CI va Docker backend qo'shish.
- [x] Test/lint/schema/deploy check/migrate bajarish.
- [x] WORK_LOG, TODO, CHANGELOG va README yangilash.
- [x] Real Redis cache va Docker backend readiness natijasini tasdiqlash.

## Test plan
pytest: health permissions/methods, unavailable dependencies, generic errors,
logging privacy, nonlocal config validation; PostgreSQL SELECT va clean migrate.
Ruff, schema validate, Django check --deploy va dependency audit.

## Rollback
Backend yangi fayllarini qaytarish; yangi isolated cluster stop qilinadi,
ma'lumotlar o'chirilmaydi. Mavjud PostgreSQL service o'zgartirilmaydi.

## Completion notes
18 backend va 9 foundation testi o'tdi. Native va Compose PostgreSQL clusterlarda
clean migrate bajarildi. Native va Docker backend HTTP health/ready 200.
OpenAPI validate/fail-on-warn va production check --deploy o'tdi.
pip-audit pinned backend/foundation dependencies uchun ma'lum zaiflik topmadi.
Docker backend build/check o'tdi. PHASE 1 local acceptance tasdiqlandi.
Remote CI GitHub remote yo'qligi sababli ishga tushmadi; bu alohida infrastructure
cheklovi WORK_LOG.md va PHASE 0 rejasida ochiq saqlanadi.
