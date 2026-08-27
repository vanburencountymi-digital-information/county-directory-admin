from django.contrib import admin

from .models import TenantMembership, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    ordering = ("email",)
    list_display = ("email", "person", "is_staff", "is_active")
    search_fields = ("email",)
    filter_horizontal = ("groups", "user_permissions")


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant_id")
    list_filter = ("tenant_id",)
