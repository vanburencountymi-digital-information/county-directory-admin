import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.authz import is_permissions_admin, require_directory_editor
from accounts.email import send_email
from accounts.models import MagicLinkToken, TenantMembership, User
from people.models import Person

from .services import upgrade_person_to_user

logger = logging.getLogger(__name__)
router = Router(tags=["auth"])


class OTPRequest(Schema):
    email: str


class ActiveTenantBody(Schema):
    tenant_id: str


def _error_page(title: str, message: str) -> HttpResponse:
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;display:flex;min-height:100vh;align-items:center;justify-content:center;background:#f5f5f5;margin:0}}
.box{{background:#fff;padding:2rem;border-radius:8px;max-width:420px;box-shadow:0 2px 10px rgba(0,0,0,.08)}}
h1{{color:#c00;font-size:1.25rem}}p{{color:#555}}</style></head><body>
<div class="box"><h1>{title}</h1><p>{message}</p><p><a href="/">Back to sign in</a></p></div></body></html>"""
    return HttpResponse(html, status=400)


@router.post("/request-otp")
def request_otp(request, payload: OTPRequest):
    email = payload.email.lower().strip()
    tenants = list(settings.DIRECTORY_EDITABLE_TENANT_IDS)
    people = list(
        Person.objects.filter(
            email_public__iexact=email,
            archived_at__isnull=True,
            tenant_id__in=tenants,
        ).order_by("tenant_id")
    )
    chosen = None
    for person in people:
        user = User.objects.filter(person=person).first()
        if user and user.groups.filter(name=settings.GROUP_DIRECTORY_EDITOR).exists():
            if TenantMembership.objects.filter(user=user, tenant_id=person.tenant_id).exists():
                chosen = (person, user)
                break
    if chosen:
        person, user = chosen
        token = secrets.token_urlsafe(32)[:64]
        MagicLinkToken.objects.create(
            token=token,
            user=user,
            email=email,
            expires_at=timezone.now() + timedelta(hours=settings.OTP_EXPIRY_HOURS),
        )
        base_url = settings.BASE_URL
        if not base_url:
            base_url = request.build_absolute_uri("/").rstrip("/")
            logger.warning("BASE_URL not set, using request host: %s", base_url)
        verify_url = f"{base_url}/api/auth/verify?token={token}"
        body = f"""<html><body>
<p>Hello {person.full_name or ""},</p>
<p><a href="{verify_url}">Log in to Directory Admin</a></p>
<p style="color:#666;font-size:12px;word-break:break-all;">{verify_url}</p>
<p>This link expires in {settings.OTP_EXPIRY_HOURS} hour(s).</p>
<p>Because Directory Admin moved to a new sign-in system, previous sessions no longer work.
Request a new link if you were signed in on the old site.</p>
</body></html>"""
        try:
            send_email(to=email, subject="Your login link — Directory Admin", body=body)
        except Exception:
            logger.exception("Failed to send OTP email to %s", email)
    return {
        "success": True,
        "message": "If this email is registered, you will receive a login link shortly.",
    }


@router.get("/verify")
def verify_otp(request, token: str):
    from django.contrib.auth import authenticate

    user = authenticate(request, token=token)
    if user is None:
        # Distinguish used/expired for friendlier pages when possible
        rec = MagicLinkToken.objects.filter(token=token).first()
        if rec is None:
            resp = _error_page("Invalid link", "This login link is not valid.")
            resp.status_code = 400
            return resp
        if rec.used_at is not None:
            resp = _error_page("Link already used", "Request a new login link from the sign-in page.")
            resp.status_code = 400
            return resp
        resp = _error_page("Link expired", "Request a new login link from the sign-in page.")
        resp.status_code = 400
        return resp
    if not user.groups.filter(name=settings.GROUP_DIRECTORY_EDITOR).exists():
        resp = _error_page(
            "No access",
            "Your account does not have permission to use Directory Admin. "
            "Contact your administrator if you believe this is a mistake.",
        )
        resp.status_code = 403
        return resp
    memberships = list(TenantMembership.objects.filter(user=user).values_list("tenant_id", flat=True))
    editable = [t for t in settings.DIRECTORY_EDITABLE_TENANT_IDS if t in memberships]
    if not editable:
        resp = _error_page("No access", "No tenant membership is configured for your account.")
        resp.status_code = 403
        return resp
    login(request, user, backend="accounts.backends.MagicLinkBackend")
    person_tenant = user.person.tenant_id
    active = person_tenant if person_tenant in editable else editable[0]
    request.session["active_tenant_id"] = active
    return HttpResponseRedirect("/")


@router.post("/active-tenant")
def set_active_tenant(request, payload: ActiveTenantBody):
    require_directory_editor(request)
    allowed = list(
        TenantMembership.objects.filter(user=request.user).values_list("tenant_id", flat=True)
    )
    if payload.tenant_id not in allowed:
        raise HttpError(400, "You cannot switch to that tenant.")
    request.session["active_tenant_id"] = payload.tenant_id
    return {"ok": True, "active_tenant_id": payload.tenant_id}


session_router = Router(tags=["session"])


@session_router.get("/me")
def me(request):
    tenant = require_directory_editor(request)
    user = request.user
    allowed = list(
        TenantMembership.objects.filter(user=user).values_list("tenant_id", flat=True)
    )
    return {
        "person_id": str(user.person_id),
        "name": user.person.full_name,
        "email": user.email,
        "active_tenant_id": tenant,
        "allowed_tenant_ids": allowed,
        "permissions_admin": is_permissions_admin(user),
    }
