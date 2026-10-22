import uuid

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from .html_forms import validate_lead
from .models import Campaign, DistributionLink, Lead, Visit

VISITOR_COOKIE = "crm_visitor"


def create_campaign(owner, template, name):
    if template.owner_id != owner.id:
        raise ValidationError("This template is not available.")
    with transaction.atomic():
        campaign = Campaign.objects.create(owner=owner, template=template, name=name)
        DistributionLink.objects.bulk_create(
            [
                DistributionLink(campaign=campaign, channel=channel)
                for channel in DistributionLink.Channel.values
            ]
        )
    return campaign


def public_url(link):
    return f"{settings.PUBLIC_ORIGIN}/r/{link.token}/"


def record_visit(request, link):
    try:
        visitor_id = uuid.UUID(request.get_signed_cookie(VISITOR_COOKIE, salt="visitor"))
    except (KeyError, ValueError, signing.BadSignature):
        visitor_id = uuid.uuid4()
    visit = Visit.objects.create(link=link, visitor_id=visitor_id)
    ticket = signing.dumps({"visit": str(visit.id), "visitor": str(visitor_id)}, salt="submission")
    return visit, ticket


def accept_lead(ticket, data, visitor_id):
    try:
        payload = signing.loads(ticket, salt="submission", max_age=86400)
        if payload["visitor"] != visitor_id:
            raise signing.BadSignature
        visit = Visit.objects.select_related("link__campaign__template").get(
            id=payload["visit"],
            visitor_id=visitor_id,
            link__campaign__active=True,
        )
    except (signing.BadSignature, Visit.DoesNotExist, KeyError, ValueError, TypeError):
        raise ValidationError("The submission link is invalid or has expired. Open the form again.")
    clean = validate_lead(visit.link.campaign.template.fields, data)
    lead, created = Lead.objects.get_or_create(visit=visit, defaults={"data": clean})
    if not created and lead.data != clean:
        raise ValidationError("An application has already been submitted for this visit.")
    return lead, created


def metrics(visits):
    counts = visits.aggregate(
        visits=Count("pk"), visitors=Count("visitor_id", distinct=True), applications=Count("lead")
    )
    counts["conversion_rate"] = (
        round(counts["applications"] / counts["visits"] * 100, 2) if counts["visits"] else 0
    )
    return counts


def campaign_stats(campaign):
    visits = Visit.objects.filter(link__campaign=campaign)
    return {
        **metrics(visits),
        "channels": [
            {"channel": channel, **metrics(visits.filter(link__channel=channel))}
            for channel in DistributionLink.Channel.values
        ],
    }
