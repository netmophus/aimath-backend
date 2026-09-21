from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import AdminCompteViewSet, AdminStatsView

router = DefaultRouter()
router.register("comptes", AdminCompteViewSet, basename="admin-comptes")

app_name = "comptes_admin"

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="stats"),
    path("", include(router.urls)),
]
