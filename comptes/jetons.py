"""Émission des jetons avec la version du mot de passe (voir authentification.py)."""

from rest_framework_simplejwt.tokens import RefreshToken

from .authentification import REVENDICATION


class RefreshVersionne(RefreshToken):
    @classmethod
    def for_user(cls, user):
        jeton = super().for_user(user)
        jeton[REVENDICATION] = user.version_mot_de_passe or 0
        return jeton
