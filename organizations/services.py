from ninja.errors import HttpError

from .models import Organization, hierarchy_family


def descendant_ids(tenant_id: str, org_id, *, include_self: bool = True) -> set:
    """IDs of org_id and every org under it in this tenant (archived excluded)."""
    rows = Organization.objects.filter(
        tenant_id=tenant_id,
        archived_at__isnull=True,
    ).values_list("id", "parent_id")
    children: dict = {}
    for oid, pid in rows:
        if pid is None:
            continue
        children.setdefault(pid, []).append(oid)
    out = set()
    stack = [org_id]
    while stack:
        current = stack.pop()
        if current in out:
            continue
        out.add(current)
        stack.extend(children.get(current, []))
    if not include_self:
        out.discard(org_id)
    return out


def validate_org_parent(*, tenant_id: str, org_id, parent_id, child_org_type: str | None) -> None:
    if parent_id is None:
        return
    if org_id is not None and str(parent_id) == str(org_id):
        raise HttpError(400, "Organization cannot be its own parent")
    try:
        parent = Organization.objects.get(id=parent_id, tenant_id=tenant_id, archived_at__isnull=True)
    except Organization.DoesNotExist:
        raise HttpError(400, "Parent organization not found") from None
    if hierarchy_family(child_org_type) != hierarchy_family(parent.org_type):
        raise HttpError(
            400,
            "Parent must be in the same hierarchy family (department vs board) for WordPress sync",
        )
    if org_id is None:
        return
    if parent.id in descendant_ids(tenant_id, org_id, include_self=False):
        raise HttpError(400, "Cannot create a circular parent relationship")
