from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .admin_views import CycleViewSet, MatiereViewSet, NiveauViewSet, SerieViewSet

router = DefaultRouter()
router.register("cycles", CycleViewSet, basename="admin-cycles")
router.register("niveaux", NiveauViewSet, basename="admin-niveaux")
router.register("series", SerieViewSet, basename="admin-series")
router.register("matieres", MatiereViewSet, basename="admin-matieres")

app_name = "programme_admin"

urlpatterns = [
    path("", include(router.urls)),
]
