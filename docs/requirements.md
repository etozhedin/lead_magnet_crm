# Assignment requirements audit

Rechecked against the original Korean assignment on 2026-10-22. The functional
requirements are implemented and covered by the verification below. Interpretations
of unspecified behavior are recorded in the ADRs; delivery steps are tracked separately.

## Functional requirements

| Requirement | Status and implementation | Verification |
|---|---|---|
| Only authenticated operators can use administration or view applicants | Implemented: Django staff sessions, owner-scoped UI and API, CSRF protection | Authentication, staff access, ownership and CSRF tests in `tests/test_api.py` |
| Upload a single AI-generated `.html` file | Implemented: UI and multipart API accept one UTF-8 HTML form | Valid upload, invalid extension/encoding/size/structure tests; browser upload flow |
| Create campaigns and custom public forms from uploaded HTML | Implemented: each campaign instantiates an uploaded template with its own public links | Campaign API test and full operator browser flow |
| Create distribution links for Instagram, X, YouTube and Threads | Implemented: four unique UUID links are generated with each campaign | Link creation test and a successful attributed application for each of all four channels |
| Save applications in a relational database as a CRM list | Implemented: PostgreSQL Lead records linked to visits and campaigns; operator table and paginated API | Persistence, retry/idempotency, applicant access and browser tests on PostgreSQL |
| Show campaign visits, visitors, applications and conversion | Implemented: dashboard, campaign detail and stats API | Deterministic counts, unique-browser deduplication, empty totals and conversion tests |
| Show performance by channel | Implemented: campaign detail table and stats API | Per-channel counts, all-four-channel attribution and older-tab attribution tests |
| Document authentication, form management, public submission, distribution links and analytics APIs | Implemented: `docs/api.md`, `docs/openapi.yaml`, authenticated `/api/docs/` | Generated OpenAPI validates with `--fail-on-warn`; endpoint tests |

## Technical and nonfunctional requirements

| Requirement | Status and implementation | Verification |
|---|---|---|
| Use a relational database | PostgreSQL is the default; Compose and CI use PostgreSQL | Original full audit on PostgreSQL 17; latest 70 server tests passed against TLS-enabled PostgreSQL during deployment preparation |
| Complete the operational flow rather than build extra features | Upload → campaign → channel link → public application → CRM and metrics | `test_operator_to_conversion` in Chromium |
| Uploaded HTML cannot access administrator credentials or administrative APIs | Separate hosts, host-only cookies, sanitization, iframe and response CSP sandbox, blocked network requests | Chromium checks cookie/parent DOM isolation, credentialed admin API fetch blocking, direct-document sandbox and public-host API denial |
| Automated tests cover core success and failure flows | 70 server tests and 3 Chromium tests | Latest checks: 70 server tests on PostgreSQL and 3 browser tests on isolated SQLite passed; two-service HTTPS workflow verified |
| README contains only running and testing instructions | English instructions for Docker, local development, HTTPS, server and browser tests | Manual content review; startup command typo corrected |
| Record major decisions and reasonable assumptions in ADRs | Three ADRs cover stack/scope, HTML isolation, attribution/metrics | Cross-checked against implementation and tests |

## Deliverables

| Deliverable | Status |
|---|---|
| Runnable source code repository | Local Git repository with complete application source and Docker setup; no remote repository has been published |
| Database schema and migrations | `docs/schema.md`, `crm/models.py`, `crm/migrations/0001_initial.py`; no pending model changes |
| `.env.example` | Present, including origins, PostgreSQL and proxy settings |
| Test code | `tests/`, pytest configuration, PostgreSQL CI workflow |
| API documentation | `docs/api.md`, generated OpenAPI, Swagger UI |
| README | English; running and testing instructions only |
| ADR | `docs/adr/001-stack-and-scope.md` through `004-render-neon-deployment.md` |

## Documented assumptions and limits

- A custom form is a campaign based on one uploaded HTML template. A different
  form design requires a new upload/campaign; a visual form builder is outside scope.
- Uploaded JavaScript and external assets are unsupported. Inline HTML/CSS and
  the application's submission bridge are supported. File uploads, radio groups
  and multiple selections are outside the documented HTML contract.
- Unique visitors are browser identifiers, not verified people. Conversion is
  applications divided by visits. Attribution follows the submitted form's visit.
- One application is allowed per visit; identical retries are idempotent. A new
  visit may submit another application. These rules are fixed in ADR 003.
- AI, external CRM/messaging/ad integrations, payments, contracts and consultant
  management have not been implemented, as the assignment explicitly excludes them.

## Delivery steps outside local verification

- Publish the repository and provide its URL. This has not been done.
- Send the repository URL and any unfinished mandatory items to the submission
  address from the assignment. No submission email has been sent.
- A hosted demo URL is optional. No hosted demo has been published.
- Submission is due within three days of receiving the assignment. The receipt
  timestamp is not recorded in this repository, so timeliness cannot be verified here.

See `docs/verification.md` for the checks actually executed. A configured CI
workflow is not treated as evidence of a remote CI run.
