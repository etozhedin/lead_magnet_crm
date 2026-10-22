# ADR 003: Attribution, visitors and conversion

Status: accepted.

Create four immutable UUID distribution links transactionally with each campaign:
Instagram, X, YouTube, Threads. Link token determines attribution on the server;
query parameters and submitted form fields cannot change the campaign or channel.
Links are retrieved through the campaign API response and operator detail screen.

Each successful GET of a public link records a visit. Reloads count as new visits;
frame loads and operator previews do not. A signed HttpOnly host-only cookie holds
a random visitor UUID for one year. Unique visitors means distinct browser IDs,
not verified people. Clearing cookies creates a new identity; channels share IDs.
Campaign uniques are deduplicated across channels, so channel uniques need not sum
to the campaign total. No IP fingerprinting or third-party analytics is used.

One lead per visit, enforced by a database unique constraint. Repeating the same
submission returns the saved lead; changing its data returns an error. A reload
creates a new visit and can create a new lead. Cross-visit email deduplication is
not assumed by the assignment. get_or_create uses the DB constraint for concurrent
retries. Attribution is to the visit that supplied the submitted form, not another
tab's most recent channel. Paused campaigns reject new visits and submissions.

Metrics cover all time: visits = Visit count; visitors = distinct visitor UUIDs;
applications = Lead count; conversion = applications / visits * 100, rounded to
two decimal places; no visits means 0%. Channel metrics use the same definitions.
Stats are computed from database records on request. No background workers needed.

Limits: no bot filtering, cross-device identity or multi-touch attribution. Test
submissions count as real data. UTC is used for stored and displayed timestamps.
