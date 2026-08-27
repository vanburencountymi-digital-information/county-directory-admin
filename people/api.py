from uuid import UUID

from django.db.models import Count, Q
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.authz import actor_label, require_directory_editor
from assignments.models import Assignment
from audit.services import insert_audit, jsonable
from people.models import Person, derive_full_name
from wordpress.serializers import person_to_wire
from wordpress.services import try_push_person_to_wordpress

router = Router(tags=["people"])

PEOPLE_PATCHABLE = {
    "name_first",
    "name_middle",
    "name_last",
    "name_suffix",
    "full_name",
    "email_public",
    "phone_public",
    "phone_public_ext",
    "job_title",
    "show_in_directory",
    "employee_id",
    "person_key",
}


def format_public_phone(phone, ext):
    p = (phone or "").strip()
    e = (ext or "").strip()
    if p and e:
        return f"{p} ext. {e}"
    if p:
        return p
    if e:
        return f"ext. {e}"
    return None


def _search_q(qs, q: str | None):
    if not q:
        return qs
    s = q.lower()
    return qs.filter(
        Q(full_name__icontains=s) | Q(email_public__icontains=s) | Q(name_last__icontains=s)
    )


class PersonCreate(Schema):
    name_first: str | None = None
    name_last: str | None = None
    full_name: str | None = None
    email_public: str | None = None
    phone_public: str | None = None
    phone_public_ext: str | None = None
    job_title: str | None = None
    show_in_directory: bool = False
    employee_id: str | None = None
    person_key: str | None = None


class PersonPatch(Schema):
    name_first: str | None = None
    name_middle: str | None = None
    name_last: str | None = None
    name_suffix: str | None = None
    full_name: str | None = None
    email_public: str | None = None
    phone_public: str | None = None
    phone_public_ext: str | None = None
    job_title: str | None = None
    show_in_directory: bool | None = None
    employee_id: str | None = None
    person_key: str | None = None


def _person_list_item(p: Person, assignment=None) -> dict:
    data = {
        "id": str(p.id),
        "full_name": p.full_name,
        "name_first": p.name_first,
        "name_last": p.name_last,
        "email_public": p.email_public,
        "phone_public": p.phone_public,
        "phone_public_ext": p.phone_public_ext,
        "job_title": p.job_title,
        "show_in_directory": p.show_in_directory,
        "updated_at": jsonable(p.updated_at),
    }
    if assignment is not None:
        data["assignment_id"] = str(assignment.id)
        data["assignment_job_title"] = assignment.job_title
        data["assignment_status"] = assignment.status
    return data


@router.get("/people")
def list_all_people(
    request,
    q: str | None = None,
    unassigned: bool = False,
    limit: int = 500,
    offset: int = 0,
):
    tenant_id = require_directory_editor(request)
    qs = Person.objects.filter(tenant_id=tenant_id, archived_at__isnull=True)
    qs = _search_q(qs, q)
    if unassigned:
        qs = qs.filter(assignments__isnull=True).distinct()
    total = qs.count()
    qs = qs.annotate(assignment_count=Count("assignments")).order_by("full_name", "name_last", "id")
    items = []
    for p in qs[offset : offset + limit]:
        row = _person_list_item(p)
        row["assignment_count"] = p.assignment_count
        assigns = (
            Assignment.objects.filter(person=p, tenant_id=tenant_id, org__archived_at__isnull=True)
            .select_related("org")
            .order_by("org__name")
        )
        labels = []
        for a in assigns:
            label = a.org.name or "Unknown org"
            if a.job_title:
                label = f"{label} — {a.job_title}"
            if label not in labels:
                labels.append(label)
        row["assignment_summary"] = "; ".join(labels) if labels else None
        items.append(row)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/people/{person_id}")
def get_person(request, person_id: UUID):
    tenant_id = require_directory_editor(request)
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    data = person_to_wire(person)
    assigns = (
        Assignment.objects.filter(person=person, tenant_id=tenant_id)
        .select_related("org")
        .order_by("org__name")
    )
    data["assignments"] = [
        {
            "id": str(a.id),
            "org_id": str(a.org_id),
            "job_title": a.job_title,
            "status": a.status,
            "seat_no": a.seat_no,
            "org_name": a.org.name,
        }
        for a in assigns
    ]
    return data


@router.post("/people")
def create_person(request, payload: PersonCreate):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    person = Person(
        tenant_id=tenant_id,
        name_first=payload.name_first,
        name_last=payload.name_last,
        full_name=derive_full_name(payload.name_first, payload.name_last, payload.full_name),
        email_public=payload.email_public,
        phone_public=payload.phone_public,
        phone_public_ext=payload.phone_public_ext,
        job_title=payload.job_title,
        show_in_directory=payload.show_in_directory,
        employee_id=payload.employee_id,
        person_key=payload.person_key,
    )
    person.save()
    after = person_to_wire(person)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="person",
        entity_id=person.id,
        details={"op": "create", "table": "core.people", "after": after},
    )
    return {"ok": True, "person": after}


@router.patch("/people/{person_id}")
def patch_person(request, person_id: UUID, payload: PersonPatch):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    updates = {
        k: v
        for k, v in payload.dict(exclude_unset=True).items()
        if k in PEOPLE_PATCHABLE
    }
    if not updates:
        raise HttpError(400, "No valid fields to update")
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    before = person_to_wire(person)
    for key, val in updates.items():
        setattr(person, key, val)
    if "full_name" in updates:
        person.full_name = derive_full_name(person.name_first, person.name_last, person.full_name)
    elif any(k in updates for k in ("name_first", "name_last", "name_middle", "name_suffix")):
        person.full_name = derive_full_name(person.name_first, person.name_last)
    person.save()
    after = person_to_wire(person)
    log = insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="person",
        entity_id=person.id,
        details={
            "op": "update",
            "table": "core.people",
            "before": before,
            "after": after,
            "columns_changed": list(updates.keys()),
        },
    )
    if "show_in_directory" in updates:
        try_push_person_to_wordpress(tenant_id, person.id)
    return {"ok": True, "person": after, "audit_id": log.id}


@router.delete("/people/{person_id}")
def archive_person(request, person_id: UUID):
    tenant_id = require_directory_editor(request)
    actor = actor_label(request)
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    before = person_to_wire(person)
    Assignment.objects.filter(person=person, tenant_id=tenant_id).update(person=None)
    from django.utils import timezone as tz

    person.archived_at = tz.now()
    person.save()
    after = person_to_wire(person)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="directory.mutation",
        entity_type="person",
        entity_id=person.id,
        details={"op": "archive", "table": "core.people", "before": before, "after": after},
    )
    try_push_person_to_wordpress(tenant_id, person.id)
    return {"ok": True}


@router.get("/directory/print")
def get_print_directory(request):
    tenant_id = require_directory_editor(request)
    rows = (
        Assignment.objects.filter(
            tenant_id=tenant_id,
            org__archived_at__isnull=True,
            person__archived_at__isnull=True,
            person__show_in_directory=True,
        )
        .exclude(status__iexact="inactive")
        .select_related("org", "org__parent", "person")
        .order_by("org__parent__name", "org__sort_order", "org__name", "person__name_last", "person__name_first")
    )
    grouped: dict[str, dict] = {}
    for a in rows:
        department = (a.org.name or "Uncategorized").strip() or "Uncategorized"
        if department not in grouped:
            parent_name = a.org.parent.name if a.org.parent_id else None
            grouped[department] = {
                "parent_group": (parent_name or "").strip() or None,
                "phone": a.org.phone,
                "email": a.org.public_email,
                "address": a.org.address_physical or a.org.address_mailing,
                "entries": [],
            }
        p = a.person
        joined = " ".join([x.strip() for x in [p.name_first, p.name_last] if x and x.strip()])
        display = joined or (p.full_name or "").strip() or "Unknown"
        grouped[department]["entries"].append(
            {
                "name": display,
                "title": a.job_title,
                "phone": format_public_phone(p.phone_public, p.phone_public_ext),
                "email": p.email_public,
            }
        )
    return [
        {
            "department": department,
            "parent_group": info["parent_group"],
            "phone": info["phone"],
            "email": info["email"],
            "address": info["address"],
            "entries": info["entries"],
        }
        for department, info in grouped.items()
    ]
