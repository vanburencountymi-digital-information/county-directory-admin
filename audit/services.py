from datetime import datetime
from uuid import UUID

from django.utils import timezone

from .models import AuditLog


def insert_audit(*, tenant_id, actor, action, entity_type, entity_id, details) -> AuditLog:
    return AuditLog.objects.create(
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )


def normalize_ts(s: str | None) -> str:
    if s is None:
        return ""
    return s.replace("Z", "+00:00").replace(" ", "T")


def timestamps_match(db_val, snapshot_val) -> bool:
    if snapshot_val is None and db_val is None:
        return True
    if db_val is None or snapshot_val is None:
        return False
    if isinstance(db_val, datetime):
        db_s = db_val.isoformat()
    else:
        db_s = str(db_val)
    if isinstance(snapshot_val, str):
        snap_s = snapshot_val
    else:
        snap_s = (
            snapshot_val.isoformat()
            if hasattr(snapshot_val, "isoformat")
            else str(snapshot_val)
        )
    return normalize_ts(db_s) == normalize_ts(snap_s)


def jsonable(v):
    if v is None:
        return None
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        if timezone.is_aware(v):
            return v.isoformat()
        return v.isoformat()
    if hasattr(v, "isoformat") and not isinstance(v, str):
        return v.isoformat()
    if isinstance(v, bool):
        return v
    return v
