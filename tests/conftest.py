import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from crm.html_forms import parse_html
from crm.models import FormTemplate
from crm.services import create_campaign

HTML = '<html><body><form><input name="name" required><input name="email" type="email" required><button>Send</button></form></body></html>'


@pytest.fixture(autouse=True)
def clean_throttles():
    cache.clear()


@pytest.fixture
def operator(db):
    return get_user_model().objects.create_user("operator", password="test-password-123", is_staff=True)


@pytest.fixture
def other_operator(db):
    return get_user_model().objects.create_user("other", password="test-password-123", is_staff=True)


@pytest.fixture
def api_client(operator):
    client = APIClient(HTTP_HOST="admin.localhost:8017")
    client.force_login(operator)
    return client


@pytest.fixture
def template(operator):
    html, fields = parse_html(HTML)
    return FormTemplate.objects.create(owner=operator, name="Guide", html=html, fields=fields)


@pytest.fixture
def campaign(operator, template):
    return create_campaign(operator, template, "Launch")


@pytest.fixture
def upload():
    return SimpleUploadedFile("form.html", HTML.encode(), content_type="text/html")


@pytest.fixture
def public_client():
    return APIClient(HTTP_HOST="forms.localhost:8017")
