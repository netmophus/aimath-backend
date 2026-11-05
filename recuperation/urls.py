from django.urls import path

from . import views

app_name = "recuperation"

urlpatterns = [
    path("demander/", views.DemanderCodeView.as_view(), name="demander"),
    path("verifier/", views.VerifierCodeView.as_view(), name="verifier"),
    path("reinitialiser/", views.ReinitialiserView.as_view(), name="reinitialiser"),
]
