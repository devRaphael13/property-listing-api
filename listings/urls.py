from django.urls import include, path
from rest_framework.routers import DefaultRouter

from listings.views import HealthView, ListingViewSet

router = DefaultRouter()
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = [
    path("", include(router.urls)),
    path("health/", HealthView.as_view(), name="health"),
]
