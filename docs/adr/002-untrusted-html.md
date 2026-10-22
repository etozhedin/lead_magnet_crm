# ADR 002: Isolate untrusted HTML

Status: accepted.

An uploaded document must not access operator sessions or administrative APIs.
Render it as data, never as a Django template. Parse HTML5 and allowlist elements
and attributes. Strip uploaded scripts, event handlers, embeds and navigation URLs.
Preserve inline CSS for design; CSP blocks external resources and CSS network loads.
Custom uploaded JavaScript is intentionally unsupported. Only the application's
nonce-authorized form bridge executes.

Administrative and public surfaces use distinct hostnames, enforced before session
middleware. Cookie domains are unset, making cookies host-only. A different port
alone is insufficient, so settings reject equal hostnames. Public paths never
serve admin APIs; admin paths never serve raw uploaded HTML. Static assets are shared.
For local development only, loopback IP and localhost GET/HEAD requests redirect
to the configured admin or public origin. Aliases never serve application content,
never forward writes and do not expose authenticated APIs. This convenience is
disabled outside DEBUG mode and when configured hosts are not .localhost names.

Documents are framed with sandbox="allow-scripts allow-forms", without allow-same-origin,
popups or top-navigation. allow-forms enables browser validation and the submit
event; form-action CSP still blocks native network submissions. Their response also imposes a CSP sandbox,
so opening a frame document directly does not remove sandbox restrictions.
default-src 'none', connect-src 'none', form-action 'none', base-uri 'none' and
frame restrictions prevent network access and nested active content.

The trusted parent accepts messages only from its exact frame window, with opaque
origin 'null', and checks the message shape. It posts to its own public API using a
signed, expiring visit ticket. Server validates the ticket, visitor cookie, campaign
status and fields. No session credentials are sent into the uploaded document.
The bridge calls native prototype methods, so fields named addEventListener or
reportValidity cannot shadow form methods. Applicant data is passed to templates
as explicit key/value pairs to avoid collisions with dictionary method names;
values remain HTML-escaped.
Anonymous submission does not use operator authentication. It requires the public
Origin header and visitor-bound ticket. Origin alone is not treated as authentication.

All admin writes use session authentication and CSRF checks, including login.
Preview documents use a separate 5-minute signed ticket, do not record visits and
cannot save leads. Public visit tickets expire after 24 hours. Deployment requires
HTTPS and correct origins. No permissive CORS is enabled.
