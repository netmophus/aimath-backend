from django.urls import path

from comptes.nita_views import InitierPaiementNitaView, VerifierPaiementNitaView
from comptes.views import ActiverCarteView, MesCartesEleveView, ProfilEleveView

from .eleve_views import (
    LeconEleveDetailView,
    MesLeconsView,
    MonProgrammeView,
    ProgrammeDetailEleveView,
    TermeGlossaireEleveDetailView,
    TermeGlossaireEleveListeView,
)

app_name = "eleve"

urlpatterns = [
    path("mon-programme/", MonProgrammeView.as_view(), name="mon-programme"),
    path("programmes/<int:id>/", ProgrammeDetailEleveView.as_view(), name="programme-detail"),
    path("lecons/<int:id>/", LeconEleveDetailView.as_view(), name="lecon-detail"),
    path("mes-lecons/", MesLeconsView.as_view(), name="mes-lecons"),
    path("glossaire/", TermeGlossaireEleveListeView.as_view(), name="glossaire-liste"),
    path("glossaire/<slug:slug>/", TermeGlossaireEleveDetailView.as_view(), name="glossaire-detail"),
    # Défini dans comptes/ (porte sur le modèle User), exposé ici pour
    # rester sous le même préfixe /api/eleve/ que le reste de cet espace.
    path("profil/", ProfilEleveView.as_view(), name="profil"),
    path("activer-carte/", ActiverCarteView.as_view(), name="activer-carte"),
    path("mes-cartes/", MesCartesEleveView.as_view(), name="mes-cartes"),
    # Idem : défini dans comptes/nita_views.py (paiement NITA), exposé ici.
    path("nita/initier/", InitierPaiementNitaView.as_view(), name="nita-initier"),
    path("nita/verifier/", VerifierPaiementNitaView.as_view(), name="nita-verifier"),
]
