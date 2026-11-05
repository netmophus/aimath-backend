"""Rafraîchissement de jeton refusé si le mot de passe a changé depuis l'émission (voir authentification.py)."""

from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.views import TokenRefreshView

from .authentification import MESSAGE, jeton_perime


class RefreshVersionneSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        from comptes.models import User

        refresh = self.token_class(attrs["refresh"])   # signature et expiration vérifiées ici
        identifiant = refresh.get(api_settings.USER_ID_CLAIM)
        utilisateur = User.objects.filter(**{api_settings.USER_ID_FIELD: identifiant}).first()
        if utilisateur is None or jeton_perime(refresh, utilisateur):
            raise InvalidToken(MESSAGE)
        return super().validate(attrs)


class RefreshVersionneView(TokenRefreshView):
    serializer_class = RefreshVersionneSerializer
