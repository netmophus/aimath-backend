from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_cartes_views import CarteFahimtaAdminViewSet
from .admin_vendeurs_views import VendeurAdminViewSet
from .admin_views import AdminCompteViewSet, AdminStatsView

router = DefaultRouter()
router.register("comptes", AdminCompteViewSet, basename="admin-comptes")
router.register("cartes", CarteFahimtaAdminViewSet, basename="admin-cartes")
router.register("vendeurs", VendeurAdminViewSet, basename="admin-vendeurs")

app_name = "comptes_admin"

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="stats"),
    path("", include(router.urls)),
]
