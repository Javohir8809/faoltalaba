# Backend

Django 6.1.2 + DRF modular monolith. Python 3.13+, PostgreSQL 18+, Redis
va Celery konfiguratsiyasi mavjud. Biznes qoidalari keyinchalik domain modullarida.

Repo ildizida `.env` yarating va Python virtual muhitida dependencies o'rnating:

```sh
python tools/dev.py init
python -m pip install -r backend/requirements-dev.txt
python backend/manage.py check
python backend/manage.py migrate --noinput
python backend/manage.py runserver 127.0.0.1:8000
```

Lokal endpointlar:
- GET `/api/v1/health/`: liveness, DB/Redisga bog'liq emas.
- GET `/api/v1/ready/`: DB va Redis tayyor bo'lsa 200, aks holda umumiy 503.
- GET `/api/v1/schema/`: lokal OpenAPI; staging/productionda route mavjud emas.

Test va contract generatsiyasi:

```sh
python -m pytest -c backend/pytest.ini backend/tests
python backend/manage.py spectacular --file docs/api/openapi.yaml --validate --fail-on-warn
python -m ruff check backend tools tests
```

Testlar haqiqiy PostgreSQL 18+ talab qiladi. Test foydalanuvchisiga faqat
lokal/test muhitida test database yaratish huquqi kerak. Production bazada test qilinmaydi.

Windowsda mavjud PostgreSQL binarlari bilan, umumiy servicega tegmasdan:

```powershell
python tools/native_postgres.py start --bin 'C:\Program Files\PostgreSQL\18\bin'
$env:POSTGRES_PORT='55432'
python backend/manage.py migrate --noinput
python -m pytest -c backend/pytest.ini backend/tests
python tools/native_postgres.py stop --bin 'C:\Program Files\PostgreSQL\18\bin'
```

Native cluster `.local/postgres/` da saqlanadi va 127.0.0.1:55432 ga bog'lanadi.
Compose va native cluster alohida DBlar; port override faqat native tekshiruv uchun.

Mavjud `.env`da `DJANGO_SECRET_KEY` yo'q bo'lsa, uni yangi tasodifiy qiymat
bilan qo'shing; boshqa credentiallarni o'zgartirmang. `init` mavjud faylni almashtirmaydi.

Nonlocal `DJANGO_SETTINGS_MODULE=config.settings.staging` yoki
`config.settings.production` orqali tanlanadi. `.env` nonlocal muhitda o'qilmaydi.
SECRET_KEY, explicit hosts, PostgreSQL credentials va Redis/Celery URLlar muhitdan
berilishi shart; DB TLS, HTTPS redirect, secure cookies va HSTS yoqiladi.
Proxy header ishonchi deployment chegarasi aniqlanmaguncha yoqilmaydi.

PHASE 2 UUID user, JWT login/refresh/logout va scoped RBAC mavjud; default API permission deny.
Account bootstrap uchun `python backend/manage.py createsuperuser` interaktiv buyrug'i.
`JWT_SIGNING_KEY` lokal .envda alohida tasodifiy qiymat bo'lishi kerak; qiymatni
log yoki Gitga yozmang. Auth contract va rol doiralari `docs/authentication.md` da.
Audit yozuvlari DB darajasida o'zgartirish/o'chirishdan himoyalangan.
Konfiguratsiya manbalari: [Django PostgreSQL](https://docs.djangoproject.com/en/6.0/ref/databases/),
[DRF release notes](https://www.django-rest-framework.org/community/release-notes/).
