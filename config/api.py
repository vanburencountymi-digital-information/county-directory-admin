from ninja import NinjaAPI
from ninja.errors import HttpError

from accounts.api import router as auth_router
from accounts.api import session_router
from accounts.permissions_api import router as permissions_router
from assignments.api import router as assignments_router
from audit.api import router as audit_router
from organizations.api import router as orgs_router
from people.api import router as people_router
from wordpress.api import clerk_router, sync_router

api = NinjaAPI(title="County Directory", version="0.1.0")


@api.exception_handler(HttpError)
def http_error(request, exc: HttpError):
    return api.create_response(request, {"detail": str(exc)}, status=exc.status_code)


api.add_router("/api/auth", auth_router)
api.add_router("/api", session_router)
api.add_router("/api", people_router)
api.add_router("/api", orgs_router)
api.add_router("/api", assignments_router)
api.add_router("/api/audit", audit_router)
api.add_router("/api/permissions", permissions_router)
api.add_router("/api/wordpress", clerk_router)
api.add_router("/sync", sync_router)


@api.get("/health")
def health(request):
    return {"status": "ok"}
