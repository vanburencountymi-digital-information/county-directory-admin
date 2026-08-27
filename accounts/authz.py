from ninja.security import HttpBearer
from django.conf import settings
from django.contrib.auth.models import Group
from ninja.errors import HttpError

from accounts.models import TenantMembership


class SyncApiBearerAuth(HttpBearer):
    """Inbound county-core pull. Independent of django.contrib.auth."""

    def authenticate(self, request, token: str):
        secret = settings.SYNC_API_SECRET
        if not secret or token != secret:
            return None
        return token


def actor_label(request) -> str:
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return user.email or str(user.pk)
    return "unknown"


def require_directory_editor(request) -> str:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        raise HttpError(401, "Not authenticated")
    if not user.groups.filter(name=settings.GROUP_DIRECTORY_EDITOR).exists():
        raise HttpError(403, "Directory editing is not enabled for your account.")
    tenant = request.session.get("active_tenant_id")
    if not tenant:
        raise HttpError(401, "Session expired or invalid tenant — sign in again.")
    if not TenantMembership.objects.filter(user=user, tenant_id=tenant).exists():
        raise HttpError(401, "Session expired or invalid tenant — sign in again.")
    return tenant


def require_permissions_admin(request) -> str:
    tenant = require_directory_editor(request)
    if not request.user.groups.filter(name=settings.GROUP_PERMISSIONS_ADMIN).exists():
        raise HttpError(403, "Permissions management is not enabled for your account.")
    return tenant


def is_permissions_admin(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=settings.GROUP_PERMISSIONS_ADMIN).exists()
