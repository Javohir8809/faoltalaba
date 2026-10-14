# Repository foundation

## Goal
PHASE 0 uchun monorepo, lokal servislar, xavfsiz konfiguratsiya va CI poydevorini yaratish. Bajarilgan ishlar yagona WORK_LOG.md faylida qayd etiladi.

## Non-goals
Django, React, Flutter biznes funksiyalari va real integratsiyalar keyingi bosqichlarda.

## Existing code inspected
AGENTS.md, PRODUCT_SPEC.md, ARCHITECTURE.md, TODO.md, README.md, PROMPTS.md va .agent/PLANS.md. Ilova kodi va Git mavjud emas.

## Assumptions
- Hozirgi bosqich PHASE 0. GitHub Actions tanlanadi: mavjud CI yo'q.
- Task runner Python 3.13 standart kutubxonasi bilan Windows va Linuxda ishlaydi.
- Compose hozir PostgreSQL 18, Redis va MinIO lokal bog'liqliklarini ko'taradi. Backend, worker, frontend va Nginx tegishli bosqichda qo'shiladi.
- Docker dastlab yo'q edi; foydalanuvchi ruxsati bilan Desktop o'rnatildi va runtime tekshiruv boshlandi.
- Redis 7 lokal skelet uchun; MinIO prebuilt image yo'qligi sababli rasmiy
  RELEASE.2025-10-15T17-29-55Z source'dan build qilinadi. Staging oldidan
  image digestlari va upstream maintenance/security holati ko'rib chiqiladi.

## Data model
Bu bosqichda model yoki migration yo'q.

## API contract
Endpoint yo'q; /api/v1/health/ PHASE 1 da.

## Permissions
Ilova RBAC keyingi bosqichda. Lokal servis portlari faqat 127.0.0.1 ga bog'lanadi.

## UI/mobile impact
Faqat papka va keyingi bosqich chegaralarini tushuntiruvchi README.

## External integration impact
HEMIS/EKT/Smart Campus/FCM tarmoqqa ulanmaydi. MinIO faqat lokal storage.

## Security/privacy
.env Gitdan chiqariladi, tasodifiy lokal parollar generatsiya qilinadi, mavjud .env ustiga yozilmaydi. Haqiqiy ma'lumot va production credentials ishlatilmaydi. Volume o'chirish task runner orqali berilmaydi.

## Implementation steps
- [x] Git va milestone branch yaratish.
- [x] Monorepo, env, task runner va Compose yaratish.
- [x] Foundation testlari va CI yaratish.
- [x] README, WORK_LOG, CHANGELOG va TODO holatini yangilash.
- [x] Mavjud muhitda unit, lint, format va syntax tekshiruvlarini bajarish.
- [ ] Docker Compose config/start/health va birinchi CI run natijasini tasdiqlash.

## Test plan
Python unittest: env xavfsiz generatsiyasi va ustiga yozmaslik; runner buyruqlari va xatolari; papka/config mavjudligi. Python compile, Git whitespace va ignore tekshiruvi. Docker mavjud bo'lsa compose config/up/health/down; bo'lmasa cheklovni ochiq yozish. CI dependency scanning boshlang'ich pip-audit vositasi bilan.

## Rollback
Yaratilgan fayllarni Git diff orqali qaytarish. Lokal servislarni down bilan to'xtatish; volume avtomatik o'chirilmaydi. .env va ma'lumot volume'larini qo'lda saqlash.

## Completion notes
7 unit/config testi o'tdi. Ruff check va format check o'tdi; compileall o'tdi.
Docker yo'qligi tufayli runtime acceptance tekshirilmaydi, reja active holatda qoladi.
Buyruqlar va batafsil cheklovlar WORK_LOG.md da. Foydalanuvchi davom etishga
ruxsat bergach PHASE 1 mustaqil backend ishlari boshlandi; ushbu runtime
acceptance ochiq saqlandi.
