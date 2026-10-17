"""Versioned routes; schema is only served in the explicit local environment."""

from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import AllowAny

from .health import HealthView, ReadinessView

urlpatterns = [
    path("api/v1/clubs/", include("clubs.api")),
    path("api/v1/activities/", include("activities.api")),
    path("api/v1/admin/integrations/hemis/", include("integrations.hemis.api")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/health/", HealthView.as_view(), name="health"),
    path("api/v1/ready/", ReadinessView.as_view(), name="ready"),
]
if settings.EXPOSE_API_SCHEMA:
    urlpatterns.append(
        path(
            "api/v1/schema/",
            SpectacularAPIView.as_view(permission_classes=[AllowAny], authentication_classes=[]),
            name="schema",
        )
    )
handler404 = "config.errors.not_found"
handler500 = "config.errors.server_error"
