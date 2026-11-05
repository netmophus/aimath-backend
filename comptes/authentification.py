"""Jetons JWT liés à la version du mot de passe.

Constat d'audit : sans cela, changer ou réinitialiser un mot de passe ne coupait AUCUNE session existante (jetons d'accès
de 45 minutes et de rafraîchissement de 7 jours restaient valides, sans liste noire).

Mécanisme : `User.version_mot_de_passe` augmente de 1 à chaque `set_password`. Les jetons émis par la connexion et par
les parcours de changement portent la version courante dans la revendication `pv` ; un jeton dont la version diffère de
celle du compte est refusé, qu'il soit d'accès ou de rafraîchissement. L'accès créé par un rafraîchissement hérite de `pv`.

Pourquoi pas la date d'émission (`iat`) : elle n'a qu'une résolution d'une seconde. Un jeton émis dans la même seconde
qu'un changement de mot de passe ne pouvait pas être départagé (soit l'ancien jeton survivait, soit le nouveau était
refusé). Le compteur est exact, sans dépendre de l'horloge ni de la seconde.

Compatibilité : un jeton émis avant ce changement n'a pas de `pv` (lu comme 0) ; comme la colonne vaut 0 par défaut, il
reste valide tant que le compte n'a pas changé de mot de passe : personne n'est déconnecté au déploiement. Les durées de
vie des jetons ne changent pas.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

MESSAGE = "Session expirée : le mot de passe a été modifié. Reconnecte-toi."
REVENDICATION = "pv"


def jeton_perime(jeton, utilisateur) -> bool:
    """Vrai si la version portée par le jeton n'est plus celle du compte."""
    portee = jeton.get(REVENDICATION, 0)
    try:
        portee = int(portee)
    except (TypeError, ValueError):
        return True
    return portee != (getattr(utilisateur, "version_mot_de_passe", 0) or 0)


class JWTAuthenticationVersionnee(JWTAuthentication):
    def get_user(self, validated_token):
        utilisateur = super().get_user(validated_token)
        if jeton_perime(validated_token, utilisateur):
            raise InvalidToken(MESSAGE)
        return utilisateur
