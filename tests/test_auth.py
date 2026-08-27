from django.conf import settings

from tests.conftest import make_person


def test_me_requires_login(client):
    r = client.get("/api/me")
    assert r.status_code == 401


def test_me_ok(as_editor, editor):
    r = as_editor.get("/api/me")
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == editor.email
    assert body["active_tenant_id"] == "VBC"
    assert body["permissions_admin"] is False


def test_request_otp_does_not_enumerate(client, editor):
    r = client.post(
        "/api/auth/request-otp",
        data={"email": "nobody@example.test"},
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_request_otp_creates_token(client, editor, monkeypatch):
    sent = {}

    def fake_send(**kwargs):
        sent.update(kwargs)
        return {"success": True}

    monkeypatch.setattr("accounts.api.send_email", fake_send)
    r = client.post(
        "/api/auth/request-otp",
        data={"email": editor.email},
        content_type="application/json",
    )
    assert r.status_code == 200
    from accounts.models import MagicLinkToken

    assert MagicLinkToken.objects.filter(user=editor).exists()
    assert sent.get("to") == editor.email


def test_verify_logs_in(client, editor):
    from django.utils import timezone
    from datetime import timedelta
    from accounts.models import MagicLinkToken
    import secrets

    token = secrets.token_urlsafe(32)[:64]
    MagicLinkToken.objects.create(
        token=token,
        user=editor,
        email=editor.email,
        expires_at=timezone.now() + timedelta(hours=1),
    )
    r = client.get(f"/api/auth/verify?token={token}")
    assert r.status_code in (302, 303)
    me = client.get("/api/me")
    assert me.status_code == 200
