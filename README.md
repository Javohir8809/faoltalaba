# Faol Talaba — Codex Development Pack

Bu papka `Faol Talaba` ekotizimini Codex yordamida bosqichma-bosqich ishlab chiqish uchun asosiy loyiha hujjatlarini o'z ichiga oladi.

## Asosiy komponentlar

- `yi.katdpi.uz` — boshqaruv/back-office web panel.
- `Faol Talaba` — talabalar va faoliyat rahbarlari uchun mobil ilova.
- `API` — HEMIS, EKT, Smart Campus va boshqa institut tizimlari bilan integratsiya qatlami.
- `Smart Campus` — faqat tayyor/natijaviy faollik ma'lumotlarini read-only ko'radi.
- `HEMIS` — talaba, xodim, fan, guruh va dars jadvali uchun source of truth.
- `EKT` — kutubxona faoliyati uchun source of truth.

## Lokal ishga tushirish

Talablar: Git, Python 3.13+ va Docker Engine/Docker Desktop bilan Compose v2.
PostgreSQL, Redis va MinIO bog'liqliklari va Django backend bootstrap mavjud.
Backend ishga tushirish tartibi `backend/README.md` da. React va Flutter
keyingi bosqichlarda ishga tushiriladi.

Repo nusxasi olingandan so'ng ildiz papkada Windows va Linux uchun bir xil buyruqlar:

```sh
python tools/dev.py init
python tools/dev.py config
python tools/dev.py up
python tools/dev.py storage-health
python tools/dev.py status
python -m pip install -r requirements-foundation.txt
python tools/dev.py test
```

`init` tasodifiy lokal parollar bilan `.env` yaratadi va mavjud faylni almashtirmaydi.
MinIO rasmiy source release'dan build qilinadi; birinchi `up` dependency download
va kompilyatsiya sababli vaqt oladi, keyingi buildlar Docker cache'dan foydalanadi.
`.env` Gitga kirmaydi; production credentials bu yerga qo'yilmaydi.
MinIO konsoli: http://127.0.0.1:9001 — login lokal `.env` ichida.
Port band bo'lsa `.env` ichidagi tegishli portni o'zgartiring.
Masalan, mavjud PostgreSQL 5432 portni ishlatsa `POSTGRES_PORT=55433`;
lokal backend 8000 portni ishlatsa `BACKEND_PORT=8001` qo'ying.
PostgreSQL 18 volume `/var/lib/postgresql` ga ulanadi.

```sh
python tools/dev.py logs
python tools/dev.py down
```

`down` ma'lumot volume'larini saqlaydi. Bu Compose faqat lokal ishlash uchun;
staging/production uchun HTTPS, alohida credentials, backup va tasdiqlangan
image digestlari kerak. MinIO tayyorligi `storage-health` orqali alohida tekshiriladi.
Docker bo'lmasa runner tushunarli xato beradi; testlar Docker talab qilmaydi.

GitHub Actions test, Compose start/health va dependency scan buyruqlarini bajaradi.
CI serverdagi muvaffaqiyat lokal tekshiruvdan alohida tasdiqlanadi.
Ishlar va tekshiruvlar yagona `WORK_LOG.md` faylida yuritiladi.

Lokal lint/format:

```sh
python -m ruff check tools tests
python -m ruff format --check tools tests
```

Backend Docker profili (lokal development):

```sh
python tools/dev.py up-backend
```

Backend http://127.0.0.1:8000/api/v1/health/ da javob beradi.
Ilova hali auth yoki biznes oqimlarini taqdim etmaydi.

## Ishlab chiqish bosqichlari

1. Repo ildiziga `AGENTS.md` ni qo'ying.
2. `PRODUCT_SPEC.md` va `ARCHITECTURE.md` ni o'zgartirmasdan source of truth sifatida saqlang.
3. Har bir katta bosqich oldidan `.agent/PLANS.md` qoidasi bo'yicha ExecPlan yarating.
4. `TODO.md` dagi faqat bitta bosqichni bir vaqtda bajarishga bering.
5. `PROMPTS.md` dagi mos promptni Codexga yuboring.
6. Codex har taskdan keyin test, lint, migration va qisqa changelog berishi shart.
7. `main` branchga bevosita katta feature yozmang; har bir milestone uchun alohida branch ishlating.

## Tavsiya etilgan repo tuzilmasi

```text
faol-talaba/
├── AGENTS.md
├── README.md
├── TODO.md
├── ARCHITECTURE.md
├── PRODUCT_SPEC.md
├── PROMPTS.md
├── .agent/
│   └── PLANS.md
├── backend/
├── admin-web/
├── mobile/
├── infra/
└── docs/
```
