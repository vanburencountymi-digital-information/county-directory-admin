from uuid import UUID, uuid4

from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.authz import actor_label, require_directory_editor
from assignments.models import Assignment
from audit.services import insert_audit, jsonable
from organizations.models import ALLOWED_ORG_TYPES, Organization, slugify_org_name
from organizations.services import validate_org_parent
from people.models import PERSON_LIST_ORDER, Person, filter_people_search
from wordpress.serializers import assignment_to_wire, organization_to_wire

router = Router(tags=["organizations"])

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


class OrgCreate(Schema):
    name: str
    org_type: str
    slug: str | None = None
    parent_id: UUID | None = None


class OrgPatch(Schema):
    name: str | None = None
    org_type: str | None = None
    parent_id: UUID | None = None
    public_email: str | None = None
    phone: str | None = None
    hours_text: str | None = None
    website_url: str | None = None
    address_mailing: str | None = None
    address_physical: str | None = None
    additional_information: str | None = None
    fax: str | None = None


class AssignmentCreate(Schema):
    job_title: str | None = None
    status: str | None = None
    seat_no: int | None = None
    person_id: UUID | None = None


def _org_list_item(o: Organization) -> dict:
    return {
        "id": str(o.id),
        "name": o.name,
        "org_type": o.org_type,
        "parent_id": str(o.parent_id) if o.parent_id else None,
        "public_email": o.public_email,
        "phone": o.phone,
        "slug": o.slug,
    }


@router.get("/orgs")
def list_orgs(request):
    tenant_id = require_directory_editor(request)
    rows = Organization.objects.filter(tenant_id=tenant_id, archived_at__isnull=True).order_by("name", "id")
    return {"items": [_org_list_item(o) for o in rows]}


@router.post("/orgs")
def create_org(request, payload: OrgCreate):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    name_clean = payload.name.strip()
    if not name_clean:
        raise HttpError(400, "Name is required")
    org_type = payload.org_type.strip()
    if org_type not in ALLOWED_ORG_TYPES:
        raise HttpError(
            400,
            f"Invalid org_type {org_type!r}. Use one of: {', '.join(sorted(ALLOWED_ORG_TYPES))}",
        )
    base_slug = (
        slugify_org_name(payload.slug.strip())
        if payload.slug and payload.slug.strip()
        else slugify_org_name(name_clean)
    )
    validate_org_parent(
        tenant_id=tenant_id,
        org_id=None,
        parent_id=payload.parent_id,
        child_org_type=org_type,
    )
    slug = base_slug
    for _ in range(64):
        taken = Organization.objects.filter(
            tenant_id=tenant_id, archived_at__isnull=True, slug=slug, org_type=org_type
        ).exists()
        if not taken:
            break
        slug = f"{base_slug[:48]}-{uuid4().hex[:8]}"
    else:
        raise HttpError(500, "Could not allocate a unique slug")
    org = Organization(
        tenant_id=tenant_id,
        name=name_clean,
        org_type=org_type,
        slug=slug,
        parent_id=payload.parent_id,
    )
    org.save()
    after = organization_to_wire(org)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="organization",
        entity_id=org.id,
        details={"op": "create", "table": "core.organizations", "after": after},
    )
    return {"ok": True, "organization": after}


@router.get("/orgs/{org_id}")
def get_org(request, org_id: UUID):
    tenant_id = require_directory_editor(request)
    try:
        org = Organization.objects.get(id=org_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Organization.DoesNotExist:
        raise HttpError(404, "Organization not found") from None
    return organization_to_wire(org)


@router.patch("/orgs/{org_id}")
def patch_org(request, org_id: UUID, payload: OrgPatch):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    updates = {k: v for k, v in payload.dict(exclude_unset=True).items() if k in ORG_PATCHABLE}
    if not updates:
        raise HttpError(400, "No valid fields to update")
    try:
        org = Organization.objects.get(id=org_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Organization.DoesNotExist:
        raise HttpError(404, "Organization not found") from None
    before = organization_to_wire(org)
    if "parent_id" in updates or "org_type" in updates:
        effective_type = updates.get("org_type", org.org_type)
        if "parent_id" in updates:
            effective_parent = updates.get("parent_id")
        else:
            effective_parent = org.parent_id
        validate_org_parent(
            tenant_id=tenant_id,
            org_id=org.id,
            parent_id=effective_parent,
            child_org_type=effective_type,
        )
    for key, val in updates.items():
        if key == "parent_id":
            org.parent_id = val
        else:
            setattr(org, key, val)
    org.save()
    after = organization_to_wire(org)
    log = insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="organization",
        entity_id=org.id,
        details={
            "op": "update",
            "table": "core.organizations",
            "before": before,
            "after": after,
            "columns_changed": list(updates.keys()),
        },
    )
    return {"ok": True, "organization": after, "audit_id": log.id}


def _person_search(qs, q: str | None):
    return filter_people_search(qs, q)


@router.get("/orgs/{org_id}/people")
def list_people_for_org(request, org_id: UUID, q: str | None = None, limit: int = 100, offset: int = 0):
    tenant_id = require_directory_editor(request)
    if not Organization.objects.filter(id=org_id, tenant_id=tenant_id, archived_at__isnull=True).exists():
        raise HttpError(404, "Organization not found")
    assigns = Assignment.objects.filter(
        org_id=org_id, tenant_id=tenant_id, person__archived_at__isnull=True, person__isnull=False
    ).select_related("person")
    if q:
        matching_ids = filter_people_search(Person.objects.filter(tenant_id=tenant_id), q).values("id")
        assigns = assigns.filter(person_id__in=matching_ids)
    total = assigns.count()
    items = []
    for a in assigns.order_by("person__name_last", "person__name_first", "person__id")[offset : offset + limit]:
        row = {
            "id": str(a.person.id),
            "full_name": a.person.full_name,
            "name_first": a.person.name_first,
            "name_last": a.person.name_last,
            "email_public": a.person.email_public,
            "phone_public": a.person.phone_public,
            "phone_public_ext": a.person.phone_public_ext,
            "show_in_directory": a.person.show_in_directory,
            "updated_at": jsonable(a.person.updated_at),
            "assignment_id": str(a.id),
            "assignment_job_title": a.job_title,
            "assignment_status": a.status,
        }
        items.append(row)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/orgs/{org_id}/people/unassigned")
def list_people_without_assignment_in_org(
    request, org_id: UUID, q: str | None = None, limit: int = 200, offset: int = 0
):
    tenant_id = require_directory_editor(request)
    if not Organization.objects.filter(id=org_id, tenant_id=tenant_id, archived_at__isnull=True).exists():
        raise HttpError(404, "Organization not found")
    assigned_ids = Assignment.objects.filter(org_id=org_id, tenant_id=tenant_id).values_list("person_id", flat=True)
    qs = Person.objects.filter(tenant_id=tenant_id, archived_at__isnull=True).exclude(id__in=assigned_ids)
    qs = _person_search(qs, q)
    total = qs.count()
    items = []
    for p in qs.order_by(*PERSON_LIST_ORDER)[offset : offset + limit]:
        items.append(
            {
                "id": str(p.id),
                "full_name": p.full_name,
                "name_first": p.name_first,
                "name_last": p.name_last,
                "email_public": p.email_public,
                "phone_public": p.phone_public,
                "phone_public_ext": p.phone_public_ext,
                "show_in_directory": p.show_in_directory,
                "updated_at": jsonable(p.updated_at),
            }
        )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/orgs/{org_id}/assignments")
def list_assignments_for_org(request, org_id: UUID):
    tenant_id = require_directory_editor(request)
    if not Organization.objects.filter(id=org_id, tenant_id=tenant_id, archived_at__isnull=True).exists():
        raise HttpError(404, "Organization not found")
    rows = Assignment.objects.filter(org_id=org_id, tenant_id=tenant_id).select_related("person").order_by("job_title", "id")
    items = []
    for a in rows:
        items.append(
            {
                "id": str(a.id),
                "job_title": a.job_title,
                "status": a.status,
                "seat_no": a.seat_no,
                "person_id": str(a.person_id) if a.person_id else None,
                "person_full_name": a.person.full_name if a.person_id else None,
                "person_email": a.person.email_public if a.person_id else None,
            }
        )
    return {"items": items}


@router.post("/orgs/{org_id}/assignments")
def create_assignment(request, org_id: UUID, payload: AssignmentCreate):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    if not Organization.objects.filter(id=org_id, tenant_id=tenant_id, archived_at__isnull=True).exists():
        raise HttpError(404, "Organization not found")
    if payload.person_id:
        if not Person.objects.filter(id=payload.person_id, tenant_id=tenant_id, archived_at__isnull=True).exists():
            raise HttpError(404, "Person not found")
    a = Assignment.objects.create(
        tenant_id=tenant_id,
        org_id=org_id,
        job_title=payload.job_title,
        status=payload.status,
        seat_no=payload.seat_no,
        person_id=payload.person_id,
    )
    after = assignment_to_wire(a)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="assignment",
        entity_id=a.id,
        details={"op": "create", "table": "core.assignments", "after": after},
    )
    return {"ok": True, "assignment": after}
