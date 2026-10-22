from datetime import timedelta
from unittest.mock import patch

import pytest
from axes.models import AccessAttempt
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from crm.serializers import SubmissionSerializer

pytestmark = pytest.mark.django_db


def test_lockout_is_shared_across_login_surfaces_and_survives_cache_clear(operator):
    client = APIClient(HTTP_HOST="admin.localhost:8017")
    credentials = {"username": operator.username, "password": "wrong"}
    endpoints = ["/login/", "/admin/login/", "/api/auth/login/"]
    for index in range(10):
        path = endpoints[index % len(endpoints)]
        response = client.post(
            path,
            credentials,
            HTTP_X_FORWARDED_FOR=f"198.51.100.{index + 1}",
            HTTP_USER_AGENT=f"Audit/{index}",
        )
        assert response.status_code == (429 if index == 9 else 400 if path.startswith("/api/") else 200)
    # Clearing a process cache or changing an alleged client IP does not reset the lock.
    cache.clear()
    for path in endpoints:
        response = client.post(
            path,
            {**credentials, "password": "test-password-123"},
            HTTP_X_FORWARDED_FOR="203.0.113.99",
        )
        assert response.status_code == 429
        assert response.json()["detail"].startswith("Too many failed")
        assert response["Retry-After"] == "600"
    assert all(attempt.ip_address is None for attempt in AccessAttempt.objects.all())
    assert "wrong" not in " ".join(AccessAttempt.objects.values_list("post_data", flat=True))


def test_lockout_expires_and_successful_login_resets_failures(operator):
    client = APIClient(HTTP_HOST="admin.localhost:8017")
    credentials = {"username": operator.username, "password": "wrong"}
    for _ in range(10):
        client.post("/api/auth/login/", credentials)
    AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=11))
    # The API's independent request-volume limiter is process-local.
    cache.clear()
    assert (
        client.post("/api/auth/login/", {**credentials, "password": "test-password-123"}).status_code == 200
    )
    assert not AccessAttempt.objects.filter(username=operator.username).exists()


def test_one_account_lockout_does_not_block_another(operator, other_operator):
    client = APIClient(HTTP_HOST="admin.localhost:8017")
    for _ in range(10):
        client.post("/login/", {"username": operator.username, "password": "wrong"})
    assert (
        client.post(
            "/login/", {"username": other_operator.username, "password": "test-password-123"}
        ).status_code
        == 302
    )


def test_oversized_public_json_is_rejected_before_field_validation(settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 1024
    client = APIClient(HTTP_HOST="forms.localhost:8017")
    with patch("crm.api.SubmissionSerializer", wraps=SubmissionSerializer) as serializer:
        response = client.post(
            "/api/public/submit/",
            {"ticket": "x", "data": {"name": "x" * 2048}},
            format="json",
            HTTP_ORIGIN=settings.PUBLIC_ORIGIN,
        )
        serializer.assert_not_called()
    assert response.status_code == 400


def test_production_hsts(settings):
    settings.SECURE_HSTS_SECONDS = 3600
    response = Client(HTTP_HOST="admin.localhost:8017").get("/login/", secure=True)
    assert response["Strict-Transport-Security"] == "max-age=3600"
