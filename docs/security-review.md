# Security review — 2026-10-22

Scope: source inspection, automated local regressions, runtime dependency audit,
and unauthenticated read-only HTTP checks against the Singapore demo services.
No password guessing, destructive requests, applicant-data extraction or load
testing was performed on the live deployment. This is a focused review, not an
independent penetration test or a guarantee of absence of vulnerabilities.

## Findings and local changes

1. **Medium: login brute-force exposure.** UI `/login/` and `/admin/login/`
   had no failed-login limit; the API limiter used a process-local cache.
   Added database-backed Axes protection across all entry points: ten failures
   cause a ten-minute account lockout. Tests cover cross-route bypass, changing
   forwarding headers and User-Agent, cache clearing, expiry and successful login.
2. **Medium: vulnerable DRF dependency.** pip-audit reported PYSEC-2026-3827
   (oversized request parsing can bypass Django's memory limit) and
   PYSEC-2026-3828 (AdminRenderer data disclosure). The latter renderer is not
   enabled in this application, so its exploit conditions were not reproduced.
   Upgraded 3.16.1 to fixed 3.17.2. A regression proves oversized JSON is rejected
   before submission serializer validation. The updated runtime requirements
   have no known advisories reported by pip-audit at review time.
3. **Low: missing application HSTS.** Added one-hour HSTS for production
   responses. HTTPS redirection and Secure cookies were already configured.

These fixes are in the working tree. The deployed application was inspected
before these changes; they require a new deployment of both services.

## Verified controls

- Anonymous admin-host `/api/leads/` and `/api/docs/` return 403.
- Public-host `/login/`, `/api/leads/` and `/api/docs/` return 404.
- Both hosts return 404 for `/.env` and `/.git/config`.
- HTTPS login responses have X-Frame-Options: DENY and nosniff.
- Staff checks and owner-filtered querysets protect campaigns, templates and leads.
  A new ordinary operator has no Django Admin model permissions.
- Login and administrative writes require CSRF. Sessions are host-only, HttpOnly,
  Secure outside development and SameSite=Lax. The public host cannot access
  administrative routes even if a canonical admin Host header is supplied.
- Uploaded HTML uses an allowlist, is never interpreted as a Django template,
  and runs inside an opaque-origin sandbox with a restrictive CSP. Scripts,
  external resources, native form navigation and outbound connections are blocked.
  The trusted bridge checks its iframe source and message shape.
- Public submissions require the exact public Origin, a signed expiring visit
  ticket and matching signed browser cookie. Unknown fields and invalid values
  are rejected; retrying a visit cannot create duplicate applications.
- ORM queries are parameterized, displayed lead values are escaped, uploads
  and field counts are bounded, Neon URLs require TLS in production, and the
  Docker image runs as a non-root user. Real `.env` files are excluded from Git
  and the build context; no cloud credentials were added during this review.

## Remaining limits

- Public visit URLs intentionally create analytics rows; bots can inflate visits
  and repeatedly open forms to obtain fresh tickets. No edge anti-bot protection
  or global visit quota is configured. The DRF submission throttle remains a
  process-local usage guard and is not a denial-of-service defence.
- Account lockout can temporarily inconvenience a targeted legitimate user.
  MFA and upstream rate limiting are not configured.
- Health checks expose only generic DB availability. Platform administrators and
  holders of the Neon connection string can access application data. Account
  permissions, database backups, log retention and provider security settings
  were not audited through cloud account configuration.
- Signed preview URLs are bearer links valid for five minutes. Do not share
  private preview URLs or deployment logs publicly.
- Use synthetic applicant data and a separate reviewer account for the demo.

## Validation

See `tests/test_security.py` for the added regressions and the existing API,
HTML-isolation and browser suites. Axes migrations are supplied by the pinned
dependency; no CRM schema migration is introduced. Expected deployment-check
warnings and operational tradeoffs are recorded in ADR 005.

Results: 75 server tests passed against disposable PostgreSQL 17; 74 passed and
one PostgreSQL-only test was skipped in the SQLite suite. Three Chromium browser
tests passed. Ruff lint/format, migration drift and OpenAPI validation passed.
The updated runtime requirement audit reported no known vulnerabilities.
