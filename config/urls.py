from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from crm import api, views
from crm.forms import OperatorAuthenticationForm
from crm.health import health

router = DefaultRouter()
router.register("templates", api.TemplateViewSet, basename="api-template")
router.register("campaigns", api.CampaignViewSet, basename="api-campaign")
router.register("leads", api.LeadViewSet, basename="api-lead")

urlpatterns = [
    path("health/", health, name="health"),
    path("", views.dashboard, name="dashboard"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="crm/login.html", authentication_form=OperatorAuthenticationForm
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("templates/", views.templates, name="templates"),
    path("templates/<int:pk>/preview/", views.template_preview, name="template-preview"),
    path("campaigns/new/", views.campaign_create, name="campaign-create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign-detail"),
    path("campaigns/<int:pk>/toggle/", views.campaign_toggle, name="campaign-toggle"),
    path("admin/", admin.site.urls),
    path("api/auth/csrf/", api.CsrfView.as_view()),
    path("api/auth/login/", api.LoginView.as_view()),
    path("api/auth/logout/", api.LogoutView.as_view()),
    path("api/auth/me/", api.MeView.as_view()),
    path("api/public/submit/", api.SubmitView.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("api/", include(router.urls)),
    path("r/<uuid:token>/", views.public_form, name="public-form"),
    path("public/render/<str:ticket>/", views.render_document, name="render-document"),
    path("public/preview/<str:ticket>/", views.preview_document, name="preview-document"),
]
