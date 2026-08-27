from datetime import datetime
from uuid import UUID

from ninja import Router
from ninja.errors import HttpError

from accounts.authz import SyncApiBearerAuth, require_directory_editor
from assignments.models import Assignment
from organizations.models import Organization
from people.models import Person
from wordpress.serializers import assignment_to_wire, organization_to_wire, person_to_wire
from wordpress.services import (
    fetch_reconciliation_report,
    push_person_to_wordpress,
    trigger_incremental_sync,
)

sync_router = Router(tags=["sync"], auth=SyncApiBearerAuth())
clerk_router = Router(tags=["wordpress"])


def _parse_since(updated_since: str | None):
    if not updated_since:
        return None
    raw = updated_since.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        raise HttpError(400, "Invalid updated_since") from None


@sync_router.get("/people")
def sync_people(request, tenant_id: str, updated_since: str | None = None):
    qs = Person.objects.filter(tenant_id=tenant_id)
    since = _parse_since(updated_since)
    if since:
        qs = qs.filter(updated_at__gt=since)
    qs = qs.order_by("updated_at")
    return {"items": [person_to_wire(p) for p in qs]}


@sync_router.get("/organizations")
def sync_organizations(
    request,
    tenant_id: str,
    updated_since: str | None = None,
    org_type: str | None = None,
):
    qs = Organization.objects.filter(tenant_id=tenant_id)
    since = _parse_since(updated_since)
    if since:
        qs = qs.filter(updated_at__gt=since)
    if org_type:
        qs = qs.filter(org_type=org_type)
    qs = qs.order_by("updated_at")
    return {"items": [organization_to_wire(o) for o in qs]}


@sync_router.get("/assignments")
def sync_assignments(request, tenant_id: str, updated_since: str | None = None):
    qs = Assignment.objects.filter(tenant_id=tenant_id).select_related("org")
    since = _parse_since(updated_since)
    if since:
        qs = qs.filter(updated_at__gt=since)
    qs = qs.order_by("updated_at")
    return {"items": [assignment_to_wire(a, include_org_type=True) for a in qs]}


@clerk_router.post("/incremental-sync")
def clerk_incremental_sync(request):
    tenant_id = require_directory_editor(request)
    body = trigger_incremental_sync(tenant_id)
    return {"ok": True, "wordpress": body}


@clerk_router.post("/reconciliation-report")
def clerk_reconciliation_report(request):
    tenant_id = require_directory_editor(request)
    body = fetch_reconciliation_report(tenant_id)
    return {"ok": True, "wordpress": body}


@clerk_router.post("/people/{person_id}/sync")
def clerk_force_sync_person(request, person_id: UUID):
    tenant_id = require_directory_editor(request)
    body = push_person_to_wordpress(tenant_id, person_id)
    return {"ok": True, "wordpress": body}
