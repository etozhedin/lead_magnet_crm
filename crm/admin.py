from django.contrib import admin

from .models import Campaign, DistributionLink, FormTemplate, Lead, Visit

admin.site.site_header = "Lead Magnet CRM Operations System"
admin.site.site_title = "Lead Magnet CRM"
admin.site.index_title = "Administration"


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    readonly_fields = ["html", "fields", "created_at"]


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "active", "created_at"]


@admin.register(DistributionLink)
class DistributionLinkAdmin(admin.ModelAdmin):
    list_display = ["campaign", "channel", "token"]
    readonly_fields = ["token"]


@admin.register(Visit, Lead)
class EventAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
