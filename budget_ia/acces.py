"""
Liste blanche de comptes pour les fonctions IA (« mode pilote »).

Réglage : IA_COMPTES_AUTORISES = téléphones d'élèves séparés par des virgules (variable d'environnement).

  - Liste VIDE (défaut) : comportement historique, rien ne change (les IA_*_ACTIVE et IA_*_DEV_SEULEMENT décident).
  - Liste NON VIDE (mode pilote) : une fonction IA n'est ouverte qu'aux élèves actifs de cette liste, à condition que son
    drapeau IA_*_ACTIVE soit vrai et l'interrupteur global ouvert. IA_*_DEV_SEULEMENT (qui exige DEBUG) est alors remplacé
    par la liste. Tous les autres élèves restent comme si l'IA était désactivée.

Fermé par défaut : une liste mal saisie (numéro inexistant, faute de frappe) n'ouvre rien à personne d'autre. Le contrôle
est appliqué deux fois : aux portes d'entrée (vues : disponibilité et refus précoce) ET dans `budget_ia.service.ouvrir`,
point de passage de TOUT appel payant (y compris l'exécution différée par le worker), si bien qu'un compte retiré de la
liste après la mise en file n'atteint jamais le fournisseur.
"""

from __future__ import annotations

import re

from django.conf import settings

# Même format que comptes.models.telephone_validator : validation STRICTE, aucune correction automatique (pas de « + »
# ajouté, pas de troncature). Une entrée qui n'est pas exactement +227 suivi de 8 chiffres est ignorée.
FORMAT_TELEPHONE = re.compile(r"^\+227\d{8}$")


def _normaliser(telephone: str) -> str:
    # Même normalisation que comptes.models.UserManager.normalize_telephone.
    return (telephone or "").strip().replace(" ", "")


def _entrees() -> list[str]:
    brut = getattr(settings, "IA_COMPTES_AUTORISES", None) or []
    if isinstance(brut, str):
        brut = brut.split(",")
    return [t for t in (_normaliser(x) for x in brut) if t]


def comptes_autorises() -> frozenset[str]:
    """Numéros VALIDES de la liste blanche (les entrées mal formées sont ignorées)."""
    return frozenset(t for t in _entrees() if FORMAT_TELEPHONE.match(t))


def entrees_invalides() -> int:
    """Nombre d'entrées mal formées (jamais les valeurs elles-mêmes : ce sont des numéros)."""
    return sum(1 for t in _entrees() if not FORMAT_TELEPHONE.match(t))


def mode_pilote() -> bool:
    """Vrai dès que la variable contient QUELQUE CHOSE, même mal formé : une liste erronée ferme l'accès, elle ne l'ouvre pas."""
    return bool(_entrees())


def compte_autorise(utilisateur_id: int | None) -> bool:
    """Vrai si ce compte est un élève actif de la liste blanche. Faux sans identité (fermé par défaut)."""
    if not utilisateur_id:
        return False
    liste = comptes_autorises()
    if not liste:
        return False      # mode pilote sans aucun numéro valide : personne
    from comptes.models import User

    return User.objects.filter(pk=utilisateur_id, telephone__in=liste, role=User.Role.ELEVE, is_active=True).exists()


def fonction_ouverte(drapeau_actif: bool, dev_seulement: bool, utilisateur_id: int | None = None) -> bool:
    """Décision commune aux trois fonctions (lecture, correction, fahimta ai)."""
    if not settings.IA_INTERRUPTEUR_GLOBAL or not drapeau_actif:
        return False
    if mode_pilote():
        return compte_autorise(utilisateur_id)
    if dev_seulement and not settings.DEBUG:
        return False
    return True
