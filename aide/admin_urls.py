from django.urls import path

from .views import DemandeAdminDetailView, DemandesAdminListeView, PieceJointeAdminView

app_name = "aide_admin"

urlpatterns = [
    path("demandes/", DemandesAdminListeView.as_view(), name="demandes"),
    path("demandes/<int:id>/", DemandeAdminDetailView.as_view(), name="demande"),
    path("demandes/<int:id>/piece-jointe/", PieceJointeAdminView.as_view(), name="piece-jointe"),
]
