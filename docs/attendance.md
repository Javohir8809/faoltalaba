# Davomat API — PHASE 6

Davomat operator JWT va faoliyatga tegishli RBAC scope orqali qayd etiladi.
STUDENT o'z davomatini tasdiqlamaydi. Hozirgi session provider ClubSession;
boshqa faoliyat sessiyalari keyingi milestone orqali ulanadi.

## Sozlash

`python tools/dev.py init` yangi `.env` uchun mustaqil `ATTENDANCE_TOKEN_KEY`
yaratadi. Mavjud `.env`ga kamida 50 belgili tasodifiy alohida kalit qo'shing.
Uni JWT/SECRET_KEY bilan bir xil qilmang. Qiymatini commit/log/chatga yubormang.
Kalitni backup va barcha backend nusxalarida barqaror saqlang: o'zgarishi karta
lookup'larini yaroqsiz qiladi; rotation alohida re-enrollment rejasini talab etadi.
Production sozlamalari kuchsiz yoki boshqa signing key bilan bir xil kalitni rad etadi.

NFC va QR/barcode bir xil typed adapter chegarasidan foydalanadi. 1–256 belgili,
printable ASCII opaque token qabul qilinadi; tashqi whitespace/control/non-ASCII
rad etiladi, case saqlanadi. NFC va QR digestlari turlicha. Raw token faqat request
input: DB/response/audit/Redis kalitlariga yozilmaydi. Statik kod identifikator;
operator autentifikatsiyasi, scope va server tekshiruvi qatnashishni tasdiqlaydi.
Karta sektorlari yoki kalitlar saqlanmaydi. Fizik NFC qurilma hali tekshirilmagan.

## Endpointlar

Barchasi `/api/v1/` prefiksli, JWT talab qiladi. Listlar pagination bilan.

- `attendance/devices/` GET/POST: operatorning o'z qurilmalari. POST
  `{installation_id, label, platform?, nfc_supported?, camera_supported?}`.
  Platform: UNKNOWN/ANDROID/IOS/WEB/SCANNER. Bir xil installation retry bir yozuv.
- `attendance/devices/{id}/` PATCH: o'z label/platform/support/is_active metadatasi.
  Qurilma UUID'i hardware autentifikatsiyasi emas; check-in'da optional.
- `attendance/card-mappings/` GET/POST: faqat SUPERADMIN. POST
  `{student_id, kind: NFC|QR, token, protocol?, variant?, uid_readable?}`.
  Protocol UNKNOWN/ISO14443/ISO15693/OTHER; MIFARE varianti aniqlansa variantga.
  Format aniqlanmagan bo'lsa UNKNOWN. Takroriy faol bir xil binding idempotent;
  boshqa talabaga yoki bekor qilingan tokenga qayta binding 409.
- `attendance/card-mappings/{id}/revoke/` POST `{reason}`: bir tomonlama bekor qilish.
- `attendance/sessions/{id}/check-in/` POST: `{method: NFC|QR, token, device_id?, note?}`
  yoki `{method: MANUAL, student_id, reason, device_id?, note?}`. Javob 200;
  yangi va duplicate bir xil record formatida. Client vaqti qabul qilinmaydi.
- `attendance/sessions/{id}/records/` GET: scope doirasidagi ro'yxat.
- `attendance/sessions/{id}/stats/` GET: total/present/voided va PRESENT uchun
  by_method (NFC/QR/MANUAL). Bekor qilingan yozuv qatnashganlar soniga kirmaydi.
- `attendance/records/{id}/` GET: scope doirasidagi operator tafsilotlari.
- `attendance/records/{id}/corrections/` POST:
  `{status: PRESENT|VOIDED, reason, expected_version, idempotency_key, note?}`.
  Yangi versiya va append-only old/new history. Stale version yoki qayta ishlatilgan
  kalitning boshqa payload/actor'i 409. Bir xil retry qayta qo'llanmaydi va joriy
  yozuv qaytariladi. Note berilmasa oldingi izoh saqlanadi; bo'sh string uni tozalaydi.
- `attendance/records/{id}/changes/` GET: operator uchun reason/snapshot tarixi.
- `students/me/activity-history/` GET: o'z activity/session/title/time/method/status/
  version tarixi. Ichki izoh, sabab, qurilma, karta, operator yoki boshqa talaba
  identifikatori berilmaydi. STUDENT roli olib tashlansa ham faol user o'z tarixini ko'radi.

## Biznes qoidalari va audit

Faqat OPEN sessiya va faol to'garakning server vaqt oynasida yangi yozuv yaratiladi.
Talaba faol user/source profile/audience va ACTIVE club membership/Participant
shartlarini bajarishi kerak. Activity→Club→Session lock tartibi scan/close/leave'ni
ketma-ketlashtiradi. Session/student DB unique constraint takrorni bloklaydi.
Duplicate yozuvning asl vaqti/usuli/operatori/qurilmasi/izohi/statusi saqlanadi;
VOIDED yozuvni yana scan qilish tiklamaydi. Yopilgan oynada duplicate ham rad etiladi.

Qo'lda kiritish sababsiz mumkin emas. Yopilgandan keyin faqat mavjud yozuv statusi
va izohi sabab bilan tuzatiladi; kechikkan yangi/backdated davomat qo'shilmaydi.
Asl maydonlarni UPDATE qilish hamda history UPDATE/DELETE/TRUNCATE PostgreSQL'da
bloklanadi. Har bir record versiyasi matching immutable change talab qiladi.
Karta binding'ini qayta yozish yoki bekor qilishni ortga qaytarish ham bloklanadi.
Barcha privileged yozuvlar umumiy audit bilan bir transaction'da; audit xatosida
hammasi rollback. Audit metadata'da raw token/izoh/sabab yo'q; sabab faqat scoped
AttendanceChange ichida saqlanadi. Unrelated scope objectlari 404, rolsizlar 403.

Attendance endpointlarida Redis atomic actor/IP limiter (240/1200 daqiqasiga),
HMAC Redis keys va alohida purpose mavjud. Redis outage 503 bilan fail closed;
limit 429. Untrusted forwarded IP e'tiborga olinmaydi. Testda limiter o'chiriladi,
alohida real Redis testlari uni yoqadi. JWT tokenlarining yangi login limiti alohida.

## Migratsiya va rollback

`python backend/manage.py migrate --noinput` additive attendance schema/guardlarni
qo'llaydi. Ishlayotgan muhitda yozuvlarni o'chirib rollback qilmang. Avval writer'larni
to'xtatish va backup/review; schema reverse faqat disposable data yoki alohida
kelishilgan retention qarori bilan. Immutable audit cleanup uchun runtime bypass yo'q.
