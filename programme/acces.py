"""
Logique d'accès aux leçons (verrouillage gratuit/premium).

Centralise LA règle d'autorisation dans une seule fonction, utilisée par le
serializer élève (programme/eleve_serializers.py) — et par n'importe quel
futur endpoint qui aurait besoin de la même décision, jamais dupliquée.

POINT CRITIQUE : le verrou se joue ICI, côté serveur, jamais côté affichage.
Un appelant qui a `eleve_peut_acceder() == False` ne doit RECEVOIR aucun
contenu premium (pas seulement se le voir masquer à l'écran) — voir
LeconEleveSerializer.to_representation, qui tronque/vide les champs plutôt
que de les renvoyer et les cacher côté front.
"""

from comptes.models import User

from .models import Lecon


def eleve_peut_acceder(user: User, lecon: Lecon) -> bool:
    """Une leçon est accessible EN ENTIER si elle est gratuite, si
    l'utilisateur a un abonnement actif, ou s'il s'agit d'un admin/enseignant
    (jamais bridés par le verrou premium, qui ne concerne que l'espace
    élève — voir LeconViewSet, réservé à IsAdminRole, qui n'appelle jamais
    cette fonction)."""
    if lecon.est_gratuit:
        return True
    if user.role in (User.Role.ADMIN, User.Role.ENSEIGNANT):
        return True
    return user.a_un_abonnement_actif
