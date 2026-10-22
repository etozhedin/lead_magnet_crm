import pytest
import time
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.core import signing
from rest_framework.test import APIClient

from crm.models import Campaign, DistributionLink, FormTemplate, Lead, Visit

pytestmark = pytest.mark.django_db
PUBLIC = {"HTTP_HOST": "forms.localhost:8017"}
ORIGIN = {"HTTP_ORIGIN": "http://forms.localhost:8017"}
DATA = {"name": "Alice", "email": "alice@example.com"}


def open_form(client, link):
    response = client.get(f"/r/{link.token}/")
    assert response.status_code == 200
    return response.context["ticket"]


def submit(client, ticket, data=DATA):
    return client.post("/api/public/submit/", {"ticket": ticket, "data": data}, format="json", **ORIGIN)


@pytest.mark.parametrize("url", ["/", "/templates/", "/campaigns/new/"])
def test_ui_requires_login(url):
    assert Client(HTTP_HOST="admin.localhost:8017").get(url).status_code == 302


@pytest.mark.parametrize(
    "url",
    ["/api/templates/", "/api/campaigns/", "/api/leads/", "/api/auth/me/", "/api/schema/", "/api/docs/"],
)
def test_api_requires_authentication(url):
    assert APIClient(HTTP_HOST="admin.localhost:8017").get(url).status_code == 403


def test_non_staff_is_not_operator():
    user = get_user_model().objects.create_user("visitor", password="abc")
    client = APIClient(HTTP_HOST="admin.localhost:8017")
    client.force_login(user)
    assert client.get("/api/leads/").status_code == 403
    assert client.get("/").status_code == 403


def test_login_requires_csrf_and_logout_ends_session(operator):
    client = APIClient(enforce_csrf_checks=True, HTTP_HOST="admin.localhost:8017")
    credentials = {"username": "operator", "password": "test-password-123"}
    assert client.post("/api/auth/login/", credentials).status_code == 403
    csrf = client.get("/api/auth/csrf/").json()["csrfToken"]
    assert (
        client.post(
            "/api/auth/login/", {**credentials, "password": "wrong"}, HTTP_X_CSRFTOKEN=csrf
        ).status_code
        == 400
    )
    assert client.post("/api/auth/login/", credentials, HTTP_X_CSRFTOKEN=csrf).status_code == 200
    assert client.get("/api/auth/me/").json() == {"username": "operator"}
    csrf = client.get("/api/auth/csrf/").json()["csrfToken"]
    assert client.post("/api/auth/logout/").status_code == 403
    assert client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=csrf).status_code == 204
    assert client.get("/api/leads/").status_code == 403


def test_login_rejects_non_staff():
    get_user_model().objects.create_user("visitor", password="abc")
    client = APIClient(enforce_csrf_checks=True, HTTP_HOST="admin.localhost:8017")
    csrf = client.get("/api/auth/csrf/").json()["csrfToken"]
    assert (
        client.post(
            "/api/auth/login/", {"username": "visitor", "password": "abc"}, HTTP_X_CSRFTOKEN=csrf
        ).status_code
        == 400
    )


def test_upload_campaign_and_links(api_client, upload):
    response = api_client.post("/api/templates/", {"name": "Guide", "file": upload}, format="multipart")
    assert response.status_code == 201, response.data
    assert "html" not in response.data
    response = api_client.post(
        "/api/campaigns/", {"name": "Launch", "template": response.data["id"]}, format="json"
    )
    assert response.status_code == 201, response.data
    assert {link["channel"] for link in response.data["links"]} == {"instagram", "x", "youtube", "threads"}
    assert all(link["url"].startswith("http://forms.localhost:8017/r/") for link in response.data["links"])
    assert Campaign.objects.count() == 1
    assert DistributionLink.objects.count() == 4


@pytest.mark.parametrize(
    "name,content",
    [
        ("bad.txt", b'<form><input name="a"></form>'),
        ("bad.html", b"no form"),
        ("bad.html", b"\xff"),
        ("large.html", b"x" * 524289),
    ],
)
def test_bad_upload_rejected(api_client, name, content):
    response = api_client.post(
        "/api/templates/", {"name": "Bad", "file": SimpleUploadedFile(name, content)}, format="multipart"
    )
    assert response.status_code == 400
    assert not FormTemplate.objects.exists()


def test_ownership(api_client, other_operator, campaign, template):
    other = APIClient(HTTP_HOST="admin.localhost:8017")
    other.force_login(other_operator)
    for resource, pk in [("campaigns", campaign.pk), ("templates", template.pk)]:
        assert other.get(f"/api/{resource}/{pk}/").status_code == 404
        assert other.get(f"/api/{resource}/").data["count"] == 0
    assert other.get(f"/api/campaigns/{campaign.pk}/stats/").status_code == 404
    assert (
        other.post("/api/campaigns/", {"name": "Stolen", "template": template.pk}, format="json").status_code
        == 400
    )
    assert other.get(f"/templates/{template.pk}/preview/").status_code == 404
    assert other.get(f"/campaigns/{campaign.pk}/").status_code == 404


def test_admin_writes_require_csrf(operator, template):
    client = APIClient(enforce_csrf_checks=True, HTTP_HOST="admin.localhost:8017")
    client.force_login(operator)
    assert client.post("/api/campaigns/", {"name": "No", "template": template.pk}).status_code == 403


def test_end_to_end_metrics_and_attribution(api_client, public_client, campaign, other_operator):
    instagram = campaign.links.get(channel="instagram")
    youtube = campaign.links.get(channel="youtube")
    first = open_form(public_client, instagram)
    second = open_form(public_client, youtube)
    # Submitting the older tab attributes to Instagram, not the latest YouTube visit.
    response = submit(public_client, first)
    assert response.status_code == 201, response.data
    assert submit(public_client, first).status_code == 200
    assert submit(public_client, first, {**DATA, "name": "Changed"}).status_code == 400
    assert Lead.objects.count() == 1
    assert Lead.objects.get().visit.link_id == instagram.id
    other_browser = APIClient(**PUBLIC)
    open_form(other_browser, instagram)
    assert submit(other_browser, second).status_code == 400  # Ticket bound to browser.
    result = api_client.get(f"/api/campaigns/{campaign.pk}/stats/").data
    assert result["visits"] == 3
    assert result["visitors"] == 2
    assert result["applications"] == 1
    assert result["conversion_rate"] == 33.33
    channels = {row["channel"]: row for row in result["channels"]}
    assert channels["instagram"]["visits"] == 2
    assert channels["instagram"]["conversion_rate"] == 50
    assert channels["youtube"]["visitors"] == 1
    assert channels["x"]["conversion_rate"] == 0
    assert api_client.get("/api/leads/").data["results"][0]["data"] == DATA
    other = APIClient(HTTP_HOST="admin.localhost:8017")
    other.force_login(other_operator)
    assert other.get("/api/leads/").data["count"] == 0
    assert other.get(f"/api/leads/{Lead.objects.get().pk}/").status_code == 404


def test_submission_failure_and_pause(public_client, api_client, campaign):
    ticket = open_form(public_client, campaign.links.first())
    assert submit(public_client, ticket, {"name": "", "email": "bad"}).status_code == 400
    assert submit(public_client, ticket, {**DATA, "channel": "x"}).status_code == 400
    assert submit(public_client, ticket + "tampered").status_code == 400
    assert (
        public_client.post("/api/public/submit/", {"ticket": ticket, "data": DATA}, format="json").status_code
        == 403
    )
    assert not Lead.objects.exists()
    assert (
        api_client.patch(f"/api/campaigns/{campaign.pk}/", {"active": False}, format="json").status_code
        == 200
    )
    assert submit(public_client, ticket).status_code == 400
    assert public_client.get(f"/r/{campaign.links.first().token}/").status_code == 404


def test_host_boundary(api_client, public_client, campaign):
    ticket = open_form(public_client, campaign.links.first())
    for path in ["/api/leads/", "/api/auth/csrf/", "/api/campaigns/", "/admin/", "/login/"]:
        assert api_client.get(path, **PUBLIC).status_code == 404
    assert api_client.get(f"/r/{campaign.links.first().token}/").status_code == 404
    assert api_client.get(f"/public/render/{ticket}/").status_code == 404
    assert api_client.post("/api/public/submit/", {}, format="json", **ORIGIN).status_code == 404


def test_frame_csp_and_preview_no_visits(api_client, public_client, campaign):
    preview = api_client.get(f"/templates/{campaign.template_id}/preview/")
    ticket = preview.context["src"].rsplit("/", 2)[1]
    document = public_client.get(f"/public/preview/{ticket}/")
    assert document.status_code == 200
    assert not Visit.objects.exists()
    assert submit(public_client, ticket).status_code == 400
    ticket = open_form(public_client, campaign.links.first())
    document = public_client.get(f"/public/render/{ticket}/")
    assert document.status_code == 200
    assert "sandbox allow-scripts" in document["Content-Security-Policy"]
    assert "connect-src 'none'" in document["Content-Security-Policy"]
    assert "form-action 'none'" in document["Content-Security-Policy"]
    assert "X-Frame-Options" not in document
    assert "nonce=" in document.content.decode()
    assert Visit.objects.count() == 1


def test_immutable_campaign_template(api_client, campaign, operator):
    template = FormTemplate.objects.create(owner=operator, name="Other", html="x", fields=[])
    assert (
        api_client.patch(
            f"/api/campaigns/{campaign.pk}/", {"template": template.pk}, format="json"
        ).status_code
        == 400
    )


def test_empty_stats(api_client, campaign):
    result = api_client.get(f"/api/campaigns/{campaign.pk}/stats/").data
    assert result["visits"] == result["visitors"] == result["applications"] == result["conversion_rate"] == 0


@pytest.mark.parametrize("channel", DistributionLink.Channel.values)
def test_each_channel_attributes_applications(public_client, api_client, campaign, channel):
    ticket = open_form(public_client, campaign.links.get(channel=channel))
    assert submit(public_client, ticket).status_code == 201
    lead = Lead.objects.get()
    assert lead.visit.link.channel == channel
    assert lead.visit.link.campaign_id == campaign.pk
    stats = api_client.get(f"/api/campaigns/{campaign.pk}/stats/").data
    assert stats["applications"] == 1
    assert stats["conversion_rate"] == 100
    for row in stats["channels"]:
        assert row["applications"] == (1 if row["channel"] == channel else 0)


def test_expired_ticket_and_tampered_cookie_cannot_submit(public_client, campaign):
    ticket = open_form(public_client, campaign.links.first())
    payload = signing.loads(ticket, salt="submission")
    with patch("django.core.signing.time.time", return_value=time.time() - 86401):
        expired = signing.dumps(payload, salt="submission")
    assert submit(public_client, expired).status_code == 400
    public_client.cookies["crm_visitor"] = "tampered"
    assert submit(public_client, ticket).status_code == 400
    assert not Lead.objects.exists()


@pytest.mark.parametrize("alias", ["127.0.0.1", "localhost"])
def test_local_address_redirects_to_admin(alias, settings):
    settings.DEBUG = True
    response = Client(HTTP_HOST=f"{alias}:8017").get("/login/?next=%2Fcampaigns%2Fnew%2F")
    assert response.status_code == 302
    assert response["Location"] == "http://admin.localhost:8017/login/?next=%2Fcampaigns%2Fnew%2F"
    assert "sessionid" not in response.cookies


def test_local_public_link_redirect_preserves_attribution(public_client, campaign, settings):
    settings.DEBUG = True
    link = campaign.links.get(channel="instagram")
    response = public_client.get(f"/r/{link.token}/?source=test", HTTP_HOST="127.0.0.1:8017")
    assert response.status_code == 302
    assert response["Location"] == f"http://forms.localhost:8017/r/{link.token}/?source=test"
    assert not Visit.objects.exists()


def test_loopback_alias_cannot_serve_admin_or_forward_writes(settings):
    client = Client(HTTP_HOST="127.0.0.1:8017")
    settings.DEBUG = True
    assert client.post("/api/auth/login/", {"username": "operator"}).status_code == 404
    settings.DEBUG = False
    assert client.get("/api/leads/").status_code == 404
