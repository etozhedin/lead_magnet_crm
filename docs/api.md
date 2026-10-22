# API usage

OpenAPI: [openapi.yaml](openapi.yaml); interactive UI at ADMIN_ORIGIN/api/docs/ after login.
Administration uses host-only Django session cookies and staff permissions.
Other operators' resources return 404. Lists are paginated (50 items per page).
Public routes are available only on PUBLIC_ORIGIN. Wrong surface returns 404.
Deployments can run separate admin/public service roles as described in ADR 004.
GET /health/ is an unauthenticated readiness probe on either host: it returns
200 {"status":"ok"} after a database query, or 503 {"status":"unavailable"}
without connection details. It does not expose campaign or applicant data.

## Authentication

1. GET /api/auth/csrf/ to obtain csrfToken and a CSRF cookie.
2. POST /api/auth/login/ with {"username":"...","password":"..."}, the cookie and
   X-CSRFToken. Login rotates CSRF, so get a fresh token after login.
3. GET /api/auth/me/ to inspect the session.
4. POST /api/auth/logout/ with session and CSRF token to end it.

All authenticated writes require X-CSRFToken (or HTML form csrfmiddlewaretoken).
Invalid credentials return 400, missing CSRF returns 403. Unauthenticated protected
API calls return 403 with SessionAuthentication. API login is IP-throttled locally;
for multiple production workers, use a shared cache/proxy rate limiter.

## Forms and campaigns

- GET/POST /api/templates/: multipart upload with name and file (.html UTF-8).
- GET /api/templates/{id}/: parsed field schema; templates immutable through API.
- GET/POST /api/campaigns/: create with name, template ID, optional active boolean.
  Response includes four generated channel links with token and absolute URL.
- GET /api/campaigns/{id}/: retrieve campaign and distribution links.
- PATCH /api/campaigns/{id}/: rename or change active. Replacing template rejected.
- GET /api/campaigns/{id}/stats/: campaign totals and four channel totals.
- GET /api/leads/?campaign={id}: applicant data, source channel and timestamps.
- GET /api/leads/{id}/: individual applicant.

## Public forms

GET PUBLIC_ORIGIN/r/{token}/ records a visit, sets signed anonymous visitor cookie,
and returns the form shell. The shell embeds /public/render/{ticket}/ in a sandbox.
Rendering the frame is not another visit. Invalid tokens/paused campaigns return 404.
Preview is initiated by an authenticated operator at /templates/{id}/preview/,
uses a 5-minute signed URL, and does not record visits or accept submissions.

POST PUBLIC_ORIGIN/api/public/submit/ accepts:

```json
{"ticket":"signed-ticket-from-public-page","data":{"name":"Alice","email":"alice@example.com"}}
```

Requires Origin: PUBLIC_ORIGIN, the page's visitor cookie and a valid visit ticket.
Returns 201 {"id":1,"created":true}; identical retry returns 200 with created:false.
Invalid/expired ticket, changed repeat submission, unknown fields and invalid field
values return 400. Wrong Origin returns 403. Throttled requests return 429.
The public API never returns applicant data. No CORS access is enabled.

Metric definitions and HTML contract: see ADR 001–003. All timestamps use UTC.
