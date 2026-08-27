from ninja.errors import HttpError

from .models import Organization, hierarchy_family


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
    current = parent
    seen = set()
    while current is not None:
        if str(current.id) == str(org_id):
            raise HttpError(400, "Cannot create a circular parent relationship")
        if current.id in seen:
            break
        seen.add(current.id)
        current = current.parent
