# PRODUCT_SPEC.md — Faol Talaba

## 1. Product vision

`Faol Talaba` — talabaning institut bilan darsdan tashqari va fikr-mulohaza bilan bog'liq faol aloqalarini yagona raqamli jarayonga aylantiruvchi platforma.

Asosiy zanjir:

`Imkoniyat → Ariza/A'zolik → Ishtirok → Tasdiqlash → Natija → Portfolio → Analitika`

## 2. Product components

### A. yi.katdpi.uz
Institutional back-office.

### B. Faol Talaba mobile
Student/responsible-person operational app.

### C. Integration API
HEMIS, EKT, Smart Campus and future systems.

## 3. Product areas

1. Clubs
2. Events
3. Volunteering
4. Competitions and olympiads
5. Science
6. Startup/innovation
7. Sports
8. Culture/creative activity
9. Library activity
10. Community/public activity
11. Mentoring
12. Professional development
13. Media/IT activity
14. Eco/social actions
15. International activity
16. Student initiatives
17. External certificates/achievements
18. Surveys
19. Lesson feedback
20. Digital portfolio
21. Analytics

## 4. Core UX principle

Student should not be forced to learn multiple institutional systems.

Operational student actions happen primarily in `Faol Talaba` mobile.

Admin/responsible staff actions happen primarily in `yi.katdpi.uz`.

Smart Campus displays summary only.

## 5. Club user story

As a student:
- I can see active clubs.
- I can filter by category.
- I can see leader, schedule, location, capacity.
- I can join/apply.
- I can see membership state.
- I can see my attendance.
- I can leave subject to policy.

As a club leader:
- I can see my club.
- I can open today's session.
- I can scan student ID card by NFC or barcode/QR.
- I can see real-time count.
- I can close the session.
- I can correct attendance only with reason and audit.

As youth staff:
- I can create/approve clubs.
- I can assign leaders.
- I can see active/dormant clubs.
- I can see attendance analytics.

## 6. Event user story

Student:
- sees event feed
- opens details
- registers if needed
- gets reminder
- checks in at event
- receives verified participation in history

Admin:
- creates event
- configures audience/capacity
- assigns responsible staff
- sees registered vs actually attended
- sees unique reach

## 7. Competition user story

Student:
- sees opportunity
- applies
- tracks status
- uploads final evidence
- sees verified result in portfolio

Responsible office:
- publishes opportunity
- reviews applications if required
- verifies evidence
- assigns level/result

## 8. Volunteering

Must support:
- campaign
- task
- role
- start/end
- verified hours
- responsible person
- attendance
- evidence where necessary

Volunteer hours are never self-declared as verified without approval.

## 9. Student initiatives

Student can submit:
- idea title
- problem
- proposed solution
- expected impact
- requested resources
- optional team

Workflow:
`SUBMITTED → UNDER_REVIEW → APPROVED / REJECTED → IN_PROGRESS → COMPLETED`

Approved initiatives can become activities/projects.

## 10. Surveys

Admin can build and target surveys.

Survey categories:
- teacher/course feedback
- education quality
- corruption-related anonymous survey/reporting
- dormitory
- cafeteria
- Wi-Fi/IT
- library
- campus services
- general student climate
- approved diagnostic/test forms

## 11. Lesson feedback

After eligible lessons, student may receive push:
"Siz hozirgina [teacher] tomonidan [subject] fanidan o'tilgan darsda qatnashdingiz. Dars bo'yicha qisqa fikringizni bildiring."

MVP: 4-6 short questions.

Teacher gets aggregate only.

## 12. Portfolio

Portfolio auto-generates from verified records.

Possible sections:
- clubs
- leadership
- events
- volunteering
- competitions
- achievements
- science
- innovation
- sports
- culture
- international
- mentoring
- certificates

Student cannot directly edit a verified record; correction uses request/audit workflow.

## 13. Smart Campus view

Example:
- Clubs: 2
- Events attended: 18
- Volunteer hours: 26
- Competitions: 4
- Achievements: 2
- Leadership roles: 3
- Activity level: High

No join/apply/upload actions in Smart Campus.

## 14. Management dashboard

Must eventually answer:
- How many active students?
- Which faculties are most/least active?
- Which clubs are actually working?
- Which clubs have no recent sessions?
- Registered vs attended per event?
- Unique student reach?
- Volunteer hours?
- Achievements by level?
- Participation trends?
- Survey response rates?
- Teacher feedback trend?

## 15. Activity score

Do NOT implement final institutional ranking formula in first MVP unless explicitly approved.

First collect reliable data.

Later scoring can consider:
- attendance
- consistency
- role
- verified result
- activity level
- leadership
- contribution

Avoid gamification that rewards meaningless check-ins.

## 16. MVP scope

MVP includes:
- HEMIS student sync
- auth
- RBAC
- clubs
- club membership
- club sessions
- NFC/QR attendance foundation
- events
- event registration
- event attendance
- achievements/evidence
- basic survey engine
- lesson feedback foundation
- FCM notifications
- student activity history
- basic portfolio
- Smart Campus read-only summary API
- audit log
- basic analytics

Post-MVP:
- advanced volunteering
- startup workflows
- mentoring workflows
- international workflows
- advanced scoring
- recommendation engine
- advanced BI
