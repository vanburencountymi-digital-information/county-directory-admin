import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class Assignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.TextField()
    person = models.ForeignKey(
        "people.Person",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assignments",
    )
    org = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    seat_no = models.IntegerField(null=True, blank=True)
    status = models.TextField(null=True, blank=True)
    job_title = models.TextField(null=True, blank=True)
    created_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    receives_financial_reports = models.BooleanField(null=True, blank=True)

    class Meta:
        db_table = "assignments_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "person", "org", "seat_no"],
                name="uq_assignments_tenant_person_org_seat",
                condition=Q(person__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.job_title or 'role'} @ {self.org_id}"
