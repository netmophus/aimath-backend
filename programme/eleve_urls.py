from django.urls import path

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
]
