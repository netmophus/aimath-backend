from django.urls import path

from .views import DemandeEleveDetailView, DemandesEleveView, PieceJointeEleveView

app_name = "aide_eleve"

urlpatterns = [
    path("demandes/", DemandesEleveView.as_view(), name="demandes"),
    path("demandes/<int:id>/", DemandeEleveDetailView.as_view(), name="demande"),
    path("demandes/<int:id>/piece-jointe/", PieceJointeEleveView.as_view(), name="piece-jointe"),
]
