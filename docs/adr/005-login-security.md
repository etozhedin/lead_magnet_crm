# ADR 005: Persistent login protection and dependency security fixes

Status: accepted; implemented locally, pending deployment.

## Context

The security review on 2026-10-22 found that the UI and Django Admin login paths
had no attempt limit. The API had only a process-local DRF throttle, which does
not provide a durable account lockout. The dependency audit also flagged DRF
3.16.1 for PYSEC-2026-3827 and PYSEC-2026-3828.

## Decision

Upgrade DRF to 3.17.2, the fixed release for both advisories. Add django-axes
8.3.1 with its database handler and authentication backend so all three login
entry points share account failure records in PostgreSQL. Its packaged migrations
run through the existing locked deployment command.

Temporarily lock an account after ten failed authentications for ten minutes.
Count by username, independent of User-Agent, cookies and forwarding headers.
Do not store client IPs or successful access logs. Passwords are masked by Axes.
Return a generic English 429 response with Retry-After, without account existence
details. Successful authentication clears earlier failures. A lockout does not
terminate an already authenticated session. Pass the underlying Django request
to authentication in the DRF view so middleware sees the same lockout state.

Set production HSTS to one hour for the exact service hostname. Do not request
preloading or include subdomains: deployment uses provider-owned onrender.com
hostnames, and preloading is a separate long-term domain decision.

## Alternatives and consequences

Copying the API's in-memory throttle to UI routes would still reset on restart
and split state between workers. A maintained authentication package is preferable
to custom lockout code. A shared Redis service is unnecessary for this demo.

Username-based lockout can temporarily deny a legitimate user access when someone
intentionally submits bad passwords for that username. Automatic expiry limits
the impact; use a unique demo account and a strong password. This does not prevent
password spraying across many accounts, distributed floods, or database exhaustion.
An edge rate limiter and MFA remain appropriate for a public production service.

Axes emits axes.W006 because this configuration intentionally omits IP-based
lockouts. Regression tests rotate forwarding headers and User-Agent while proving
the username-wide limit still holds. Django's HSTS subdomain and preload warnings
also remain intentional; no security checks are silenced.

## References

- [Django security](https://docs.djangoproject.com/en/5.2/topics/security/)
- [DRF security fixes in 3.17.2](https://www.django-rest-framework.org/community/release-notes/#3172)
- [Axes installation](https://django-axes.readthedocs.io/en/stable/2_installation.html)
- [Axes customization](https://django-axes.readthedocs.io/en/stable/5_customization.html)
