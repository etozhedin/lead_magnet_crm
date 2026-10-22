from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .html_forms import MAX_HTML_BYTES, parse_html
from .models import Campaign, FormTemplate


class OperatorAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("Only operators can access this application.")


class TemplateUploadForm(forms.Form):
    name = forms.CharField(label="Form name", max_length=160)
    file = forms.FileField(label="HTML file")

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".html") or upload.size > MAX_HTML_BYTES:
            raise forms.ValidationError("Upload an .html file of at most 512 KiB.")
        try:
            return parse_html(upload.read().decode("utf-8"))
        except UnicodeDecodeError:
            raise forms.ValidationError("The file must use UTF-8 encoding.")


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "template"]
        labels = {"name": "Campaign name", "template": "HTML template"}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = FormTemplate.objects.filter(owner=owner)
