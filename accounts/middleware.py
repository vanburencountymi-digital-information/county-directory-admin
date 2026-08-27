from django.utils.deprecation import MiddlewareMixin


class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.active_tenant_id = None
        if hasattr(request, "session"):
            request.active_tenant_id = request.session.get("active_tenant_id")
