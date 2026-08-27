import uuid

from django.db import models
from django.utils import timezone


def derive_full_name(name_first, name_last, full_name=None):
    if full_name is not None and str(full_name).strip():
        return str(full_name).strip()
    parts = [p for p in [(name_first or "").strip(), (name_last or "").strip()] if p]
    return " ".join(parts) if parts else ""


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.TextField()
    employee_id = models.TextField(null=True, blank=True)
    name_first = models.TextField(null=True, blank=True)
    name_middle = models.TextField(null=True, blank=True)
    name_last = models.TextField(null=True, blank=True)
    name_suffix = models.TextField(null=True, blank=True)
    full_name = models.TextField(null=True, blank=True)
    email_public = models.TextField(null=True, blank=True)
    phone_public = models.TextField(null=True, blank=True)
    phone_public_ext = models.TextField(null=True, blank=True)
    job_title = models.TextField(null=True, blank=True)
    person_key = models.TextField(null=True, blank=True)
    role = models.CharField(max_length=255, null=True, blank=True)
    show_in_directory = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "people_person"
        indexes = [
            models.Index(fields=["tenant_id", "name_last", "name_first"]),
            models.Index(fields=["tenant_id", "person_key"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "employee_id"],
                name="uq_people_tenant_employee",
                condition=models.Q(employee_id__isnull=False) & ~models.Q(employee_id=""),
            ),
            models.UniqueConstraint(
                fields=["person_key"],
                name="uq_people_person_key",
                condition=models.Q(person_key__isnull=False) & ~models.Q(person_key=""),
            ),
        ]
        permissions = [
            ("trigger_wordpress_sync", "Can trigger WordPress sync for a person"),
        ]

    def save(self, *args, **kwargs):
        self.full_name = derive_full_name(self.name_first, self.name_last, self.full_name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name or str(self.id)
