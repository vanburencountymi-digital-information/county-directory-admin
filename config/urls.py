from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import path, re_path
from config.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", api.urls),
]


def spa_index(_request):
    dist = settings.BASE_DIR / "frontend" / "dist" / "index.html"
    static_index = settings.BASE_DIR / "staticfiles" / "index.html"
    for candidate in (dist, static_index):
        if candidate.is_file():
            return FileResponse(candidate.open("rb"))
    return HttpResponse(
        '{"message": "County Directory API — build frontend to enable UI."}',
        content_type="application/json",
    )


urlpatterns += [
    re_path(r"^(?!api/|sync/|admin/|health|static/|assets/).*$", spa_index),
]
