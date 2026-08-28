import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


def compose_name(name_first=None, name_middle=None, name_last=None, name_suffix=None) -> str:
    parts = [
        str(p).strip()
        for p in (name_first, name_middle, name_last, name_suffix)
        if p is not None and str(p).strip()
    ]
    return " ".join(parts)


def resolve_full_name(
    *,
    display_name=None,
    name_first=None,
    name_middle=None,
    name_last=None,
    name_suffix=None,
) -> str:
    if display_name is not None and str(display_name).strip():
        return str(display_name).strip()
    return compose_name(name_first, name_middle, name_last, name_suffix)


def display_name_from_source(row: dict) -> str | None:
    """Import core.people.full_name only when it is a true override of the name parts."""
    computed = compose_name(
        row.get("name_first"),
        row.get("name_middle"),
        row.get("name_last"),
        row.get("name_suffix"),
    )
    raw = row.get("full_name")
    if raw is None:
        return None
    stripped = str(raw).strip()
    if not stripped or stripped == computed:
        return None
    return stripped


def filter_people_search(qs, q: str | None):
    if not q or not str(q).strip():
        return qs
    s = str(q).strip()
    return qs.filter(
        Q(display_name__icontains=s)
        | Q(name_first__icontains=s)
        | Q(name_middle__icontains=s)
        | Q(name_last__icontains=s)
        | Q(name_suffix__icontains=s)
        | Q(email_public__icontains=s)
    )


PERSON_LIST_ORDER = ("name_last", "name_first", "id")


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.TextField()
    employee_id = models.TextField(null=True, blank=True)
    name_first = models.TextField(null=True, blank=True)
    name_middle = models.TextField(null=True, blank=True)
    name_last = models.TextField(null=True, blank=True)
    name_suffix = models.TextField(null=True, blank=True)
    display_name = models.TextField(null=True, blank=True)
    email_public = models.TextField(null=True, blank=True)
    phone_public = models.TextField(null=True, blank=True)
    phone_public_ext = models.TextField(null=True, blank=True)
    show_in_directory = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "people_person"
        indexes = [
            models.Index(fields=["tenant_id", "name_last", "name_first"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "employee_id"],
                name="uq_people_tenant_employee",
                condition=models.Q(employee_id__isnull=False) & ~models.Q(employee_id=""),
            ),
        ]
        permissions = [
            ("trigger_wordpress_sync", "Can trigger WordPress sync for a person"),
        ]

    def save(self, *args, **kwargs):
        if self.display_name is not None:
            stripped = str(self.display_name).strip()
            self.display_name = stripped or None
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return resolve_full_name(
            display_name=self.display_name,
            name_first=self.name_first,
            name_middle=self.name_middle,
            name_last=self.name_last,
            name_suffix=self.name_suffix,
        )

    def __str__(self):
        return self.full_name or str(self.id)
