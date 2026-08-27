import uuid

from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    tenant_id = models.TextField()
    actor = models.TextField()
    action = models.TextField()
    entity_type = models.TextField()
    entity_id = models.UUIDField(null=True, blank=True)
    details = models.JSONField(default=dict)
    ts = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "audit_auditlog"
        indexes = [models.Index(fields=["tenant_id", "-ts"])]
        permissions = [
            ("revert_auditlog", "Can revert a directory mutation"),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type} {self.entity_id}"
