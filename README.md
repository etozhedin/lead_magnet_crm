# Running

## Docker Compose (PostgreSQL)

Install Docker with Docker Compose, then run:

```sh
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose up -d web
```

Open the [operator dashboard](http://admin.localhost:8017/) and sign in with the
account you created. Upload `examples/guide.html`, create a campaign, open one of
its channel links and submit a test application. Refresh the campaign page to see
the application and conversion metrics.

In local development (`DEBUG=1`), `http://127.0.0.1:8017/` and
`http://localhost:8017/` redirect to the configured local hostname.

Public forms use `http://forms.localhost:8017`. If your system does not resolve
these names, add this entry to your hosts file:

```text
127.0.0.1 admin.localhost forms.localhost
```

After signing in, open [Swagger UI](http://admin.localhost:8017/api/docs/) for the
interactive API documentation. Stop the application with `docker compose down`;
the database volume is retained.

## Local development

Use Python 3.11 or later. For a quick local run with SQLite:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
export DEBUG=1 DB_ENGINE=sqlite
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8017
```

For local PostgreSQL, unset `DB_ENGINE` and export the `POSTGRES_*` variables from
`.env.example`, using `POSTGRES_HOST=localhost` and the credentials and port of your
running PostgreSQL instance. Then run the same migration, account creation and
server commands. Django reads process environment variables; the `.env` file is
loaded automatically by Docker Compose only.

## HTTPS deployment

Set `DEBUG=0`, a randomly generated `SECRET_KEY`,
`ADMIN_ORIGIN=https://crm.example.com` and `PUBLIC_ORIGIN=https://forms.example.com`.
Point both hostnames to the application and terminate HTTPS at a reverse proxy.
Keep the cookie domain unset. Preserve the original Host header.

Behind a trusted proxy, set `TRUST_PROXY=1`. The proxy must overwrite
`X-Forwarded-Proto` and prevent direct external access to the backend.

## Render + Neon (two services, no custom domain)

1. Publish this repository to your Git provider. Create a Neon project near the
   region you will use on Render. In Neon **Connect**, turn connection pooling
   **off** and copy the **direct** PostgreSQL connection URL, retaining
   `sslmode=require` and any `channel_binding` parameter. Startup migrations use
   a session lock and must not use a `-pooler` hostname.
2. In Render, create a **Blueprint** from this repository using `render.yaml`.
   It defines two free Docker web services in Singapore, `lead-magnet-crm-admin-sg` and
   `lead-magnet-crm-forms-sg`. Choose different service names before import if those
   names already identify resources in your workspace, and update all
   `fromService.name` references to match.
3. Supply the prompted values on the admin service: `DATABASE_URL`,
   `ADMIN_ORIGIN`, `PUBLIC_ORIGIN`, `BOOTSTRAP_OPERATOR_USERNAME` and
   `BOOTSTRAP_OPERATOR_PASSWORD`. Use a unique password of at least 16 characters.
   The Blueprint generates a shared `SECRET_KEY` and copies it, the database URL
   and both origins to the forms service. Do not give the forms service bootstrap
   credentials. `deploy/render.env.example` lists the configuration fields without
   real secrets.
4. Origins must be the **exact HTTPS URLs** assigned by Render, without a path or
   trailing slash. Render may add a suffix to a service's hostname. If the URLs
   are not available during initial Blueprint setup, temporarily enter
   `https://admin.pending.invalid` and `https://forms.pending.invalid`. Once the
   two services exist, copy their actual URLs from the Render dashboard, update
   both origin variables on the **admin** service and save them. **Sync the
   Blueprint again** so the forms service receives the new shared values, then
   manually deploy both services. The temporary origins intentionally do not
   serve the UI: a green health check alone does not mean URL setup is complete.
5. Wait for both deployments to pass `/health/`. Startup applies migrations under
   a PostgreSQL lock, creates the initial operator once, then starts Gunicorn on
   Render's `PORT`. Free services do not need shell access or a pre-deploy hook.
   Open `ADMIN_ORIGIN/login/` and sign in. Existing users and passwords are never
   overwritten by bootstrap. After the first successful sign-in, remove **both**
   bootstrap variables from the admin service and redeploy it.
6. Upload `examples/guide.html`, create a campaign and open a generated link. Its
   hostname must match `PUBLIC_ORIGIN`. Submit an application and verify the
   application and channel metrics in the operator dashboard. Accessing
   `PUBLIC_ORIGIN/api/leads/` must return 404.

Both services must always share the same database, signing key and origin values.
After changing any of these values on admin, sync the Blueprint and deploy both
services. Deploy the same commit to both. Automatic deploys are disabled in the
template; trigger updates from Render's dashboard.

Render Free services sleep after idle periods, so the first opening can take
about a minute. Both services consume the workspace's shared free usage allowance.
No Render persistent disk is required: HTML, sessions, visits and applications
are stored in Neon. Keep local `.env` credentials separate from cloud secrets.

Platform instructions: [Render Docker](https://render.com/docs/docker),
[Blueprint environment references](https://render.com/docs/blueprint-spec),
[Render Free limits](https://render.com/docs/free),
[Neon Django connections](https://neon.com/docs/guides/django).

# Testing

## Docker Compose (PostgreSQL)

With the database service running:

```sh
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings web pytest
docker compose run --rm web ruff check .
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose run --rm web python manage.py spectacular --file /tmp/openapi.yaml --validate --fail-on-warn
```

Tests create a separate test database. The database user must have permission to
create databases, as the default Compose PostgreSQL user does.

To run browser tests inside a disposable container, install Chromium and its Linux
dependencies as root in that container:

```sh
docker compose run --rm --user root -e DJANGO_SETTINGS_MODULE=config.settings web sh -c 'python -m playwright install --with-deps chromium && pytest -m browser'
```

## Local checks

After installing the development requirements:

```sh
. .venv/bin/activate
pytest
ruff check .
DEBUG=1 DB_ENGINE=sqlite python manage.py check
DEBUG=1 DB_ENGINE=sqlite python manage.py makemigrations --check --dry-run
DEBUG=1 DB_ENGINE=sqlite python manage.py spectacular --file docs/openapi.yaml --validate --fail-on-warn
```

The default local test settings use a separate SQLite database. To test against
PostgreSQL locally, configure the database environment variables described above,
unset `DB_ENGINE`, and run `DJANGO_SETTINGS_MODULE=config.settings pytest`.

## Browser tests

```sh
python -m playwright install chromium
pytest -m browser
```

On Linux, use `python -m playwright install --with-deps chromium` to install the
required system libraries. Browser tests start their own test server and check
the operator workflow, submissions, attribution, and isolation of uploaded HTML.

Run every test, including browser tests, with:

```sh
pytest -o addopts=''
```

Deployment configuration, readiness, operator bootstrap and migration-lock tests
are included in `tests/test_deployment.py`. The real advisory-lock test requires
PostgreSQL and is skipped by the fast SQLite suite. To run it with Compose:

```sh
docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings web pytest tests/test_deployment.py
```

Before publishing a Render configuration, validate `render.yaml` against
`https://render.com/schema/render.yaml.json` or, with Render CLI installed, run
`render blueprints validate render.yaml`. Validation with the Render account and
the live Neon connection are checked during the actual deployment.
