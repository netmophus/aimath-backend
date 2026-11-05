from django.urls import path

from .refresh import RefreshVersionneView
from .views import (
    ClassesPubliquesView,
    ChangerMotDePasseView,
    InscriptionEleveView,
    MeView,
    ModifierMotDePasseView,
    TelephoneTokenObtainPairView,
)

app_name = "comptes"

urlpatterns = [
    path("classes/", ClassesPubliquesView.as_view(), name="classes"),
    path("register/", InscriptionEleveView.as_view(), name="register"),
    path("login/", TelephoneTokenObtainPairView.as_view(), name="login"),
    path("refresh/", RefreshVersionneView.as_view(), name="refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("changer-mot-de-passe/", ChangerMotDePasseView.as_view(), name="changer-mot-de-passe"),
    path("modifier-mot-de-passe/", ModifierMotDePasseView.as_view(), name="modifier-mot-de-passe"),
]
