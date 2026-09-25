from django.urls import path

from .nita_views import NitaCallbackView, NitaMockConfirmerView

app_name = "nita"

urlpatterns = [
    # PUBLIC (voir NitaCallbackView) — jamais sous /api/eleve/ ou /api/admin/.
    path("callback/", NitaCallbackView.as_view(), name="callback"),
    # Réservé admin, inerte hors NITA_MOCK=1 (voir NitaMockConfirmerView).
    path("mock/confirmer/", NitaMockConfirmerView.as_view(), name="mock-confirmer"),
]
