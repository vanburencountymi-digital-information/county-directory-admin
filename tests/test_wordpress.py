from unittest.mock import patch
from uuid import uuid4

from tests.conftest import make_org, make_person
from assignments.models import Assignment
from wordpress.serializers import person_to_wire


VBC_TRIGGER = "https://vbc.example.test/wp-json/county/v1/trigger-incremental-sync"
FORCE_SYNC_URL = "https://vbc.example.test/wp-json/county/v1/force-sync-person"
WP_SECRET = "test-wp-trigger-secret"
SYNC_SECRET = "test-sync-api-secret"


class _FakeResp:
    status_code = 200
    text = '{"success":true}'
    reason_phrase = "OK"

    def json(self):
        return {"success": True}


def test_person_wire_booleans_and_tenant(person):
    wire = person_to_wire(person)
    assert wire["show_in_directory"] is True
    assert isinstance(wire["show_in_directory"], bool)
    assert wire["tenant_id"] == "VBC"
    assert wire["full_name"] == "Ada Lovelace"
    assert set(wire.keys()) >= {
        "id",
        "tenant_id",
        "name_first",
        "full_name",
        "show_in_directory",
        "archived_at",
    }


def test_sync_people_requires_bearer(client, person, settings):
    settings.SYNC_API_SECRET = SYNC_SECRET
    r = client.get("/sync/people", {"tenant_id": "VBC"})
    assert r.status_code in (401, 403)


def test_sync_people_golden(client, person, settings):
    settings.SYNC_API_SECRET = SYNC_SECRET
    r = client.get(
        "/sync/people",
        {"tenant_id": "VBC"},
        HTTP_AUTHORIZATION=f"Bearer {SYNC_SECRET}",
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert items[0]["id"] == str(person.id)
    assert items[0]["show_in_directory"] is True
    assert items[0]["tenant_id"] == "VBC"
    assert items[0]["full_name"] == person.full_name


def test_health_unauthenticated(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_force_sync_requires_login(client):
    r = client.post(f"/api/wordpress/people/{uuid4()}/sync")
    assert r.status_code == 401


def test_force_sync_posts_payload(as_editor, settings, monkeypatch):
    settings.WP_SYNC_TRIGGER_URL_BY_TENANT = {"VBC": VBC_TRIGGER}
    settings.WP_SYNC_TRIGGER_SECRET = WP_SECRET
    p = make_person()
    org = make_org()
    Assignment.objects.create(tenant_id="VBC", org=org, person=p, job_title="Deputy")
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResp()

    monkeypatch.setattr("wordpress.services.httpx.post", fake_post)
    r = as_editor.post(f"/api/wordpress/people/{p.id}/sync")
    assert r.status_code == 200
    assert captured["url"] == FORCE_SYNC_URL
    assert captured["headers"]["X-County-Directory-Admin-Secret"] == WP_SECRET
    assert captured["json"]["person"]["id"] == str(p.id)
    assert captured["json"]["person"]["show_in_directory"] is True
    assert captured["json"]["assignments"][0]["org_type"] == org.org_type
    assert captured["json"]["assignments"][0]["job_title"] == "Deputy"


def test_incremental_sync_uses_outbound_secret(as_editor, settings, monkeypatch):
    settings.WP_SYNC_TRIGGER_URL_BY_TENANT = {"VBC": VBC_TRIGGER}
    settings.WP_SYNC_TRIGGER_SECRET = WP_SECRET
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr("wordpress.services.httpx.post", fake_post)
    r = as_editor.post("/api/wordpress/incremental-sync")
    assert r.status_code == 200
    assert captured["url"] == VBC_TRIGGER
    assert captured["headers"]["X-County-Directory-Admin-Secret"] == WP_SECRET


def test_force_sync_unknown_person_is_404(as_editor, settings, monkeypatch):
    settings.WP_SYNC_TRIGGER_URL_BY_TENANT = {"VBC": VBC_TRIGGER}
    settings.WP_SYNC_TRIGGER_SECRET = WP_SECRET
    captured = []

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(url)
        return _FakeResp()

    monkeypatch.setattr("wordpress.services.httpx.post", fake_post)
    r = as_editor.post(f"/api/wordpress/people/{uuid4()}/sync")
    assert r.status_code == 404
    assert captured == []


def test_sync_organizations_and_assignments(client, settings):
    settings.SYNC_API_SECRET = SYNC_SECRET
    org = make_org(name="Clerk")
    person = make_person()
    Assignment.objects.create(tenant_id="VBC", org=org, person=person, job_title="Deputy")
    headers = {"HTTP_AUTHORIZATION": f"Bearer {SYNC_SECRET}"}
    orgs = client.get("/sync/organizations", {"tenant_id": "VBC"}, **headers)
    assert orgs.status_code == 200
    assert orgs.json()["items"][0]["name"] == "Clerk"
    assert orgs.json()["items"][0]["tenant_id"] == "VBC"
    assigns = client.get("/sync/assignments", {"tenant_id": "VBC"}, **headers)
    assert assigns.status_code == 200
    item = assigns.json()["items"][0]
    assert item["job_title"] == "Deputy"
    assert item["org_type"] == "department"
    assert item["person_id"] == str(person.id)


def test_reconciliation_report_uses_outbound_secret(as_editor, settings, monkeypatch):
    settings.WP_SYNC_TRIGGER_URL_BY_TENANT = {"VBC": VBC_TRIGGER}
    settings.WP_SYNC_TRIGGER_SECRET = WP_SECRET
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr("wordpress.services.httpx.post", fake_post)
    r = as_editor.post("/api/wordpress/reconciliation-report")
    assert r.status_code == 200
    assert captured["url"] == "https://vbc.example.test/wp-json/county/v1/reconciliation-report"
    assert captured["headers"]["X-County-Directory-Admin-Secret"] == WP_SECRET
