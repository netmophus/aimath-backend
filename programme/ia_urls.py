from django.urls import path

from .ia_views import GenererSectionView, VerifierContenuView

app_name = "programme_ia_admin"

urlpatterns = [
    path("generer/", GenererSectionView.as_view(), name="generer"),
    path("verifier/", VerifierContenuView.as_view(), name="verifier"),
]
