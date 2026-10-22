# Verification — 2026-10-22

Re-audited against the original assignment after switching all authored interface
and documentation text to English. Executed with Python 3.12, PostgreSQL 17 in a
separate disposable Docker container, and Chromium through Playwright.

## Executed checks

- Full suite against PostgreSQL: **52 passed** (49 server tests + 3 browser tests).
- Fast server suite against SQLite: **49 passed**.
- `ruff check .`: passed.
- Django `check`: no issues.
- `makemigrations --check --dry-run`: no changes.
- OpenAPI generation with `--validate --fail-on-warn`: passed.
- `docker compose config --quiet`: passed without changing the running database.
- `docker compose build web`: passed.
- All migrations applied successfully to a fresh PostgreSQL database from the image.
- Gunicorn HTTP checks: login 200; admin CSS 200; public form bridge JS 200;
  public-host admin API 404; anonymous admin-host applicant API 403; service admin
  login 200. Authored text in these responses is English.
- Reviewed the English campaign-detail screenshot after an actual application.
- Scanned 44 source/documentation files: no remaining Cyrillic text. Django's
  default language and all authored HTML language attributes are English.
- README reviewed: English running/testing instructions only. Fixed a malformed
  `docker compose run` command.

## Functional evidence

The primary browser flow logs in, uploads the English example HTML, creates a
campaign, opens the Instagram distribution link, submits a lead, and verifies
persistence, attribution and the operator detail screen. Server tests separately
submit and verify an application for each of Instagram, X, YouTube and Threads.

The isolation browser test checks removal of uploaded scripts, denied cookie and
parent DOM access, CSP-blocked credentialed requests to the administrative API,
host-only operator cookies, sandbox preservation on direct document navigation,
and administrative API denial on the public host.

Additional failure cases cover invalid uploads, unauthorized access, another
operator's data, missing CSRF, invalid credentials, unknown/invalid form fields,
expired/tampered tickets, a tampered visitor cookie, an incorrect request origin,
paused campaigns and repeated submissions with changed data.

A browser regression test verifies that valid field names such as
`addEventListener`, `reportValidity` and `items` do not break submissions or the
CRM table. Submitted script-like text remains escaped in the operator interface.
Both name-collision bugs were reproduced before being fixed.

## Verification limits

GitHub Actions is configured to repeat checks on PostgreSQL but has not been run
remotely. Linux browser installation inside Docker was documented, not executed
in this audit; the browser suite ran locally against PostgreSQL. No hosted demo,
remote repository or submission email has been created. Temporary audit containers
are removed after verification; the user's existing database container is retained.

## Docker deployment recheck

Rechecked the running Compose deployment on port 8017 after a browser request to
`127.0.0.1:8017` exposed a DisallowedHost response. Added development-only GET/HEAD
redirects from loopback addresses to the configured canonical hosts. Rebuilt and
recreated only the web service; PostgreSQL was not restarted during this fix.

- Web service is running; PostgreSQL is healthy.
- Django system checks pass and all migrations are applied.
- One active staff operator exists; applicant data was not inspected.
- **53 server tests passed inside the deployed image**, using a uniquely named
  temporary PostgreSQL test database which Django removed after the run.
- **3 browser tests passed locally** with a separate SQLite test database.
- A real Chromium request to `http://127.0.0.1:8017/` redirects to
  `http://admin.localhost:8017/login/` and loads the English sign-in page (200).
- The administrative applicant API on `forms.localhost:8017` returns 404.
- Production record counts were unchanged by verification.
- The current configuration is a local development deployment: DEBUG=1 and the
  published port is bound to 127.0.0.1. External HTTPS deployment was not tested.

The original 52-test PostgreSQL audit above predates the four additional loopback
redirect tests. The current suite contains 56 tests in total.
