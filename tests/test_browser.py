from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest
from django.db import connections
from playwright.sync_api import expect, sync_playwright

from crm.html_forms import parse_html
from crm.models import Campaign, FormTemplate, Lead, Visit
from crm.services import create_campaign

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def browser_context(live_server, settings, operator):
    port = urlsplit(live_server.url).port
    settings.ADMIN_ORIGIN = f"http://admin.localhost:{port}"
    settings.PUBLIC_ORIGIN = f"http://forms.localhost:{port}"
    settings.CSRF_TRUSTED_ORIGINS = [settings.ADMIN_ORIGIN]
    settings.ALLOWED_HOSTS = ["localhost", "admin.localhost", "forms.localhost"]
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chromium", args=["--host-resolver-rules=MAP *.localhost 127.0.0.1"]
        )
        context = browser.new_context()
        yield context
        context.close()
        browser.close()


def db_call(fn):
    # Playwright's sync API owns an event loop on the test thread. Keep ORM calls
    # on a separate synchronous thread, without disabling Django's async guard.
    def run():
        try:
            return fn()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(run).result()


def login(page, settings):
    page.goto(settings.ADMIN_ORIGIN + "/login/")
    page.locator("[name=username]").fill("operator")
    page.locator("[name=password]").fill("test-password-123")
    page.get_by_role("button", name="Sign in →").click()
    expect(page.get_by_role("heading", name="Your campaigns")).to_be_visible()


def test_operator_to_conversion(browser_context, settings, operator):
    page = browser_context.new_page()
    login(page, settings)
    page.goto(settings.ADMIN_ORIGIN + "/templates/")
    page.get_by_label("Form name").fill("Content guide")
    page.get_by_label("HTML file").set_input_files(ROOT / "examples/guide.html")
    page.get_by_role("button", name="Upload HTML →").click()
    expect(page.get_by_text("HTML form uploaded.", exact=False)).to_be_visible()
    page.goto(settings.ADMIN_ORIGIN + "/campaigns/new/")
    page.get_by_label("Campaign name").fill("Guide launch")
    page.get_by_label("HTML template").select_option(label="Content guide")
    page.get_by_role("button", name="Create campaign →").click()
    expect(page.get_by_role("heading", name="Guide launch")).to_be_visible()
    token = db_call(lambda: Campaign.objects.get().links.get(channel="instagram").token)
    public = browser_context.new_page()
    public.goto(f"{settings.PUBLIC_ORIGIN}/r/{token}/")
    frame = public.frame_locator("#lead-frame")
    frame.get_by_label("Your name").fill("Alice")
    frame.get_by_label("Email").fill("alice@example.com")
    frame.get_by_role("button", name="Get the guide →").click()
    expect(public.get_by_role("heading", name="Application submitted")).to_be_visible()
    page.reload()
    expect(page.get_by_text("alice@example.com", exact=False)).to_be_visible()
    assert db_call(lambda: (Lead.objects.count(), Visit.objects.count())) == (1, 1)
    assert db_call(lambda: Lead.objects.get().visit.link.channel) == "instagram"
    (ROOT / "test-results").mkdir(exist_ok=True)
    page.screenshot(path=str(ROOT / "test-results/campaign.png"), full_page=True)


def test_uploaded_html_isolation(browser_context, settings, operator):
    html, fields = parse_html("""<html><body><script>window.pwned=true;fetch('/api/leads/')</script>
    <style>body {background: white} @import url("https://attacker.invalid/leak");</style>
    <form action="/api/campaigns/" target="_top"><input name="email" type="email" required>
    <button>Send</button></form><img src="https://attacker.invalid/pixel"></body></html>""")

    def create_hostile():
        template = FormTemplate.objects.create(owner=operator, name="Hostile", html=html, fields=fields)
        return create_campaign(operator, template, "Isolation").links.first().token

    token = db_call(create_hostile)
    page = browser_context.new_page()
    login(page, settings)
    public = browser_context.new_page()
    requests = []
    public.on("request", lambda request: requests.append(request.url))
    public.goto(f"{settings.PUBLIC_ORIGIN}/r/{token}/")
    expect(public.frame_locator("#lead-frame").locator("input")).to_be_visible()
    frame = public.frames[1]
    assert frame.evaluate("typeof window.pwned") == "undefined"
    assert (
        frame.evaluate("""() => {try {return document.cookie} catch(e) {return e.name}}""") == "SecurityError"
    )
    assert (
        frame.evaluate("""() => {try {return parent.document.title} catch(e) {return e.name}}""")
        == "SecurityError"
    )
    assert (
        frame.evaluate(
            "async url => {try {await fetch(url, {credentials: 'include'}); return 'unsafe'} catch(e) {return 'blocked'}}",
            settings.ADMIN_ORIGIN + "/api/leads/",
        )
        == "blocked"
    )
    # Administrative session cookies are never shared with the forms host.
    cookies = browser_context.cookies(settings.PUBLIC_ORIGIN)
    assert "sessionid" not in {cookie["name"] for cookie in cookies}
    assert all("attacker.invalid" not in url for url in requests)
    # Direct navigation to the raw document retains the response-level sandbox.
    raw_url = frame.url
    public.goto(raw_url)
    assert (
        public.evaluate("""() => {try {return document.cookie} catch(e) {return e.name}}""")
        == "SecurityError"
    )
    denied = browser_context.new_page()
    assert denied.goto(settings.PUBLIC_ORIGIN + "/api/leads/").status == 404
    assert not db_call(lambda: Lead.objects.exists())


def test_custom_field_names_do_not_break_submission_or_crm(browser_context, settings, operator):
    html, fields = parse_html("""<form>
      <input name="items" required>
      <input name="addEventListener" required>
      <input name="reportValidity" required>
      <button type="submit">Submit application</button>
    </form>""")

    def create_custom():
        template = FormTemplate.objects.create(owner=operator, name="Custom fields", html=html, fields=fields)
        campaign = create_campaign(operator, template, "Custom field campaign")
        return campaign.pk, campaign.links.get(channel="threads").token

    campaign_id, token = db_call(create_custom)
    public = browser_context.new_page()
    public.goto(f"{settings.PUBLIC_ORIGIN}/r/{token}/")
    frame = public.frame_locator("#lead-frame")
    payload = "<script>window.pwned=true</script>"
    frame.locator("[name=items]").fill(payload)
    frame.locator("[name=addEventListener]").fill("First field")
    frame.locator("[name=reportValidity]").fill("Second field")
    frame.get_by_role("button", name="Submit application").click()
    expect(public.get_by_role("heading", name="Application submitted")).to_be_visible()
    page = browser_context.new_page()
    login(page, settings)
    page.goto(f"{settings.ADMIN_ORIGIN}/campaigns/{campaign_id}/")
    expect(page.get_by_text(payload, exact=False)).to_be_visible()
    assert page.evaluate("typeof window.pwned") == "undefined"
