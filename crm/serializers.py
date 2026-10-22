from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .html_forms import MAX_HTML_BYTES, parse_html
from .models import Campaign, DistributionLink, FormTemplate, Lead
from .services import create_campaign, public_url


class TemplateSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = FormTemplate
        fields = ["id", "name", "file", "fields", "created_at"]
        read_only_fields = ["fields", "created_at"]

    def validate_file(self, upload):
        if not upload.name.lower().endswith(".html") or upload.size > MAX_HTML_BYTES:
            raise serializers.ValidationError("Upload a single .html file of at most 512 KiB.")
        try:
            return parse_html(upload.read().decode("utf-8"))
        except UnicodeDecodeError:
            raise serializers.ValidationError("The file must use UTF-8 encoding.")
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

    def create(self, validated_data):
        html, fields = validated_data.pop("file")
        return FormTemplate.objects.create(html=html, fields=fields, **validated_data)


class LinkSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = DistributionLink
        fields = ["channel", "token", "url"]

    def get_url(self, obj) -> str:
        return public_url(obj)


class CampaignSerializer(serializers.ModelSerializer):
    links = LinkSerializer(many=True, read_only=True)

    class Meta:
        model = Campaign
        fields = ["id", "name", "template", "active", "created_at", "links"]
        read_only_fields = ["created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        self.fields["template"].queryset = (
            FormTemplate.objects.filter(owner=request.user)
            if request and request.user.is_authenticated
            else FormTemplate.objects.none()
        )

    def validate(self, attrs):
        if self.instance and "template" in attrs and attrs["template"].pk != self.instance.template_id:
            raise serializers.ValidationError(
                "The campaign template cannot be changed; create a new campaign."
            )
        return attrs

    def create(self, validated_data):
        active = validated_data.pop("active", True)
        campaign = create_campaign(**validated_data)
        if not active:
            campaign.active = False
            campaign.save(update_fields=["active"])
        return campaign


class LeadSerializer(serializers.ModelSerializer):
    campaign = serializers.IntegerField(source="visit.link.campaign_id", read_only=True)
    channel = serializers.CharField(source="visit.link.channel", read_only=True)

    class Meta:
        model = Lead
        fields = ["id", "campaign", "channel", "data", "created_at"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=256)


class UserSerializer(serializers.Serializer):
    username = serializers.CharField()


class CsrfSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class SubmissionSerializer(serializers.Serializer):
    ticket = serializers.CharField(max_length=1000)
    data = serializers.DictField(child=serializers.CharField(max_length=4000, allow_blank=True))

    def validate_data(self, value):
        if len(value) > 30:
            raise serializers.ValidationError("A maximum of 30 fields is allowed.")
        return value


class SubmissionResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    created = serializers.BooleanField()


class MetricsSerializer(serializers.Serializer):
    visits = serializers.IntegerField()
    visitors = serializers.IntegerField()
    applications = serializers.IntegerField()
    conversion_rate = serializers.FloatField()


class ChannelMetricsSerializer(MetricsSerializer):
    channel = serializers.ChoiceField(choices=DistributionLink.Channel.choices)


class CampaignStatsSerializer(MetricsSerializer):
    channels = ChannelMetricsSerializer(many=True)
