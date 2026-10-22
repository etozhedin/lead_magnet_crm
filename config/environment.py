import os
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def origin_setting(name, default, *, debug):
    value = os.getenv(name, default).strip().rstrip("/")
    parsed = urlsplit(value)
    try:
        parsed.port
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a valid HTTP(S) origin.") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ImproperlyConfigured(f"{name} must be an HTTP(S) origin without a path or credentials.")
    if not debug and parsed.scheme != "https":
        raise ImproperlyConfigured(f"{name} must use HTTPS when DEBUG=0.")
    return value


def external_database(url, *, debug):
    try:
        database = dj_database_url.parse(url, conn_max_age=0, conn_health_checks=True)
    except (ValueError, TypeError):
        # Do not include the supplied URL or parser exception: both may contain credentials.
        raise ImproperlyConfigured("DATABASE_URL must be a valid PostgreSQL connection URL.") from None
    if database["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL must select PostgreSQL.")
    options = database.setdefault("OPTIONS", {})
    options.setdefault("sslmode", "require")
    options.setdefault("connect_timeout", 5)
    if not debug and options["sslmode"] not in {"require", "verify-ca", "verify-full"}:
        raise ImproperlyConfigured("DATABASE_URL must require TLS when DEBUG=0.")
    database["DISABLE_SERVER_SIDE_CURSORS"] = True
    return database
