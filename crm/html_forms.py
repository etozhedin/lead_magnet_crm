import re

from bs4 import BeautifulSoup
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator

MAX_HTML_BYTES = 512 * 1024
NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
ALLOWED_TAGS = set(
    "html head body title meta style div span p section article header footer main h1 h2 h3 h4 h5 h6 form input textarea select option optgroup button label fieldset legend small strong em b i u br hr ul ol li a img table thead tbody tr td th dl dt dd".split()
)
ALLOWED_ATTRS = set(
    "class id style name type value placeholder required minlength maxlength min max step pattern checked selected disabled multiple for rows cols autocomplete aria-label role alt width height".split()
)
INPUT_TYPES = {"text", "email", "tel", "url", "number", "date", "checkbox", "radio", "hidden"}


def parse_html(raw):
    if len(raw.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValidationError("The HTML file must not exceed 512 KiB.")
    soup = BeautifulSoup(raw, "html5lib")
    forms = soup.find_all("form")
    if len(forms) != 1:
        raise ValidationError("The HTML document must contain exactly one <form>.")
    fields = []
    seen = set()
    for node in forms[0].find_all(["input", "textarea", "select"]):
        kind = node.get("type", "text").lower() if node.name == "input" else node.name
        if kind in {"submit", "button", "reset"}:
            continue
        if kind not in INPUT_TYPES | {"textarea", "select"}:
            raise ValidationError(f"Field type {kind} is not supported.")
        name = node.get("name", "")
        if not NAME.fullmatch(name) or name in seen:
            raise ValidationError(
                "Each field needs a unique name using ASCII letters, digits and underscores."
            )
        if node.has_attr("multiple") or node.has_attr("disabled"):
            raise ValidationError("Multiple and disabled fields are not supported.")
        seen.add(name)
        options = (
            [o.get("value", o.get_text()) for o in node.find_all("option")] if kind == "select" else None
        )
        if kind in {"checkbox", "radio"}:
            options = [node.get("value", "on")]
        fields.append({"name": name, "type": kind, "required": node.has_attr("required"), "options": options})
    if not fields or len(fields) > 30:
        raise ValidationError("The form must contain between 1 and 30 fields.")
    # Allowlist HTML; no uploaded code is ever executed or interpolated as a template.
    for node in list(soup.find_all(True)):
        if node.parent is None:
            continue
        if node.name not in ALLOWED_TAGS:
            node.decompose()
            continue
        for attr in list(node.attrs):
            if attr not in ALLOWED_ATTRS:
                del node[attr]
    surviving_form = soup.find("form")
    if surviving_form is None or not seen.issubset(
        {n.get("name") for n in surviving_form.find_all(["input", "textarea", "select"])}
    ):
        raise ValidationError("The form or its fields are inside an unsupported HTML element.")
    return str(soup), fields


def validate_lead(fields, data):
    if not isinstance(data, dict) or set(data) - {f["name"] for f in fields}:
        raise ValidationError("The submission contains unknown fields.")
    result = {}
    errors = {}
    for field in fields:
        name = field["name"]
        value = data.get(name, "")
        if not isinstance(value, str) or len(value) > 4000:
            errors[name] = "Expected a string of at most 4000 characters."
            continue
        value = value.strip()
        if field["required"] and not value:
            errors[name] = "This field is required."
            continue
        if value:
            try:
                if field["type"] == "email":
                    validate_email(value)
                elif field["type"] == "url":
                    URLValidator(schemes=["http", "https"])(value)
                elif field["type"] == "number":
                    from decimal import Decimal, InvalidOperation

                    try:
                        if not Decimal(value).is_finite():
                            raise InvalidOperation
                    except InvalidOperation:
                        raise ValidationError("Enter a valid number.")
                elif field["type"] == "date":
                    from datetime import date

                    try:
                        date.fromisoformat(value)
                    except ValueError:
                        raise ValidationError("Enter a valid date in YYYY-MM-DD format.")
                if field["options"] is not None and value not in field["options"]:
                    raise ValidationError("Invalid value.")
            except ValidationError as exc:
                errors[name] = exc.messages[0]
        result[name] = value
    if errors:
        raise ValidationError(errors)
    return result
