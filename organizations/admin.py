from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant_id", "org_type", "slug", "archived_at")
    list_filter = ("tenant_id", "org_type")
    search_fields = ("name", "slug")
