from datetime import date, datetime
from uuid import UUID

from django.utils import timezone

PERSON_WIRE_FIELDS = (
    "id",
    "tenant_id",
    "name_first",
    "name_middle",
    "name_last",
    "name_suffix",
    "full_name",
    "email_public",
    "phone_public",
    "phone_public_ext",
    "job_title",
    "employee_id",
    "person_key",
    "role",
    "show_in_directory",
    "archived_at",
    "created_at",
    "updated_at",
)

ORG_WIRE_FIELDS = (
    "id",
    "tenant_id",
    "org_type",
    "name",
    "slug",
    "public_email",
    "phone",
    "website_url",
    "hours_text",
    "archived_at",
    "created_at",
    "updated_at",
    "department_id",
    "parent_department_id",
    "address_mailing",
    "address_physical",
    "additional_information",
    "fax",
)


def jsonable(v):
    if v is None:
        return None
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bool):
        return v
    return v


def person_to_wire(person) -> dict:
    return {field: jsonable(getattr(person, field)) for field in PERSON_WIRE_FIELDS}


def organization_to_wire(org) -> dict:
    data = {field: jsonable(getattr(org, field)) for field in ORG_WIRE_FIELDS}
    data["parent_id"] = str(org.parent_id) if org.parent_id else None
    return data


def assignment_to_wire(assignment, *, include_org_type: bool = False) -> dict:
    data = {
        "id": str(assignment.id),
        "tenant_id": assignment.tenant_id,
        "person_id": str(assignment.person_id) if assignment.person_id else None,
        "org_id": str(assignment.org_id),
        "job_title": assignment.job_title,
        "status": assignment.status,
        "seat_no": assignment.seat_no,
        "receives_financial_reports": assignment.receives_financial_reports,
        "created_at": jsonable(assignment.created_at),
        "updated_at": jsonable(assignment.updated_at),
    }
    if include_org_type:
        data["org_type"] = assignment.org.org_type
    return data
