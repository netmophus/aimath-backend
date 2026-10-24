"""
Appel Anthropic du Professeur particulier : un SEUL appel, outil forcé (JSON
structuré), sans retry automatique (max_retries=0). Même mapping d'erreurs que
la lecture et la correction ; jamais la clé ni le contenu dans un message.

`appeler_outil` est la fonction que les tests remplacent : aucun test
automatique n'atteint le réseau.
"""

from __future__ import annotations

import logging

from django.conf import settings

from ..ia.exceptions import (
    IAConfigurationInvalide, IAErreurFournisseur, IAQuotaDepasse, IAReponseVide, IATimeout,
)
from ..lecture_exercice import LectureTropLongue

logger = logging.getLogger(__name__)


def appeler_outil(*, modele: str, systeme: str, outil: dict, message: str, max_tokens: int, etiquette: str) -> tuple[dict, dict]:
    """Renvoie (entrée de l'outil, {"tokens_entree", "tokens_sortie"})."""
    cle = settings.ANTHROPIC_API_KEY
    if not cle:
        raise IAConfigurationInvalide("Clé API Anthropic absente (ANTHROPIC_API_KEY dans le .env du serveur).")
    try:
        import anthropic
    except ImportError as exc:
        raise IAConfigurationInvalide("Le paquet Python 'anthropic' n'est pas installé sur le serveur.") from exc

    delai = float(settings.IA_PROF_TIMEOUT_SECONDES)
    client = anthropic.Anthropic(api_key=cle, timeout=delai, max_retries=0)
    try:
        reponse = client.messages.create(
            model=modele,
            max_tokens=max_tokens,
            system=systeme,
            tools=[outil],
            tool_choice={"type": "tool", "name": outil["name"]},
            messages=[{"role": "user", "content": message}],
        )
    except anthropic.AuthenticationError as exc:
        raise IAConfigurationInvalide("Clé API Anthropic refusée par le fournisseur.") from exc
    except anthropic.RateLimitError as exc:
        raise IAQuotaDepasse("Quota Anthropic atteint (429).") from exc
    except (anthropic.APITimeoutError, TimeoutError) as exc:
        raise IATimeout(f"Le fournisseur IA n'a pas répondu dans le délai imparti ({delai:.0f}s).") from exc
    except anthropic.APIConnectionError as exc:
        raise IAErreurFournisseur("Impossible de joindre le fournisseur IA.") from exc
    except anthropic.APIStatusError as exc:
        raise IAErreurFournisseur(f"Le fournisseur IA a répondu une erreur ({exc.status_code}).") from exc
    except anthropic.AnthropicError as exc:
        raise IAErreurFournisseur("Erreur inattendue côté fournisseur IA.") from exc

    usage = getattr(reponse, "usage", None)
    infos = {"tokens_entree": getattr(usage, "input_tokens", None) or 0, "tokens_sortie": getattr(usage, "output_tokens", None) or 0}
    stop_reason = getattr(reponse, "stop_reason", None)
    logger.info(
        "professeur %s anthropic modele=%s tokens_entree=%s tokens_sortie=%s stop_reason=%s",
        etiquette, modele, infos["tokens_entree"], infos["tokens_sortie"], stop_reason,
    )
    if stop_reason == "max_tokens":
        raise LectureTropLongue("La réponse du professeur est trop longue : reformule ou raccourcis ta demande.")
    for bloc in reponse.content:
        if getattr(bloc, "type", None) == "tool_use" and getattr(bloc, "name", None) == outil["name"] and isinstance(bloc.input, dict):
            return bloc.input, infos
    raise IAReponseVide("Le fournisseur IA n'a renvoyé aucune réponse exploitable.")
