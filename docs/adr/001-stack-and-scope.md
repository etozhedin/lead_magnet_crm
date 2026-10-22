# ADR 001: Django monolith and scope

Status: accepted.

The assignment prioritizes a complete three-day operational flow. Use Django 5.2,
PostgreSQL, Django sessions, templates and DRF. Bootstrap is vendored, so the UI
does not require an external CDN. SQLite is an explicit local/test convenience;
Compose and CI use PostgreSQL. No AI, external CRM, ads or messaging integrations.

An operator is an active staff user. Provision users via createsuperuser or the
superuser-only service admin. No public registration or password reset is needed.
Operator UI and API filter resources by owner. A superuser is trusted to manage
all records using Django Admin. Other staff users receive no model permissions by
default. Campaigns have one immutable template; templates cannot be edited via API.
Create a new campaign for a different form. Campaigns can be paused and resumed.
Historical events are retained. No permanent deletion API is exposed.

HTML contract: UTF-8 .html up to 512 KiB, exactly one form, 1–30 named fields.
Names must be unique ASCII identifiers. Supported: text, email, tel, url, number,
date, checkbox, a single radio, hidden, textarea and single-select. Radio groups,
multiple selections, disabled controls, password/file inputs and external assets
are rejected or unsupported. Field values are strings, at most 4000 characters.
Server validation covers required values, declared options, email, URL, number
and date. Other HTML constraints are browser hints, not server validation rules.
Browser-supplied hidden fields are untrusted. The supplied example is compatible.

No end-user HTML editor or general-purpose form builder is included. Name the
campaign and select the uploaded HTML to instantiate a custom public form. For
different content, upload another file. This interpretation satisfies the custom
form flow without building an out-of-scope visual form builder.
