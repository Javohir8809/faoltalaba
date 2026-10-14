# Faol Talaba — ish jurnali

Bu yagona jurnal har bir ish bosqichi, o'zgartirilgan fayllar, bajarilgan
buyruqlar, tekshiruvlar va qolgan muammolar bilan yangilanadi.

## 2026-10-14 — PHASE 0: Repository foundation

### Boshlang'ich tahlil
- Yetti loyiha hujjati o'qildi; dastur kodi va Git yo'q edi.
- Faqat PHASE 0 bajariladi. Biznes funksiyalari keyingi bosqichlarda.
- Muhit: Python 3.13.2, Git 2.53.0.windows.3. Docker buyruqi topilmadi.

### Bajarilgan ishlar
- Git repository va `chore/repository-foundation` branch yaratildi.
- `docs/exec-plans/active/repository-foundation.md` reja yozildi.
- Monorepo papkalari va ularning vazifalarini tushuntiruvchi READMElar yaratildi.
- Git ignore, editor konfiguratsiyasi va LF qoidasi qo'shildi.
- Sir saqlamaydigan `.env.example`, tasodifiy lokal credential generatsiyasi va task runner yaratildi.
- PostgreSQL 18, Redis va MinIO uchun loopback portli Compose skeleti qo'shildi.
- Foundation testlari va GitHub Actions CI skeleti qo'shildi.
- READMEga Windows/Linux lokal buyruqlari, portlar va ma'lumot volume'larini saqlash qoidasi yozildi.
- `requirements-foundation.txt` da Ruff 0.17.0 va PyYAML 6.0.3 mahkamlandi; loyiha uchun `ruff.toml` yaratildi.
- TODO faqat tekshirilgan ishlarga belgilandi. Compose/CI acceptance hali ochiq.

### Tekshiruvlar
- `git init -b main`, `git switch -c chore/repository-foundation` — muvaffaqiyatli.
- `python --version`, `git --version`, `node --version` — Python 3.13.2, Git 2.53.0.windows.3, Node v25.6.1.
- `python tools/dev.py init` — lokal .env yaratildi, parollar outputga chiqarilmadi.
- `git check-ignore .env` — .env ignore qilinganini tasdiqladi.
- `python tools/dev.py config` — Docker topilmagani uchun exit 2; muvaffaqiyat deb hisoblanmadi.
- `python -m venv .venv`; `.venv/Scripts/python -m pip install ruff PyYAML` — izolatsiyalangan tekshiruv muhiti tayyorlandi.
- Birinchi Ruff check ikki import tartibi xatosini topdi; `ruff check --fix` va `ruff format` bilan tuzatildi.
- `.venv/Scripts/python tools/dev.py test` — yakuniy 7 test o'tdi: credential generatsiyasi, .envni saqlash, shell-siz argv, volume saqlash, maxfiy config output, xatolar va Compose xavfsizlik qoidalari.
- `.venv/Scripts/python -m ruff check tools tests` — o'tdi.
- `.venv/Scripts/python -m ruff format --check tools tests` — 2 fayl formatga mos.
- `.venv/Scripts/python -m compileall -q tools tests` — o'tdi.
- `git diff --no-index --check NUL tools/dev.py` — whitespace xabari yo'q; exit 1 yangi fayl farqi sababli.
- `git add --intent-to-add .` — yangi fayllar diff uchun ko'rinadigan qilindi; commit yaratilmadi. `git ls-files .env` bo'sh chiqdi.
- Git whitespace tekshiruvi yangi fayllardagi ortiqcha yakuniy bo'sh satrlarni topdi; tuzatildi, yakuniy `git diff --check` o'tdi.
- CI YAML PyYAML bilan parse qilindi; bu CI ishga tushganini anglatmaydi.
- API, migration va biznes E2E tekshiruvlari bajarilmadi: ilova hali yaratilmagan.

### Cheklovlar
- Docker o'rnatilmagan: Compose config/start va konteyner runtime tekshiruvi lokal muhitda bajarilmaydi.
- GitHub remote yo'q; CI serverda hali ishga tushmagan.
- Ilova hali yaratilmagan; backend API, migratsiya, UI va biznes E2E bu bosqichga kirmaydi.
- MinIO latest va image taglari staging oldidan tasdiqlangan digestlarga mahkamlanishi kerak.

### Keyingi qadam
Docker Engine/Desktop va Compose v2 mavjud muhitda config/up/storage-health/downni
tekshirish, CI ni ishga tushirish va PHASE 0 acceptance'ni yopish.
Bu bosqich runtime tasdiqlanmaguncha to'liq DONE deb belgilanmaydi.

## 2026-10-14 — PHASE 1: Backend bootstrap

### Ruxsat va qarorlar
- Foydalanuvchi ishni davom ettirishga ruxsat berdi; barcha ishlar shu jurnalga yoziladi.
- AGENTS, PRODUCT_SPEC, ARCHITECTURE, TODO va active planlar qayta tekshirildi.
- PHASE 0 Docker/CI acceptance ochiq saqlandi. Mustaqil backend bootstrap boshlandi.
- Windowsdagi mavjud PostgreSQL 18.3 binarlari topildi. Umumiy PostgreSQL service
  va uning ma'lumotlari o'zgartirilmadi; .local/postgres alohida cluster 55432 portda ishga tushirildi.
- UUID user va JWT PHASE 2 da kiritiladi; auth/admin ilovalari va ularning
  default integer user migratsiyalari hozir yaratilmagan. API default deny.

### Bajarilgan ishlar va fayllar
- `docs/exec-plans/active/backend-bootstrap.md` — assumptions va tekshirish rejasi.
- `backend/manage.py`, `backend/config/` — Django 6.1.2 + DRF 3.18.3;
  local/test/staging/production settings; PostgreSQL/Redis/Celery va CORS konfiguratsiyasi.
- `backend/config/health.py`, `urls.py`, `errors.py` — public read-only health,
  dependency readiness va bir xil JSON xatolar. Xato javobida private qiymatlar yo'q.
- `backend/config/logging.py`, `middleware.py` — UTC JSON loglar; request body,
  query, credential, raw exception va PII logga yozilmaydi.
- `backend/requirements*.txt`, `pytest.ini`, `tests/test_bootstrap.py` — pinned
  dependencies va PostgreSQL, permission, privacy, error, deployment testlari.
- `backend/Dockerfile`, `.dockerignore`, `infra/compose.yaml` — non-root lokal backend profili.
- `.github/workflows/foundation.yml` — backend tests, migrations, OpenAPI, Docker probes,
  lint va dependency scan qo'shildi. Remote CI run hali bajarilmagan.
- `tools/native_postgres.py` — mavjud native binarlardan isolated local cluster
  start/stop; SCRAM password, loopback binding, ma'lumotlar saqlanadi.
- `.env.example`, `tools/dev.py`, foundation testlari — tasodifiy Django secret
  generatsiyasi. Mavjud lokal .envga secret qo'shildi, oldingi parollar saqlandi.
- `docs/api/openapi.yaml`, `docs/api/README.md` — generatsiya qilingan API contract.
- READMElar, TODO, CHANGELOG yangilandi; Redis runtime tasdiqlanmagani uchun ochiq qoldi.

### Buyruqlar va natijalar
- `.venv/Scripts/python -m pip install Django>=6,<7 ...` — backend stack o'rnatildi;
  o'rnatilgan direct dependency versiyalari requirements fayllarida mahkamlandi.
- `postgres.exe --version` — PostgreSQL 18.3.
- `.venv/Scripts/python tools/native_postgres.py start --bin .../PostgreSQL/18/bin`
  — isolated localhost:55432 baza tayyor. Native DB tests/migrate uchun
  `POSTGRES_PORT=55432` faqat command muhitida berildi, .envning Compose porti o'zgarmadi.
- `python backend/manage.py check` — 0 muammo.
- `python backend/manage.py migrate --noinput` — clean DBda contenttypes.0001 va .0002 o'tdi.
- `python -m pytest -c backend/pytest.ini backend/tests` — yakuniy 16 test o'tdi;
  real PostgreSQL 18+ va migratsiya jadvali mavjudligi tekshirildi.
- `python tools/dev.py test` — 7 foundation testi o'tdi; jami 23 test.
- Ruff dastlab import/line length xatolarini ko'rsatdi; fix/format bilan tuzatildi.
- `python -m ruff check backend tools tests` va `format --check` — yakuniy tekshiruvlar o'tdi.
- `python -m compileall -q backend tools tests` — o'tdi.
- `python -m pip check` — broken dependency yo'q.
- `python -m pip_audit --strict -r backend/requirements.txt -r requirements-foundation.txt`
  — ma'lum zaiflik topilmadi; bu penetration test emas.
- OpenAPI birinchi generatsiya docs/api papkasi yo'qligi sababli xato berdi;
  docs/api/README yaratilib tuzatildi. Yakuniy `spectacular --validate --fail-on-warn` o'tdi.
- Production sample environment bilan `manage.py check --deploy --fail-level WARNING`
  — 0 muammo. Real production deploy bajarilmadi.
- `manage.py makemigrations --check --dry-run` — qo'shimcha migration o'zgarishi yo'q.
- Lokal `manage.py runserver 127.0.0.1:8000 --noreload` ishga tushirildi.
- HTTP GET `/api/v1/health/` → 200 `status=ok`.
- HTTP GET `/api/v1/ready/` → 503 `status=unavailable`; real Redis hali mavjud emas.
- Yangi config fayllaridagi yakuniy bo'sh satrlar olib tashlandi;
  yakuniy `git diff --check` o'tdi. `.env` va `.local/postgres` ignore tasdiqlandi.

### Ochiq tekshiruvlar
- Docker Engine/Compose va real Redis runtime; Docker build/probes.
- GitHub remote va birinchi CI run. Hech narsa publish/push qilinmadi.
- PHASE 1 to'liq DONE emas: Redis runtime acceptance ochiq.
- Lokal development server va isolated PostgreSQL hozir ishlayapti; production emas.

### Keyingi milestone
Infrastructure runtime tekshiruvlarini yopish; so'ng PHASE 2 — UUID identity,
refresh rotation/revocation, RBAC va privileged changes uchun audit.

## 2026-10-14 — Docker/Redis runtime tekshiruvi

- Foydalanuvchi Docker/Redis ishga tushirish va readiness tekshiruviga ruxsat berdi.
- Windows 11 Pro, WSL 2.6.3 mavjud; Linux distro o'rnatilmagan.
- Docker Desktop va docker CLI topilmadi. Git remote mavjud emas;
  shu sabab remote CI tekshiruvi hali bajarilmaydi.
- Dockerning rasmiy Windows install qo'llanmasi tekshirildi:
  https://docs.docker.com/desktop/setup/install/windows-install/
- Docker Desktopni WSL2 backend bilan lokal o'rnatish va Compose testlarini
  bajarish boshlandi; natijalar quyida yoziladi. Mavjud PostgreSQL service saqlanadi.
- Port tekshiruvi: 5432 mavjud PostgreSQL service, 55432 isolated native cluster,
  8000 oldingi lokal Django tomonidan band. Compose uchun lokal .envga
  POSTGRES_PORT=55433 va BACKEND_PORT=8001 qo'yiladi; oldingi credentiallar saqlanadi.
- `infra/compose.yaml` backend porti parametrlandi va `.env.example`/README yangilandi.
- `backend/tests/test_runtime.py` — haqiqiy Redis cache roundtrip va DB+Redis
  readiness integration testlari qo'shildi.
- Task runner `up-backend` buyrug'i bilan backend profilini build/start qiladi;
  `down` barcha profillarni to'xtatadi, volume saqlanadi. Docker Windows installer
  yo'llari yangi terminal ochilmasdan topiladi. Tegishli regression test qo'shildi.
- Winget orqali Docker Desktop 4.95.0 per-user, WSL2 backend bilan o'rnatildi;
  installer hash tekshiruvi o'tdi va `Successfully installed` qaytdi.
- Docker CLI 29.8.2 va Compose v5.6.0 mavjud. Docker Desktop yashirin
  background launch qilindi; daemon readiness tekshirilmoqda.
- `python tools/dev.py config` — haqiqiy Compose konfiguratsiya validatsiyasi o'tdi.
- 8 foundation testi o'tdi; Ruff import/format tuzatishidan keyin check o'tdi.
- Birinchi daemon/Compose urinishlari WSL bootstrap tugamagani uchun 500 berdi;
  engine tayyor bo'lgach `docker info` 29.8.2 qaytardi.
- Image pull yangi installer PATH terminalga o'tmagani sababli
  docker-credential-desktop topilmadi. Runner child process PATHiga Docker bin
  papkasini qo'shish bilan tuzatildi; tizimning global PATHi o'zgartirilmadi.
- DockerHub minio/minio pull access denied, Quay latest manifest ham mavjud emas.
  Rasmiy MinIO release source build tavsiya qilgani sababli `infra/minio/Dockerfile`
  orqali RELEASE.2025-10-15T17-29-55Z (session-policy security fix) mahkamlandi.
  Multi-stage Go builder, checksum-verifying modules, non-root runtime va license
  qo'shildi; texnologiya stacki o'zgarmadi. READMEda upstream archive holati va
  staging oldidan maintenance/security review talabi qayd etildi.
- PostgreSQL va Redis Compose konteynerlari healthy bo'ldi.
- Runtime build runnerning --project-directory argumenti Compose relative pathlarini
  noto'g'ri resolve qilayotganini aniqladi. Argument olib tashlandi; backend build,
  env_file va MinIO context endi infra/compose.yaml joylashuviga nisbatan yechiladi.
- Compose yangi PostgreSQL bazasida clean migrate o'tdi; 18 backend testi (jumladan
  real Redis cache roundtrip va real DB+Redis readiness) va 9 foundation testi o'tdi.
- Ishlab turgan native backend `/api/v1/ready/` endpointi endi HTTP 200 `status=ok` qaytardi.
- MinIO source build va backend container build davom etmoqda.
- Backend Docker image build o'tdi va konteyner healthy bo'ldi.
- Docker backend http://127.0.0.1:8001/api/v1/health/ va /ready/ → 200 `status=ok`.
- Konteyner ichidagi `manage.py check` → 0 muammo; `migrate --check` o'tdi.
- PHASE 1 Redis va backend Docker acceptance tasdiqlandi. Remote CI hali yo'q;
  MinIO/runtime restart tekshiruvi PHASE 0 da davom etmoqda.
- Backend ExecPlan `docs/exec-plans/completed/backend-bootstrap.md` ga ko'chirildi.
- Remote CI uchun repozitoriy URL'i asinxron so'raldi; lokal tekshiruvlar davom etadi.

## 2026-10-15 — runtime va GitHub davomiy tekshiruvi

- Foydalanuvchi `git@github.com:Javohir8809/faoltalaba.git` manzilini berdi.
- GitHub sahifasida repo bo'shligi tekshirildi. SSH ulanishi publickey ruxsati yo'q
  deb qaytdi; HTTPS/Git Credential Manager mavjudligini tekshirish boshlandi.
- Redis konteynerida `redis-cli ping` → PONG; backend runtime UID → 1000 (non-root).
- `.env` va `.local/postgres` Git ignore tasdiqlandi; `.env` Git tracked fayllarida yo'q.
- MinIO source build o'tdi, storage readiness va barcha to'rtta servis healthy tasdiqlandi.
- `python tools/dev.py down`, so'ng `up-backend` bajarildi; volume o'chirilmadi.
  Build cache ishladi va barcha servislar yana healthy holatga keldi.
- Native SSH ishlamagani uchun origin shu repo HTTPS manziliga o'tkazildi.
  Mavjud Git Credential Manager credentials bilan GitHub API repo push permission'ni
  tasdiqladi. Credential qiymatlari outputga yozilmadi.
- GitHub CI uchun bosh repo bo'sh ekanligi tasdiqlandi; main uchun kichik empty
  baseline va implementation uchun alohida milestone branch tayyorlanadi.
- Restartdan keyin PostgreSQL contenttype count va Redisga yozilgan owned test
  marker saqlangani tasdiqlandi; marker o'chirildi. Health/ready yana 200,
  storage-health o'tdi.
- Initial main baseline commit `5a9e0f9`, implementation commit `f0faa25` yaratildi.
  `git push origin main` va `git push -u origin chore/repository-foundation` o'tdi.
- Push oldidan staged fayllar lokal uchta credential qiymatiga solishtirilib
  tekshirildi; sirlar va .local ma'lumotlari staged/committed fayllarda topilmadi.
- Remote CI natijasi tekshirilmoqda. Main branchga implementation merge qilinmadi.
- Draft PR #1 yaratildi va ushbu chatga biriktirildi:
  https://github.com/Javohir8809/faoltalaba/pull/1
- Push CI run: https://github.com/Javohir8809/faoltalaba/actions/runs/38620753027
  — Foundation tests, lint/format, syntax va Compose config allaqachon o'tdi;
  source MinIO build bosqichi davom etmoqda. Yakuniy natija hali tasdiqlanmadi.
- GitHub Actions push run 38620753027, implementation commit f0faa25:
  yakuniy `conclusion=success`. Foundation tests, lint/format, syntax, Compose,
  storage readiness, backend tests/migrations/schema, Docker backend probes,
  shutdown va dependency scanning bosqichlarining barchasi success.
- PR uchun avtomatik run 38621213393 ham boshlandi; bu ayni implementationning
  takroriy PR-event tekshiruvi. Push run muvaffaqiyati tasdiqlangan.
- PHASE 0 dagi barcha checkboxlar bajarilgan tekshiruvlar asosida yopildi.
  Repository foundation ExecPlan completed papkasiga ko'chiriladi.
- PHASE 0 va PHASE 1 lokal hamda remote pipeline poydevori tayyor. Keyingi
  milestone PHASE 2 — UUID identity, JWT rotation/revocation, RBAC va audit.
