import secrets
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import CampaignForm, TemplateUploadForm
from .models import Campaign, DistributionLink, FormTemplate, Lead, Visit
from .services import VISITOR_COOKIE, campaign_stats, create_campaign, metrics, public_url, record_visit


def operator_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


@operator_required
@require_GET
def dashboard(request):
    campaigns = Campaign.objects.filter(owner=request.user).select_related("template").order_by("-created_at")
    return render(
        request,
        "crm/dashboard.html",
        {
            "campaigns": [{"campaign": c, "stats": campaign_stats(c)} for c in campaigns],
            "stats": metrics(Visit.objects.filter(link__campaign__owner=request.user)),
        },
    )


@operator_required
def templates(request):
    form = TemplateUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        html, fields = form.cleaned_data["file"]
        FormTemplate.objects.create(
            owner=request.user, name=form.cleaned_data["name"], html=html, fields=fields
        )
        messages.success(request, "HTML form uploaded. You can now create a campaign.")
        return redirect("templates")
    return render(
        request,
        "crm/templates.html",
        {
            "form": form,
            "templates": FormTemplate.objects.filter(owner=request.user).order_by("-created_at"),
        },
    )


@operator_required
def campaign_create(request):
    form = CampaignForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        campaign = create_campaign(request.user, form.cleaned_data["template"], form.cleaned_data["name"])
        messages.success(request, "Campaign created. Links for all four channels are ready.")
        return redirect("campaign-detail", pk=campaign.pk)
    return render(request, "crm/campaign_form.html", {"form": form})


@operator_required
@require_GET
def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
    stats = campaign_stats(campaign)
    links = {link.channel: public_url(link) for link in campaign.links.all()}
    leads = list(
        Lead.objects.filter(visit__link__campaign=campaign)
        .select_related("visit__link")
        .order_by("-created_at")[:100]
    )
    for lead in leads:
        # Django's template lookup prefers dictionary keys over methods. A form
        # field called "items" must not shadow dict.items in the template.
        lead.display_fields = list(lead.data.items())
    return render(
        request,
        "crm/campaign_detail.html",
        {
            "campaign": campaign,
            "stats": stats,
            "channels": [{**channel, "url": links[channel["channel"]]} for channel in stats["channels"]],
            "leads": leads,
        },
    )


@operator_required
@require_POST
def campaign_toggle(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk, owner=request.user)
    campaign.active = not campaign.active
    campaign.save(update_fields=["active"])
    return redirect("campaign-detail", pk=pk)


@operator_required
@require_GET
def template_preview(request, pk):
    template = get_object_or_404(FormTemplate, pk=pk, owner=request.user)
    ticket = signing.dumps({"template": template.pk}, salt="preview")
    return render(
        request,
        "crm/preview.html",
        {
            "template": template,
            "src": settings.PUBLIC_ORIGIN + reverse("preview-document", args=[ticket]),
        },
    )


@require_GET
def public_form(request, token):
    link = get_object_or_404(
        DistributionLink.objects.select_related("campaign__template"), token=token, campaign__active=True
    )
    visit, ticket = record_visit(request, link)
    response = render(request, "crm/public.html", {"campaign": link.campaign, "ticket": ticket})
    response.set_signed_cookie(
        VISITOR_COOKIE,
        str(visit.visitor_id),
        salt="visitor",
        max_age=31536000,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )
    response["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; frame-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response


def form_document(template):
    nonce = secrets.token_urlsafe(24)
    # The stored document is sanitized HTML, never a Django template.
    bridge = """
    const form = document.querySelector('form');
    EventTarget.prototype.addEventListener.call(form, 'submit', function(event) {
      event.preventDefault();
      if (!HTMLFormElement.prototype.reportValidity.call(form)) return;
      const data = Object.fromEntries(new FormData(form));
      parent.postMessage({type: 'crm-submit', data: data}, '*');
    });
    """
    html = template.html.replace("</body>", f'<script nonce="{nonce}">{bridge}</script></body>')
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Content-Security-Policy"] = (
        f"sandbox allow-scripts allow-forms; default-src 'none'; script-src 'nonce-{nonce}'; "
        "style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; "
        "base-uri 'none'; object-src 'none'; frame-src 'none'; "
        f"frame-ancestors {settings.PUBLIC_ORIGIN} {settings.ADMIN_ORIGIN}"
    )
    return response


@require_GET
@xframe_options_exempt
def render_document(request, ticket):
    try:
        payload = signing.loads(ticket, salt="submission", max_age=86400)
        visitor = request.get_signed_cookie(VISITOR_COOKIE, salt="visitor")
        if visitor != payload["visitor"]:
            raise signing.BadSignature
        visit = get_object_or_404(
            Visit.objects.select_related("link__campaign__template"),
            id=payload["visit"],
            visitor_id=visitor,
            link__campaign__active=True,
        )
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise Http404
    return form_document(visit.link.campaign.template)


@require_GET
@xframe_options_exempt
def preview_document(request, ticket):
    try:
        payload = signing.loads(ticket, salt="preview", max_age=300)
        template = get_object_or_404(FormTemplate, pk=payload["template"])
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        raise Http404
    return form_document(template)
