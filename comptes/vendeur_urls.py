from django.urls import path

from .vendeur_views import (
    MesCartesVendeurView,
    MoiVendeurView,
    VendreCarteView,
    VerifierEleveView,
)

app_name = "vendeur"

urlpatterns = [
    path("moi/", MoiVendeurView.as_view(), name="moi"),
    path("cartes/", MesCartesVendeurView.as_view(), name="cartes"),
    path("verifier-eleve/", VerifierEleveView.as_view(), name="verifier-eleve"),
    path("vendre-carte/", VendreCarteView.as_view(), name="vendre-carte"),
]
