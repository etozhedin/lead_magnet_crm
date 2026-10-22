from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import Campaign, FormTemplate, Lead
from .serializers import (
    CampaignSerializer,
    CampaignStatsSerializer,
    CsrfSerializer,
    LeadSerializer,
    LoginSerializer,
    SubmissionResultSerializer,
    SubmissionSerializer,
    TemplateSerializer,
    UserSerializer,
)
from .services import VISITOR_COOKIE, accept_lead, campaign_stats


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class SubmissionThrottle(AnonRateThrottle):
    scope = "submit"


class CsrfView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=CsrfSerializer, tags=["Authentication"])
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer}, tags=["Authentication"])
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if not user or not user.is_staff:
            return Response({"detail": "Invalid credentials."}, status=400)
        login(request, user)
        return Response({"username": user.username})


class LogoutView(APIView):
    @extend_schema(request=None, responses={204: None}, tags=["Authentication"])
    def post(self, request):
        logout(request)
        return Response(status=204)


class MeView(APIView):
    @extend_schema(responses=UserSerializer, tags=["Authentication"])
    def get(self, request):
        return Response({"username": request.user.username})


@extend_schema_view(
    list=extend_schema(tags=["Forms"]),
    create=extend_schema(tags=["Forms"]),
    retrieve=extend_schema(tags=["Forms"]),
)
class TemplateViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = TemplateSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FormTemplate.objects.none()
        return FormTemplate.objects.filter(owner=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CampaignViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CampaignSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Campaign.objects.none()
        return (
            Campaign.objects.filter(owner=self.request.user).prefetch_related("links").order_by("-created_at")
        )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @extend_schema(responses=CampaignStatsSerializer)
    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        return Response(campaign_stats(self.get_object()))


class LeadViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LeadSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Lead.objects.none()
        leads = (
            Lead.objects.filter(visit__link__campaign__owner=self.request.user)
            .select_related("visit__link")
            .order_by("-created_at")
        )
        campaign = self.request.query_params.get("campaign")
        if campaign:
            try:
                campaign = int(campaign)
            except ValueError:
                raise serializers.ValidationError({"campaign": "Expected an integer."})
            leads = leads.filter(visit__link__campaign_id=campaign)
        return leads


class SubmitView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [SubmissionThrottle]

    @extend_schema(
        request=SubmissionSerializer,
        responses={201: SubmissionResultSerializer, 200: SubmissionResultSerializer},
        auth=[],
        tags=["Public forms"],
    )
    def post(self, request):
        if request.headers.get("Origin") != settings.PUBLIC_ORIGIN:
            return Response({"detail": "Invalid request origin."}, status=403)
        serializer = SubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lead, created = accept_lead(
                **serializer.validated_data,
                visitor_id=request.get_signed_cookie(VISITOR_COOKIE, default="", salt="visitor"),
            )
        except DjangoValidationError as exc:
            return Response({"errors": getattr(exc, "message_dict", None) or exc.messages}, status=400)
        return Response(
            {"id": lead.id, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
