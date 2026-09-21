from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .glossaire_views import TermeGlossaireViewSet
from .lecon_views import LeconViewSet
from .programme_views import ChapitreViewSet, NotionViewSet, ProgrammeViewSet, ThemeViewSet

router = DefaultRouter()
router.register("programmes", ProgrammeViewSet, basename="admin-programmes")
router.register("themes", ThemeViewSet, basename="admin-themes")
router.register("chapitres", ChapitreViewSet, basename="admin-chapitres")
router.register("notions", NotionViewSet, basename="admin-notions")
router.register("lecons", LeconViewSet, basename="admin-lecons")
router.register("glossaire", TermeGlossaireViewSet, basename="admin-glossaire")

app_name = "programme_hierarchie_admin"

urlpatterns = [
    path("", include(router.urls)),
]
