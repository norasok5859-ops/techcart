from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from store.urls import api_patterns, dashboard_patterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include(dashboard_patterns)),
    path("api/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("", include("store.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if not settings.DEBUG:
    # Product photos in media/ are part of the demo, so serve them in production too (Vercel).
    urlpatterns.insert(0, re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}))
