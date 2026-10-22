import pytest
from django.core.exceptions import ValidationError

from crm.html_forms import MAX_HTML_BYTES, parse_html, validate_lead


def test_sanitizer_removes_active_content_and_network_attributes():
    html, fields = parse_html("""<html><head><base href="https://evil.test"><script>alert(1)</script></head>
    <body onload="alert(1)"><iframe src="/api/leads/"></iframe><object data="/admin/"></object>
    <form action="https://evil.test" target="_top"><input name="email" type="email" required
    onfocus="fetch('/admin/')"><button formaction="https://evil.test">Send</button></form>
    <img src="https://evil.test/pixel"><a href="javascript:alert(1)">Click</a></body></html>""")
    for forbidden in [
        "<script",
        "<iframe",
        "<object",
        "<base",
        "onload=",
        "onfocus=",
        "formaction=",
        "src=",
        "href=",
        "target=",
        "action=",
    ]:
        assert forbidden not in html
    assert fields == [{"name": "email", "type": "email", "required": True, "options": None}]


@pytest.mark.parametrize(
    "html",
    [
        "<p>No form</p>",
        "<form></form><form></form>",
        "<form></form>",
        "<form><input></form>",
        '<form><input name="a"><input name="a"></form>',
        '<form><input name="file" type="file"></form>',
        '<form><select name="a" multiple><option>A</option></select></form>',
        '<form><input name="a" disabled></form>',
    ],
)
def test_rejects_invalid_html(html):
    with pytest.raises(ValidationError):
        parse_html(html)


def test_rejects_large_document():
    with pytest.raises(ValidationError):
        parse_html("a" * (MAX_HTML_BYTES + 1))


@pytest.mark.parametrize(
    "data", [{}, {"email": "bad"}, {"email": "ok@example.com", "admin": "1"}, {"email": ["bad"]}]
)
def test_server_validates_fields(data):
    _, fields = parse_html('<form><input name="email" type="email" required></form>')
    with pytest.raises(ValidationError):
        validate_lead(fields, data)


def test_select_and_checkbox_values():
    _, fields = parse_html(
        '<form><select name="plan"><option value="a">A</option></select><input name="consent" type="checkbox" required></form>'
    )
    assert validate_lead(fields, {"plan": "a", "consent": "on"})["consent"] == "on"
    with pytest.raises(ValidationError):
        validate_lead(fields, {"plan": "b", "consent": "on"})


@pytest.mark.parametrize(
    "kind,value",
    [("number", "NaN"), ("number", "abc"), ("date", "2025-99-99"), ("url", "javascript:alert(1)")],
)
def test_typed_values(kind, value):
    _, fields = parse_html(f'<form><input name="value" type="{kind}"></form>')
    with pytest.raises(ValidationError):
        validate_lead(fields, {"value": value})
