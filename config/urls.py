from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/admin/", include("apps.accounts.admin_urls")),
    path("api/admin/", include("apps.books.admin_urls")),
    path("api/", include("apps.books.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
