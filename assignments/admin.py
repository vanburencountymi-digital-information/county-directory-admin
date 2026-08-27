from django.contrib import admin

from .models import Assignment


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant_id", "org", "person", "job_title", "seat_no")
    list_filter = ("tenant_id",)
