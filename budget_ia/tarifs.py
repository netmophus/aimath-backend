"""
Tarifs Anthropic (USD par million de tokens) et conversion FCFA.

SOURCE : https://platform.claude.com/docs/en/about-claude/pricing (consultée le 2026-11-03).
Identifiants vérifiés (docs models/overview, sonnet-5 et sonnet-5-5, le 2026-11-03) :
  - `claude-sonnet-5` : actif mais LEGACY (retrait au plus tôt le 2027-06-30) ;
  - `claude-sonnet-5-5` : modèle Sonnet ACTUEL (retrait au plus tôt le 2027-09-28), mêmes prix entrée/sortie, cache lecture moitié moins cher.
PDF : « standard API pricing, no additional PDF fees » (tokens de texte + tokens d'image par page) ; image : ceil(l/28) x ceil(h/28) tokens.
Un modèle absent de cette table est REFUSÉ : on n'invente jamais un prix.
Surcharge possible sans toucher au code : IA_TARIFS_USD (JSON) dans l'environnement.
Les images et PDF sont facturés comme des tokens d'entrée (aucune ligne distincte sur la page officielle).
"""

from decimal import Decimal

from django.conf import settings

from programme.ia.exceptions import IAConfigurationInvalide

UNITE = Decimal(1_000_000)

TARIFS_PAR_DEFAUT = {
    # Claude Sonnet 5 : 2 $ entrée, 10 $ sortie (tarif standard depuis le 2026-08-31), cache lecture 0,20 $.
    "claude-sonnet-5": {"entree": "2", "sortie": "10", "cache_ecriture_5m": "2.5", "cache_ecriture_1h": "4", "cache_lecture": "0.2"},
    # Claude Sonnet 5.5 : mêmes tarifs entrée/sortie, cache lecture 0,10 $.
    "claude-sonnet-5-5": {"entree": "2", "sortie": "10", "cache_ecriture_5m": "2.5", "cache_ecriture_1h": "4", "cache_lecture": "0.1"},
}


class ModeleNonTarife(IAConfigurationInvalide):
    """Aucun tarif vérifié pour ce modèle : l'appel est refusé tant que le tarif n'est pas renseigné."""


def tarif(modele: str) -> dict:
    table = getattr(settings, "IA_TARIFS_USD", None) or TARIFS_PAR_DEFAUT
    brut = table.get(modele)
    if not brut:
        raise ModeleNonTarife(f"Aucun tarif vérifié pour le modèle « {modele} » : appel refusé.")
    return {cle: Decimal(str(valeur)) for cle, valeur in brut.items()}


def taux_usd_fcfa() -> Decimal:
    taux = Decimal(str(settings.IA_TAUX_USD_FCFA))
    if taux <= 0:
        raise IAConfigurationInvalide("Taux USD/FCFA invalide.")
    return taux


def marge() -> Decimal:
    return Decimal(str(settings.IA_MARGE_SECURITE))


def cout_usd(modele: str, *, entree=0, sortie=0, cache_ecriture=0, cache_lecture=0) -> Decimal:
    t = tarif(modele)
    return (
        Decimal(entree or 0) * t["entree"]
        + Decimal(sortie or 0) * t["sortie"]
        + Decimal(cache_ecriture or 0) * t["cache_ecriture_5m"]
        + Decimal(cache_lecture or 0) * t["cache_lecture"]
    ) / UNITE


def usd_vers_fcfa(usd: Decimal) -> Decimal:
    """USD -> FCFA, taux configurable ET marge de sécurité incluse (estimation prudente)."""
    return (usd * taux_usd_fcfa() * (Decimal(1) + marge())).quantize(Decimal("0.0001"))
