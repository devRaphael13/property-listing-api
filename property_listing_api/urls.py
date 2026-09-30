"""Root URL configuration.

The `handler*` hooks below make Django's own 400/404/500 responses speak the same
JSON envelope as the REST API, for /api/ paths only (so /admin/ keeps its HTML).
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.renderers import OpenApiJsonRenderer, OpenApiYamlRenderer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from listings.exceptions import error_payload

API_PREFIX = "/api/"


def _is_api_request(request):
    return request.path.startswith(API_PREFIX)


def _json_error(request, status_code, code, message):
    if not _is_api_request(request):
        return None
    return JsonResponse(error_payload(code, message, status_code=status_code), status=status_code)


def bad_request(request, exception):
    response = _json_error(request, 400, "bad_request", "Malformed request.")
    if response is not None:
        return response
    from django.views.defaults import bad_request as django_bad_request

    return django_bad_request(request, exception)


def page_not_found(request, exception):
    response = _json_error(request, 404, "not_found", f"No route matches {request.path}.")
    if response is not None:
        return response
    from django.views.defaults import page_not_found as django_page_not_found

    return django_page_not_found(request, exception)


def server_error(request):
    response = _json_error(
        request, 500, "server_error", "Internal server error. Please try again later."
    )
    if response is not None:
        return response
    from django.views.defaults import server_error as django_server_error

    return django_server_error(request)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("listings.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Fixed extensions, so CI or a client generator can fetch a stable URL.
    path(
        "api/schema.json",
        SpectacularAPIView.as_view(renderer_classes=[OpenApiJsonRenderer]),
        name="schema-json",
    ),
    path(
        "api/schema.yaml",
        SpectacularAPIView.as_view(renderer_classes=[OpenApiYamlRenderer]),
        name="schema-yaml",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

handler400 = "property_listing_api.urls.bad_request"
handler404 = "property_listing_api.urls.page_not_found"
handler500 = "property_listing_api.urls.server_error"
