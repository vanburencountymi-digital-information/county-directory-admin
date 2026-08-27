import re
import uuid

from django.db import models
from django.utils import timezone

ALLOWED_ORG_TYPES = frozenset(
    {
        "department",
        "board",
        "local_unit",
        "county",
        "external",
        "committee",
        "authority",
        "task_force",
        "city",
        "township",
        "village",
        "external_org",
        "commission",
        "office",
        "division",
        "court",
        "municipality",
    }
)

BOARD_LIKE_ORG_TYPES = frozenset(
    {
        "board",
        "commission",
        "committee",
        "authority",
        "task_force",
    }
)


def hierarchy_family(org_type: str | None) -> str:
    t = (org_type or "").strip().lower()
    if t in BOARD_LIKE_ORG_TYPES:
        return "board"
    return "department"


def slugify_org_name(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")[:80] or "organization"


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.TextField()
    org_type = models.TextField()
    name = models.TextField()
    slug = models.CharField(max_length=100)
    public_email = models.TextField(null=True, blank=True)
    phone = models.TextField(null=True, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
        db_column="parent_id",
    )
    website_url = models.TextField(null=True, blank=True)
    hours_text = models.TextField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    department_id = models.TextField(null=True, blank=True)
    parent_department_id = models.TextField(null=True, blank=True)
    address_mailing = models.TextField(null=True, blank=True)
    address_physical = models.TextField(null=True, blank=True)
    additional_information = models.TextField(null=True, blank=True)
    fax = models.TextField(null=True, blank=True)
    sort_order = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "organizations_organization"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "slug", "org_type"],
                name="uq_orgs_tenant_slug_org_type",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "name"]),
        ]

    def __str__(self):
        return self.name
