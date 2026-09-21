"""Couche fournisseur IA — point d'entrée UNIQUE pour interroger un modèle
de langage, quel que soit le fournisseur.

`appeler_ia(system_prompt, user_prompt)` lit IA_FOURNISSEUR/IA_MODELE dans
les réglages Django (donc dans .env, via python-decouple) et fait suivre au
bon SDK. Ajouter un fournisseur = ajouter une branche dans `appeler_ia` +
sa fonction `_appeler_xxx`, sans toucher au reste de l'app (prompts, vues).

Sécurité : la clé API n'est JAMAIS journalisée, ni renvoyée dans un message
d'erreur. Les exceptions levées ici sont toujours celles de
programme.ia.exceptions, avec un message FR sûr à afficher tel quel.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

from .exceptions import (
    IAConfigurationInvalide,
    IAErreurFournisseur,
    IAQuotaDepasse,
    IAReponseVide,
    IATimeout,
)


@dataclass(frozen=True)
class ReponseIA:
    """Résultat d'un appel IA : le texte généré + de quoi estimer un coût
    (voir programme.ia.cout), sans jamais transporter la clé API."""

    texte: str
    fournisseur: str
    modele: str
    tokens_entree: int | None = None
    tokens_sortie: int | None = None


def appeler_ia(system_prompt: str, user_prompt: str, *, max_tokens: int | None = None) -> ReponseIA:
    """Envoie (system_prompt, user_prompt) au fournisseur IA configuré et
    renvoie sa réponse. Lève une sous-classe de IAErreur (message FR) en cas
    de souci — clé absente, quota, timeout, réponse vide, erreur réseau."""

    fournisseur = (settings.IA_FOURNISSEUR or '').strip().lower()
    max_tokens = max_tokens or settings.IA_MAX_TOKENS_REPONSE

    if fournisseur == 'anthropic':
        return _appeler_anthropic(system_prompt, user_prompt, max_tokens=max_tokens)

    raise IAConfigurationInvalide(
        f"Fournisseur IA inconnu : « {fournisseur or '(vide)'} ». "
        "Vérifie le réglage IA_FOURNISSEUR dans le .env du serveur."
    )


def _appeler_anthropic(system_prompt: str, user_prompt: str, *, max_tokens: int) -> ReponseIA:
    cle = settings.ANTHROPIC_API_KEY
    if not cle:
        raise IAConfigurationInvalide(
            "Clé API Anthropic absente (ANTHROPIC_API_KEY dans le .env du serveur)."
        )

    try:
        import anthropic
    except ImportError as exc:
        raise IAConfigurationInvalide(
            "Le paquet Python 'anthropic' n'est pas installé sur le serveur."
        ) from exc

    modele = settings.IA_MODELE
    client = anthropic.Anthropic(api_key=cle, timeout=float(settings.IA_TIMEOUT_SECONDES))

    try:
        reponse = client.messages.create(
            model=modele,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise IAConfigurationInvalide(
            "Clé API Anthropic refusée par le fournisseur (vérifie ANTHROPIC_API_KEY)."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise IAQuotaDepasse(
            "Quota Anthropic atteint (429) : réessaie plus tard, ou vérifie le plan de facturation."
        ) from exc
    except (anthropic.APITimeoutError, TimeoutError) as exc:
        raise IATimeout(
            f"Le fournisseur IA n'a pas répondu dans le délai imparti ({settings.IA_TIMEOUT_SECONDES}s)."
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise IAErreurFournisseur(
            "Impossible de joindre le fournisseur IA (problème réseau côté serveur)."
        ) from exc
    except anthropic.APIStatusError as exc:
        raise IAErreurFournisseur(
            f"Le fournisseur IA a répondu une erreur ({exc.status_code})."
        ) from exc
    except anthropic.AnthropicError as exc:
        raise IAErreurFournisseur("Erreur inattendue côté fournisseur IA.") from exc

    texte = "".join(
        bloc.text for bloc in reponse.content if getattr(bloc, "type", None) == "text"
    ).strip()
    if not texte:
        raise IAReponseVide("Le fournisseur IA a renvoyé une réponse vide.")

    usage = getattr(reponse, "usage", None)
    tokens_entree = getattr(usage, "input_tokens", None)
    tokens_sortie = getattr(usage, "output_tokens", None)

    # Suivi de consommation (jamais la clé, jamais le contenu) — utile pour
    # surveiller le coût d'une fonctionnalité déclenchée manuellement par un
    # admin. `stop_reason == "max_tokens"` signale une réponse tronquée :
    # utile à repérer si IA_MAX_TOKENS_REPONSE s'avère trop juste.
    logger.info(
        "appel IA anthropic modele=%s tokens_entree=%s tokens_sortie=%s stop_reason=%s",
        modele, tokens_entree, tokens_sortie, getattr(reponse, "stop_reason", None),
    )

    return ReponseIA(
        texte=texte,
        fournisseur='anthropic',
        modele=modele,
        tokens_entree=tokens_entree,
        tokens_sortie=tokens_sortie,
    )
