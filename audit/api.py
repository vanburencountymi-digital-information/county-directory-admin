from uuid import UUID

from django.db import transaction
from ninja import Router
from ninja.errors import HttpError

from accounts.authz import actor_label, require_directory_editor
from audit.models import AuditLog
from audit.services import insert_audit, timestamps_match
from organizations.models import Organization
from people.api import PEOPLE_PATCHABLE
from people.models import Person
from wordpress.serializers import organization_to_wire, person_to_admin

router = Router(tags=["audit"])

ORG_PATCHABLE = {
    "name",
    "org_type",
    "parent_id",
    "public_email",
    "phone",
    "hours_text",
    "website_url",
    "address_mailing",
    "address_physical",
    "additional_information",
    "fax",
}


@router.get("")
@router.get("/")
def list_audit(
    request,
    limit: int = 50,
    offset: int = 0,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
):
    tenant_id = require_directory_editor(request)
    qs = AuditLog.objects.filter(
        tenant_id=tenant_id,
        action__in=["directory.mutation", "directory.revert"],
    )
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if entity_id:
        qs = qs.filter(entity_id=entity_id)
    items = []
    for row in qs.order_by("-id")[offset : offset + limit]:
        items.append(
            {
                "id": row.id,
                "actor": row.actor,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": str(row.entity_id) if row.entity_id else None,
                "details": row.details,
                "ts": row.ts.isoformat(),
            }
        )
    return {"items": items, "limit": limit, "offset": offset}


@router.post("/{audit_id}/revert")
def revert_mutation(request, audit_id: int):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    with transaction.atomic():
        try:
            log_row = AuditLog.objects.select_for_update().get(id=audit_id, tenant_id=tenant_id)
        except AuditLog.DoesNotExist:
            raise HttpError(404, "Audit entry not found") from None
        if log_row.action != "directory.mutation":
            raise HttpError(400, "Only directory.mutation entries can be reverted")
        details = log_row.details or {}
        if details.get("reverted"):
            raise HttpError(400, "This change was already reverted")
        op = details.get("op")
        table = details.get("table")
        before = details.get("before") or {}
        after = details.get("after") or {}
        entity_id = log_row.entity_id
        if op != "update" or table not in ("core.people", "core.organizations"):
            raise HttpError(400, "Revert is only supported for update operations on people and organizations")
        if not entity_id:
            raise HttpError(400, "Missing entity id")

        if table == "core.people":
            try:
                current = Person.objects.select_for_update().get(
                    id=entity_id, tenant_id=tenant_id, archived_at__isnull=True
                )
            except Person.DoesNotExist:
                raise HttpError(409, "Person no longer exists or is archived") from None
            if not timestamps_match(current.updated_at, after.get("updated_at")):
                raise HttpError(409, "Record was changed after this edit; revert blocked for safety")
            state_before = person_to_admin(current)
            changed = False
            for col in PEOPLE_PATCHABLE:
                if col in before:
                    setattr(current, col, before[col])
                    changed = True
            if not changed:
                raise HttpError(400, "Nothing to revert")
            current.save()
            state_after = person_to_admin(current)
        else:
            try:
                current = Organization.objects.select_for_update().get(
                    id=entity_id, tenant_id=tenant_id, archived_at__isnull=True
                )
            except Organization.DoesNotExist:
                raise HttpError(409, "Organization not found or archived") from None
            if not timestamps_match(current.updated_at, after.get("updated_at")):
                raise HttpError(409, "Record was changed after this edit; revert blocked for safety")
            state_before = organization_to_wire(current)
            changed = False
            for col in ORG_PATCHABLE:
                if col in before:
                    if col == "parent_id":
                        current.parent_id = before[col]
                    else:
                        setattr(current, col, before[col])
                    changed = True
            if not changed:
                raise HttpError(400, "Nothing to revert")
            current.save()
            state_after = organization_to_wire(current)

        revert_log = insert_audit(
            tenant_id=tenant_id,
            actor=actor,
            action="directory.revert",
            entity_type=log_row.entity_type,
            entity_id=entity_id,
            details={
                "op": "revert",
                "reverts_audit_id": audit_id,
                "table": table,
                "before": state_before,
                "after": state_after,
            },
        )
        merged = dict(details)
        merged["reverted"] = True
        merged["reverted_at_audit_id"] = revert_log.id
        log_row.details = merged
        log_row.save(update_fields=["details"])

    return {"ok": True, "audit_id": audit_id, "revert_audit_id": revert_log.id}
