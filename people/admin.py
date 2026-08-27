from django.contrib import admin

from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("full_name", "tenant_id", "email_public", "show_in_directory", "archived_at")
    list_filter = ("tenant_id", "show_in_directory")
    search_fields = ("full_name", "email_public", "name_last", "employee_id")
