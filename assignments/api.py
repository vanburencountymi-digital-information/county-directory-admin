from uuid import UUID

from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.authz import actor_label, require_directory_editor
from assignments.models import Assignment
from audit.services import insert_audit
from organizations.models import Organization
from people.models import Person
from wordpress.serializers import assignment_to_wire

router = Router(tags=["assignments"])

ASSIGNMENT_PATCHABLE = {"job_title", "status", "seat_no"}


class AssignmentCreate(Schema):
    job_title: str | None = None
    status: str | None = None
    seat_no: int | None = None
    person_id: UUID | None = None


class AssignmentPatch(Schema):
    job_title: str | None = None
    status: str | None = None
    seat_no: int | None = None


class AssignmentPersonLink(Schema):
    person_id: UUID


@router.get("/assignments/open")
def list_open_assignments(request):
    tenant_id = require_directory_editor(request)
    rows = (
        Assignment.objects.filter(tenant_id=tenant_id, person__isnull=True, org__archived_at__isnull=True)
        .select_related("org")
        .order_by("org__name", "job_title", "id")
    )
    return {
        "items": [
            {
                "id": str(a.id),
                "job_title": a.job_title,
                "status": a.status,
                "seat_no": a.seat_no,
                "org_id": str(a.org_id),
                "org_name": a.org.name,
            }
            for a in rows
        ]
    }


@router.patch("/assignments/{assignment_id}")
def patch_assignment(request, assignment_id: UUID, payload: AssignmentPatch):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    updates = {k: v for k, v in payload.dict(exclude_unset=True).items() if k in ASSIGNMENT_PATCHABLE}
    if not updates:
        raise HttpError(400, "No valid fields to update")
    try:
        a = Assignment.objects.get(id=assignment_id, tenant_id=tenant_id)
    except Assignment.DoesNotExist:
        raise HttpError(404, "Assignment not found") from None
    before = assignment_to_wire(a)
    for key, val in updates.items():
        setattr(a, key, val)
    a.save()
    after = assignment_to_wire(a)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="assignment",
        entity_id=a.id,
        details={
            "op": "update",
            "table": "core.assignments",
            "before": before,
            "after": after,
            "columns_changed": list(updates.keys()),
        },
    )
    return {"ok": True, "assignment": after}


@router.delete("/assignments/{assignment_id}")
def delete_assignment(request, assignment_id: UUID):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    try:
        a = Assignment.objects.get(id=assignment_id, tenant_id=tenant_id)
    except Assignment.DoesNotExist:
        raise HttpError(404, "Assignment not found") from None
    if a.person_id is not None:
        raise HttpError(
            409,
            "Cannot delete a role while someone is assigned to it — unlink the person first",
        )
    before = assignment_to_wire(a)
    aid = a.id
    a.delete()
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="assignment",
        entity_id=aid,
        details={"op": "delete", "table": "core.assignments", "before": before},
    )
    return {"ok": True}


@router.post("/assignments/{assignment_id}/person")
def link_person_to_assignment(request, assignment_id: UUID, payload: AssignmentPersonLink):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    try:
        a = Assignment.objects.get(id=assignment_id, tenant_id=tenant_id)
    except Assignment.DoesNotExist:
        raise HttpError(404, "Assignment not found") from None
    if a.person_id is not None:
        raise HttpError(409, "Role already has someone assigned — unlink them first")
    if not Person.objects.filter(id=payload.person_id, tenant_id=tenant_id, archived_at__isnull=True).exists():
        raise HttpError(404, "Person not found")
    before = assignment_to_wire(a)
    a.person_id = payload.person_id
    a.save()
    after = assignment_to_wire(a)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="assignment",
        entity_id=a.id,
        details={"op": "link_person", "table": "core.assignments", "before": before, "after": after},
    )
    return {"ok": True, "assignment": after}


@router.delete("/assignments/{assignment_id}/person")
def unlink_person_from_assignment(request, assignment_id: UUID):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    try:
        a = Assignment.objects.get(id=assignment_id, tenant_id=tenant_id)
    except Assignment.DoesNotExist:
        raise HttpError(404, "Assignment not found") from None
    if a.person_id is None:
        raise HttpError(409, "No person is linked to this role")
    before = assignment_to_wire(a)
    a.person = None
    a.save()
    after = assignment_to_wire(a)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="assignment",
        entity_id=a.id,
        details={"op": "unlink_person", "table": "core.assignments", "before": before, "after": after},
    )
    return {"ok": True, "assignment": after}
