from datetime import timedelta
from uuid import uuid4

from django.core.management import call_command
from django.utils import timezone

from accounts.backends import MagicLinkBackend
from accounts.email import send_email
from accounts.models import MagicLinkToken
from tests.conftest import make_org, make_person


def test_seed_groups_command(db):
    call_command("seed_groups")
    from django.contrib.auth.models import Group

    assert Group.objects.filter(name="directory_editor").exists()


def test_magic_link_expired(editor):
    token = MagicLinkToken.objects.create(
        token="expired-token-value-0123456789abcdef0123456789ab",
        user=editor,
        email=editor.email,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    assert MagicLinkBackend().authenticate(None, token=token.token) is None


def test_send_email_posts(monkeypatch, settings):
    settings.WP_EMAIL_ENDPOINT = "https://example.test/send-email"
    settings.COUNTY_SEND_EMAIL_API_KEY = "k"

    class Resp:
        status_code = 200

        def json(self):
            return {"success": True, "message": "ok"}

        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def post(self, url, json=None, headers=None):
            assert url.endswith("send-email")
            assert headers["X-API-Key"] == "k"
            return Resp()

    monkeypatch.setattr("accounts.email.httpx.Client", Client)
    out = send_email("a@example.test", "Hi", "<p>x</p>")
    assert out["success"] is True


def test_org_people_list(as_editor):
    org = make_org()
    r = as_editor.get(f"/api/orgs/{org.id}/people")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_get_person_detail_and_unassigned(as_editor):
    org = make_org()
    p = make_person()
    detail = as_editor.get(f"/api/people/{p.id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == str(p.id)
    assert "display_name" in detail.json()
    assert detail.json()["full_name"] == p.full_name
    una = as_editor.get(f"/api/orgs/{org.id}/people/unassigned")
    assert una.status_code == 200
    assert any(i["id"] == str(p.id) for i in una.json()["items"])


def test_patch_assignment_and_open_list(as_editor):
    org = make_org()
    created = as_editor.post(
        f"/api/orgs/{org.id}/assignments",
        data={"job_title": "Chair"},
        content_type="application/json",
    )
    aid = created.json()["assignment"]["id"]
    patched = as_editor.patch(
        f"/api/assignments/{aid}",
        data={"status": "active"},
        content_type="application/json",
    )
    assert patched.status_code == 200
    open_r = as_editor.get("/api/assignments/open")
    assert any(i["id"] == aid for i in open_r.json()["items"])


def test_get_org_and_parent_family_rejected(as_editor):
    dept = make_org(name="Dept", org_type="department", slug="dept-x")
    board = make_org(name="Board", org_type="board", slug="board-x")
    got = as_editor.get(f"/api/orgs/{dept.id}")
    assert got.status_code == 200
    r = as_editor.patch(
        f"/api/orgs/{dept.id}",
        data={"parent_id": str(board.id)},
        content_type="application/json",
    )
    assert r.status_code == 400


def test_permissions_search_and_revoke(as_editor, editor):
    from django.conf import settings
    from accounts.services import grant_directory_group

    grant_directory_group(editor.person, settings.GROUP_PERMISSIONS_ADMIN, "VBC")
    search = as_editor.get("/api/permissions/people?q=ada")
    assert search.status_code == 200
    target = make_person(email_public="revokee@example.test")
    as_editor.post(
        f"/api/permissions/people/{target.id}/caps",
        data={"cap_key": settings.GROUP_DIRECTORY_EDITOR},
        content_type="application/json",
    )
    revoked = as_editor.delete(
        f"/api/permissions/people/{target.id}/caps/{settings.GROUP_DIRECTORY_EDITOR}"
    )
    assert revoked.status_code == 200


def test_spa_index(client):
    r = client.get("/login")
    assert r.status_code == 200


def test_try_push_swallows_http_error(settings):
    from wordpress.services import try_push_person_to_wordpress

    settings.WP_SYNC_TRIGGER_SECRET = None
    try_push_person_to_wordpress("VBC", uuid4())


def test_sync_invalid_updated_since(client, settings):
    settings.SYNC_API_SECRET = "s"
    r = client.get(
        "/sync/people",
        {"tenant_id": "VBC", "updated_since": "not-a-date"},
        HTTP_AUTHORIZATION="Bearer s",
    )
    assert r.status_code == 400


def test_set_active_tenant(as_editor):
    r = as_editor.post(
        "/api/auth/active-tenant",
        data={"tenant_id": "SJC"},
        content_type="application/json",
    )
    assert r.status_code == 400


def test_verify_used_token(client, editor):
    from datetime import timedelta
    from django.utils import timezone
    from accounts.models import MagicLinkToken
    import secrets

    token = secrets.token_urlsafe(32)[:64]
    MagicLinkToken.objects.create(
        token=token,
        user=editor,
        email=editor.email,
        expires_at=timezone.now() + timedelta(hours=1),
        used_at=timezone.now(),
    )
    r = client.get(f"/api/auth/verify?token={token}")
    assert r.status_code == 400
