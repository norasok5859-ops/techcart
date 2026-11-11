from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from store.media_views import media
from store.urls import api_patterns, dashboard_patterns

urlpatterns = [
    # Product photos: uploads kept in the database (Vercel) and the bundled files in media/.
    re_path(r"^media/(?P<path>.*)$", media, name="media"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("dashboard/", include(dashboard_patterns)),
    path("api/", include(api_patterns)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("", include("store.urls")),
]
