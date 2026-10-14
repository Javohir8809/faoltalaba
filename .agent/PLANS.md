# Codex Execution Plans for Faol Talaba

For any task that:
- changes more than one domain,
- requires a migration plus API plus UI,
- changes authentication/permissions,
- adds an external integration,
- or is expected to touch more than ~5 files,

create an ExecPlan before implementation.

Store active plans in:
`docs/exec-plans/active/<short-name>.md`

Move completed plans to:
`docs/exec-plans/completed/<short-name>.md`

An ExecPlan must contain:

## Goal
What user-visible or system capability will exist after this plan.

## Non-goals
What is explicitly excluded.

## Existing code inspected
List relevant files/modules inspected before design.

## Assumptions
All assumptions that could affect implementation.

## Data model
Models, fields, constraints, indexes, migrations.

## API contract
Endpoints, methods, auth, request/response shape, errors.

## Permissions
Who may do what.

## UI/mobile impact
Screens/components and states.

## External integration impact
HEMIS/EKT/Smart Campus/FCM/MinIO, if any.

## Security/privacy
Sensitive data, abuse cases, audit requirements.

## Implementation steps
Ordered, checkable steps.

## Test plan
Unit/API/integration/E2E tests.

## Rollback
How to revert safely.

## Completion notes
Commands run, tests passed/failed, remaining risks.

Rules:
- The plan is a living document.
- Update it when implementation reveals incorrect assumptions.
- Do not silently diverge from it.
- Do not mark complete until validation is performed.
