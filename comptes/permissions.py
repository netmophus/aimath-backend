from rest_framework.permissions import BasePermission

from .models import User


class IsAdminRole(BasePermission):
    """
    Autorise uniquement les utilisateurs authentifiés dont le RÔLE MÉTIER
    est "admin" (champ User.role) — volontairement indépendant de
    is_staff/is_superuser, qui ne concernent que l'accès à l'admin Django.
    """

    message = "Réservé aux administrateurs."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)


class IsVendeurActif(BasePermission):
    """
    Autorise uniquement les vendeurs (User.Role.VENDEUR) au statut "actif" —
    même garde qu'IsEleveActif, pour la même raison (double sécurité, ne
    repose pas uniquement sur le fait que la connexion refuse déjà les
    comptes non actifs).
    """

    message = "Réservé aux vendeurs actifs."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.Role.VENDEUR
            and user.statut == User.Statut.ACTIF
        )


class IsEleveActif(BasePermission):
    """
    Autorise uniquement les élèves (User.Role.ELEVE) au statut "actif".

    Double sécurité côté API : la connexion (TelephoneTokenObtainPairSerializer)
    refuse déjà d'émettre des jetons pour un compte non actif, donc en théorie
    un élève en_attente/rejeté/suspendu n'a pas de jeton — mais on ne fait
    jamais reposer la sécurité d'un endpoint uniquement sur ce qui se passe
    ailleurs dans le code.
    """

    message = "Réservé aux élèves actifs."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.Role.ELEVE
            and user.statut == User.Statut.ACTIF
        )
