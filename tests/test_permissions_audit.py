from django.conf import settings

from accounts.services import grant_directory_group
from tests.conftest import make_person


def test_grant_and_list_caps(as_editor, editor):
    grant_directory_group(editor.person, settings.GROUP_PERMISSIONS_ADMIN, "VBC")
    r = as_editor.get("/api/permissions/caps")
    assert r.status_code == 200
    keys = {i["cap_key"] for i in r.json()["items"]}
    assert settings.GROUP_DIRECTORY_EDITOR in keys


def test_grant_creates_user(as_editor, editor):
    grant_directory_group(editor.person, settings.GROUP_PERMISSIONS_ADMIN, "VBC")
    target = make_person(email_public="new-editor@example.test")
    r = as_editor.post(
        f"/api/permissions/people/{target.id}/caps",
        data={"cap_key": settings.GROUP_DIRECTORY_EDITOR},
        content_type="application/json",
    )
    assert r.status_code == 200
    target.refresh_from_db()
    assert hasattr(target, "user")
    caps = as_editor.get(f"/api/permissions/people/{target.id}/caps")
    assert any(c["cap_key"] == settings.GROUP_DIRECTORY_EDITOR for c in caps.json()["items"])


def test_audit_list(as_editor):
    as_editor.post(
        "/api/orgs",
        data={"name": "Audited", "org_type": "department"},
        content_type="application/json",
    )
    r = as_editor.get("/api/audit?limit=20")
    assert r.status_code == 200
    assert r.json()["items"]
