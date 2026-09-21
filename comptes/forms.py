"""
Formulaires admin liés au User custom.

django.contrib.auth.admin.UserAdmin s'appuie par défaut sur des formulaires
(UserCreationForm/UserChangeForm) codés en dur sur le User standard de
Django (champ "username"). On les réécrit ici pour qu'ils pointent vers
notre modèle, où l'identifiant est "telephone".
"""

from django.contrib.auth.forms import BaseUserCreationForm
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm

from .models import User


class UserCreationForm(BaseUserCreationForm):
    """Formulaire de création d'un compte depuis l'admin Django."""

    class Meta:
        model = User
        fields = ("telephone", "prenom", "nom", "email", "role")


class UserChangeForm(DjangoUserChangeForm):
    """Formulaire d'édition d'un compte depuis l'admin Django."""

    class Meta:
        model = User
        fields = "__all__"
