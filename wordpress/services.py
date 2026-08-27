"""Outbound WordPress client and force-sync service.

Call push_person_to_wordpress explicitly from people/assignments views.
Do not use Django signals.
"""

from uuid import UUID

import httpx
from django.conf import settings
from ninja.errors import HttpError

from assignments.models import Assignment
from people.models import Person

from .serializers import assignment_to_wire, person_to_wire


def _wp_secret() -> str:
    secret = settings.WP_SYNC_TRIGGER_SECRET
    if not secret:
        raise HttpError(503, "WP_SYNC_TRIGGER_SECRET is not configured on Directory Admin.")
    return secret


def _wp_route_url(tenant_id: str, route: str) -> str:
    trigger = settings.WP_SYNC_TRIGGER_URL_BY_TENANT.get(tenant_id)
    if not trigger:
        raise HttpError(
            404,
            f"No WordPress sync URL configured for tenant {tenant_id!r}. "
            "Set WP_SYNC_TRIGGER_URL_BY_TENANT on Directory Admin.",
        )
    base = trigger.rsplit("/", 1)[0]
    return f"{base}/{route.lstrip('/')}"


def _wp_post(url: str, secret: str, json_body: dict | None = None) -> dict:
    try:
        r = httpx.post(
            url,
            headers={"X-County-Directory-Admin-Secret": secret},
            json=json_body,
            timeout=300.0,
        )
    except httpx.RequestError as e:
        raise HttpError(502, f"Could not reach WordPress: {e}") from e
    if r.status_code >= 400:
        raise HttpError(502, (r.text or r.reason_phrase or f"HTTP {r.status_code}").strip())
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def trigger_incremental_sync(tenant_id: str) -> dict:
    url = settings.WP_SYNC_TRIGGER_URL_BY_TENANT.get(tenant_id)
    if not url:
        raise HttpError(
            404,
            f"No WordPress sync URL configured for tenant {tenant_id!r}. "
            "Set WP_SYNC_TRIGGER_URL_BY_TENANT on Directory Admin.",
        )
    return _wp_post(url, _wp_secret())


def fetch_reconciliation_report(tenant_id: str) -> dict:
    url = _wp_route_url(tenant_id, "reconciliation-report")
    return _wp_post(url, _wp_secret())


def push_person_to_wordpress(tenant_id: str, person_id: UUID) -> dict:
    """Push one person + assignments. Includes archived people (unpublish)."""
    url = _wp_route_url(tenant_id, "force-sync-person")
    secret = _wp_secret()
    try:
        person = Person.objects.get(id=person_id, tenant_id=tenant_id)
    except Person.DoesNotExist:
        raise HttpError(404, "Person not found") from None
    assigns = (
        Assignment.objects.select_related("org")
        .filter(person_id=person_id, tenant_id=tenant_id)
        .order_by("org__name")
    )
    payload = {
        "person": person_to_wire(person),
        "assignments": [assignment_to_wire(a, include_org_type=True) for a in assigns],
    }
    return _wp_post(url, secret, payload)


def try_push_person_to_wordpress(tenant_id: str, person_id: UUID) -> None:
    """Best-effort push: directory write already committed."""
    try:
        push_person_to_wordpress(tenant_id, person_id)
    except HttpError:
        pass
