from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connection
from django.test import Client

from config.environment import external_database, origin_setting


def test_neon_url_preserves_credentials_and_requires_tls():
    database = external_database(
        "postgresql://demo:p%40ss%3Aword@ep-demo.neon.tech/neondb?sslmode=verify-full&channel_binding=require",
        debug=False,
    )
    assert database["PASSWORD"] == "p@ss:word"
    assert database["OPTIONS"]["sslmode"] == "verify-full"
    assert database["OPTIONS"]["channel_binding"] == "require"
    assert database["CONN_MAX_AGE"] == 0
    assert database["CONN_HEALTH_CHECKS"]
    assert database["DISABLE_SERVER_SIDE_CURSORS"]


def test_neon_tls_is_enabled_when_url_omits_it():
    database = external_database("postgres://demo:password@ep-demo.neon.tech/neondb", debug=False)
    assert database["OPTIONS"]["sslmode"] == "require"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://demo:sensitive@ep-demo.neon.tech/neondb?sslmode=disable",
        "sqlite:///tmp/demo.sqlite3",
        "not-a-url-with-sensitive-data",
    ],
)
def test_invalid_or_insecure_production_database_is_rejected_without_leaking_secrets(url):
    with pytest.raises(ImproperlyConfigured) as caught:
        external_database(url, debug=False)
    assert "sensitive" not in str(caught.value)
    assert url not in str(caught.value)


@pytest.mark.parametrize(
    "value",
    [
        "http://admin.example.com",
        "https://admin.example.com/path",
        "https://user:password@admin.example.com",
        "https://admin.example.com?query=1",
    ],
)
def test_production_origins_are_https_without_paths_or_credentials(monkeypatch, value):
    monkeypatch.setenv("TEST_ORIGIN", value)
    with pytest.raises(ImproperlyConfigured):
        origin_setting("TEST_ORIGIN", "", debug=False)


@pytest.mark.django_db
def test_role_boundaries_and_render_health_hostname(settings, api_client):
    settings.RENDER_EXTERNAL_HOSTNAME = "assigned-service-123.onrender.com"
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, settings.RENDER_EXTERNAL_HOSTNAME]
    settings.SERVICE_ROLE = "public"
    assert api_client.get("/api/leads/").status_code == 404
    assert api_client.get("/login/").status_code == 404
    assert api_client.get("/health/", HTTP_HOST="forms.localhost:8017").status_code == 200
    assert api_client.get("/health/", HTTP_HOST=settings.RENDER_EXTERNAL_HOSTNAME).json() == {"status": "ok"}
    assert api_client.get("/api/leads/", HTTP_HOST=settings.RENDER_EXTERNAL_HOSTNAME).status_code == 404
    settings.SERVICE_ROLE = "admin"
    assert api_client.post("/api/public/submit/", {}, HTTP_HOST="forms.localhost:8017").status_code == 404
    assert api_client.get("/health/").status_code == 200


@pytest.mark.django_db
def test_https_proxy_and_platform_health(settings):
    settings.ADMIN_ORIGIN = "https://crm.example.com"
    settings.PUBLIC_ORIGIN = "https://forms.example.com"
    settings.ALLOWED_HOSTS = ["crm.example.com", "forms.example.com"]
    settings.LOCAL_HOST_ALIASES = ()
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    client = Client(HTTP_HOST="crm.example.com")
    assert client.get("/login/").status_code == 301
    assert client.get("/login/", HTTP_X_FORWARDED_PROTO="https").status_code == 200
    assert client.get("/health/").status_code == 200


@pytest.mark.django_db
def test_health_failure_is_generic_and_does_not_expose_connection_details(client):
    with patch("crm.health.connection.cursor", side_effect=OperationalError("sensitive-host-and-password")):
        response = client.get("/health/", HTTP_HOST="admin.localhost:8017")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"sensitive" not in response.content


@pytest.mark.django_db
def test_bootstrap_creates_only_a_staff_operator_and_preserves_existing_credentials(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_USERNAME", "initial-operator")
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_PASSWORD", "Unique-operator-password-758!")
    call_command("bootstrap_operator", stdout=StringIO())
    user = get_user_model().objects.get(username="initial-operator")
    assert user.is_active and user.is_staff and not user.is_superuser
    assert user.check_password("Unique-operator-password-758!")
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_PASSWORD", "Another-password-that-must-not-replace-the-first")
    call_command("bootstrap_operator", stdout=StringIO())
    user.refresh_from_db()
    assert user.check_password("Unique-operator-password-758!")
    assert get_user_model().objects.filter(username="initial-operator").count() == 1


@pytest.mark.django_db
def test_bootstrap_does_not_promote_an_existing_user(monkeypatch):
    user = get_user_model().objects.create_user("ordinary", password="original-password")
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_USERNAME", "ordinary")
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_PASSWORD", "Unique-operator-password-758!")
    with pytest.raises(CommandError):
        call_command("bootstrap_operator", stdout=StringIO())
    user.refresh_from_db()
    assert not user.is_staff
    assert user.check_password("original-password")


@pytest.mark.django_db
def test_bootstrap_rejects_missing_and_weak_credentials(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_USERNAME", "initial-operator")
    monkeypatch.delenv("BOOTSTRAP_OPERATOR_PASSWORD", raising=False)
    with pytest.raises(CommandError):
        call_command("bootstrap_operator", stdout=StringIO())
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_PASSWORD", "password")
    with pytest.raises(CommandError):
        call_command("bootstrap_operator", stdout=StringIO())
    assert not get_user_model().objects.filter(username="initial-operator").exists()


def test_failed_deploy_releases_lock_and_does_not_bootstrap():
    cursor = MagicMock()
    database = MagicMock(vendor="postgresql", settings_dict={"HOST": "direct.neon.tech"})
    database.cursor.return_value.__enter__.return_value = cursor
    with (
        patch("crm.management.commands.prepare_deploy.connection", database),
        patch(
            "crm.management.commands.prepare_deploy.call_command",
            side_effect=CommandError("migration failed"),
        ) as commands,
    ):
        with pytest.raises(CommandError, match="migration failed"):
            call_command("prepare_deploy", stdout=StringIO())
    assert commands.call_count == 1
    assert commands.call_args.args[0] == "migrate"
    assert any("pg_advisory_unlock" in call.args[0] for call in cursor.execute.call_args_list)


@pytest.mark.django_db(transaction=True)
def test_prepare_deploy_on_postgresql(monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL for the deployment advisory lock.")
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_USERNAME", "deploy-operator")
    monkeypatch.setenv("BOOTSTRAP_OPERATOR_PASSWORD", "Unique-deploy-password-926!")
    call_command("prepare_deploy", stdout=StringIO())
    call_command("prepare_deploy", stdout=StringIO())
    assert get_user_model().objects.filter(username="deploy-operator", is_staff=True).count() == 1
