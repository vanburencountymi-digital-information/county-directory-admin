from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "ts", "actor", "action", "entity_type", "tenant_id")
    list_filter = ("tenant_id", "action", "entity_type")
    readonly_fields = ("tenant_id", "actor", "action", "entity_type", "entity_id", "details", "ts")
