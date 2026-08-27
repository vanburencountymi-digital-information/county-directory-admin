from uuid import UUID

from django.conf import settings
from django.contrib.auth.models import Group
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.authz import actor_label, require_permissions_admin
from accounts.models import TenantMembership, User
from accounts.services import grant_directory_group, upgrade_person_to_user
from audit.services import insert_audit
from people.models import Person

router = Router(tags=["permissions"])

GROUP_META = {
    settings.GROUP_DIRECTORY_EDITOR: {
        "cap_key": settings.GROUP_DIRECTORY_EDITOR,
        "cap_label": "Directory editor",
        "description": "Can edit the directory",
    },
    settings.GROUP_PERMISSIONS_ADMIN: {
        "cap_key": settings.GROUP_PERMISSIONS_ADMIN,
        "cap_label": "Permissions admin",
        "description": "Can grant and revoke directory access",
    },
}


@router.get("/caps")
def list_caps(request):
    require_permissions_admin(request)
    items = []
    for name, meta in GROUP_META.items():
        group = Group.objects.filter(name=name).first()
        items.append(
            {
                "id": str(group.id) if group else name,
                **meta,
            }
        )
    return {"items": items}


@router.get("/people")
def search_people(request, q: str, limit: int = 25):
    tenant_id = require_permissions_admin(request)
    s = q.lower()
    rows = Person.objects.filter(
        tenant_id=tenant_id,
        archived_at__isnull=True,
    ).filter(
        models_q(s)
    ).order_by("full_name", "name_last", "id")[:limit]
    return {
        "items": [
            {
                "id": str(p.id),
                "full_name": p.full_name,
                "name_first": p.name_first,
                "name_last": p.name_last,
                "email_public": p.email_public,
            }
            for p in rows
        ]
    }


def models_q(s: str):
    from django.db.models import Q

    return Q(full_name__icontains=s) | Q(email_public__icontains=s) | Q(name_last__icontains=s)


@router.get("/people/{person_id}/caps")
def get_person_caps(request, person_id: UUID):
    tenant_id = require_permissions_admin(request)
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    user = User.objects.filter(person=person).first()
    group_names = set()
    if user:
        if TenantMembership.objects.filter(user=user, tenant_id=tenant_id).exists():
            group_names = set(user.groups.values_list("name", flat=True))
    items = []
    for name, meta in GROUP_META.items():
        if name in group_names:
            items.append({**meta, "granted_at": None, "granted_by": None})
    return {"items": items}


class CapGrant(Schema):
    cap_key: str


@router.post("/people/{person_id}/caps")
def grant_cap(request, person_id: UUID, payload: CapGrant):
    tenant_id = require_permissions_admin(request)
    actor = actor_label(request)
    if payload.cap_key not in GROUP_META:
        raise HttpError(404, "Unknown cap_key")
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    try:
        grant_directory_group(person, payload.cap_key, tenant_id)
    except ValueError as e:
        raise HttpError(400, str(e)) from e
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="permissions.mutation",
        entity_type="person_cap",
        entity_id=person_id,
        details={"op": "grant", "cap_key": payload.cap_key, "cap_label": GROUP_META[payload.cap_key]["cap_label"]},
    )
    return {"ok": True}


@router.delete("/people/{person_id}/caps/{cap_key}")
def revoke_cap(request, person_id: UUID, cap_key: str):
    tenant_id = require_permissions_admin(request)
    actor = actor_label(request)
    if cap_key not in GROUP_META:
        raise HttpError(404, "Unknown cap_key")
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    user = User.objects.filter(person=person).first()
    if not user:
        raise HttpError(404, "Grant not found")
    group = Group.objects.get(name=cap_key)
    if not user.groups.filter(id=group.id).exists():
        raise HttpError(404, "Grant not found")
    user.groups.remove(group)
    insert_audit(
        tenant_id=tenant_id,
        actor=actor,
        action="permissions.mutation",
        entity_type="person_cap",
        entity_id=person_id,
        details={"op": "revoke", "cap_key": cap_key, "cap_label": GROUP_META[cap_key]["cap_label"]},
    )
    return {"ok": True}
