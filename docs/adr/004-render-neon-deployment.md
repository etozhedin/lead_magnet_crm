# ADR 004: Two Render services and Neon

Status: accepted and deployed. Render services run in Singapore; Neon remains in its existing region.

## Context

The demo needs separate administrative and public origins. There is no custom
domain, and the operator wants Render with Neon. All durable application state,
including uploaded HTML, already lives in PostgreSQL.

## Decision

Deploy the same Docker image as two Render web services with separate onrender.com
hostnames. SERVICE_ROLE=admin/public restricts each instance's route surface,
in addition to the existing host checks. Local Compose remains a combined service
on port 8017. Gunicorn binds to PORT when the hosting platform supplies it.
The default Docker image installs runtime dependencies only. Local Compose sets
INSTALL_DEV=1 to retain pytest, Playwright and lint commands for development.

Use DATABASE_URL for Neon, require TLS outside development, disable server-side
cursors, close connections after each request and enable connection health checks.
Use the direct Neon URL for this small demo: session-level deployment locks cannot
be held safely through a transaction-mode connection pooler.

The Blueprint generates SECRET_KEY once on the admin service. The forms service
references the same key, DATABASE_URL and origins from admin. This is required for
signed preview links, visitor cookies and application tickets to work across the
two services. Origins are explicit inputs rather than guesses from service names;
Render may append a suffix to an assigned hostname.

On startup, RUN_MIGRATIONS=1 runs prepare_deploy before Gunicorn. A PostgreSQL
advisory lock serializes migrations across concurrent service starts. This works
with the free plan without shell access, one-off jobs or a paid pre-deploy hook.
Migration failure prevents startup. Bootstrap credentials create an active staff
operator with no superuser privileges, once. Existing users and passwords are not
modified or promoted. Bootstrap secrets are needed on admin only and are removed
after the first successful deployment.

/health/ performs a database query and returns only a generic 200/503 status. It
works on either surface and on the instance's Render-assigned hostname. It is
exempt from HTTPS redirection for platform probes; application routes require
HTTPS with DEBUG=0. Only the trusted proxy's X-Forwarded-Proto is accepted when
TRUST_PROXY=1. An extra platform hostname never exposes administrative routes.

## Alternatives and consequences

One Render service with two custom domains would avoid a second instance, but a
domain is not available. A VPS and HTTPS proxy would work but add server upkeep.
Render Postgres would also work; Neon was selected explicitly for the hosted DB.

Two free services may have independent cold starts and share the workspace's free
usage allowance. The first opening can be slow. No persistent Render disk is
required. The template uses manual deployments. Schema changes must remain
compatible during rolling updates; startup locks do not make destructive schema
changes safe. A larger production system should separate migration orchestration
and use an appropriate shared throttle/cache backend.

Exact public URLs and Neon credentials are supplied through Render, never Git.
After changing a referenced shared value, sync the Blueprint and deploy both
services, because copied environment values are refreshed during Blueprint sync.

References:
- [Render Docker](https://render.com/docs/docker)
- [Render Blueprint environment references](https://render.com/docs/blueprint-spec)
- [Render health checks](https://render.com/docs/health-checks)
- [Render free limitations](https://render.com/docs/free)
- [Neon Django connection settings](https://neon.com/docs/guides/django)

## Region migration (2026-10-22)

The operator requested an Asian Render region closer to reviewers in Korea.
Choose Singapore for both services. Render regions are immutable, so create
replacement services, retaining the same Neon database and signing key.
Accounts, uploaded forms and campaign identifiers remain in the database.
Public hostnames change; use newly generated links after the move.

During cutover, copy database and key values from the Oregon service through
Render environment references. After provisioning, remove that dependency:
the Singapore admin retains its existing secret values, and the Singapore forms
service references the Singapore admin. Verify both services before retiring
the Oregon instances. Never commit connection strings or signing keys.

Neon is intentionally unchanged at the operator's request. Its distance from
Singapore can add database latency; this migration does not claim to optimize
that round trip.
