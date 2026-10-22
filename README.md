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
