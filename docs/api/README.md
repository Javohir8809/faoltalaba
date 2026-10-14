# API contract

`openapi.yaml` Django drf-spectacular orqali generatsiya qilinadi:

```sh
python backend/manage.py spectacular --file docs/api/openapi.yaml --validate --fail-on-warn
```

Health liveness faqat jarayon ishlayotganini bildiradi. Readiness PostgreSQL va
Redisga ulanishni tekshiradi, credential yoki dependency error matnini qaytarmaydi.
Auth va domain endpointlar keyingi bosqichlarda qo'shiladi.
