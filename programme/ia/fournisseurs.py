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
    IAErreur,
    IAConfigurationInvalide,
    IAErreurFournisseur,
    IAQuotaDepasse,
    IAReponseVide,
    IATimeout,
)


@dataclass(frozen=True)
class ReponseIA:
    """Résultat d'un appel IA : le texte généré + de quoi estimer un coût
    (voir programme.ia.cout), sans jamais transporter la clé API.

    `tronque` (dérivé de `stop_reason == "max_tokens"`) signale que `texte`
    s'arrête au milieu de la génération, coupé par IA_MAX_TOKENS_REPONSE —
    à propager jusqu'à l'appelant, JAMAIS à traiter comme un contenu complet
    (voir programme.ia.service et programme.ia_views)."""

    texte: str
    fournisseur: str
    modele: str
    tokens_entree: int | None = None
    tokens_sortie: int | None = None
    stop_reason: str | None = None
    tronque: bool = False


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
    client = anthropic.Anthropic(api_key=cle, timeout=float(settings.IA_TIMEOUT_SECONDES), max_retries=0)

    # Budget commun : la génération de contenu (admin) compte dans le même plafond mensuel.
    from budget_ia import service as budget
    op = budget.ouvrir(
        fonctionnalite="contenu_admin", modele=modele, tokens_sortie_max=max_tokens,
        tokens_entree=budget.estimer_entree(message=user_prompt, systeme=system_prompt),
    )
    try:
        reponse = budget.appeler_sdk(op, lambda: client.messages.create(
            model=modele,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ))
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
    stop_reason = getattr(reponse, "stop_reason", None)
    if not texte:
        if stop_reason == "max_tokens":
            raise IAReponseVide(
                "La génération a atteint la limite de tokens (IA_MAX_TOKENS_REPONSE) "
                "avant de produire le moindre texte — probablement absorbée par le "
                "raisonnement interne du modèle. Augmente IA_MAX_TOKENS_REPONSE."
            )
        raise IAReponseVide("Le fournisseur IA a renvoyé une réponse vide.")

    usage = getattr(reponse, "usage", None)
    tokens_entree = getattr(usage, "input_tokens", None)
    tokens_sortie = getattr(usage, "output_tokens", None)
    tronque = stop_reason == "max_tokens"

    # Suivi de consommation (jamais la clé, jamais le contenu) — utile pour
    # surveiller le coût d'une fonctionnalité déclenchée manuellement par un
    # admin. `stop_reason == "max_tokens"` signale une réponse tronquée : on
    # ne se contente plus de le journaliser, voir `tronque` sur ReponseIA.
    logger.info(
        "appel IA anthropic modele=%s tokens_entree=%s tokens_sortie=%s stop_reason=%s",
        modele, tokens_entree, tokens_sortie, stop_reason,
    )

    return ReponseIA(
        texte=texte,
        fournisseur='anthropic',
        modele=modele,
        tokens_entree=tokens_entree,
        tokens_sortie=tokens_sortie,
        stop_reason=stop_reason,
        tronque=tronque,
    )


# --------------------------------------------------------------------------
#  Streaming (génération longue, ex. « sujet type examen »)
# --------------------------------------------------------------------------
#
#  Pourquoi : le routeur Heroku coupe (H12) toute requête dont le PREMIER octet
#  n'est pas parti avant 30 s, puis impose 55 s sans octet. Une génération
#  longue renvoyée d'un bloc dépasse 30 s. En streaming, des octets partent
#  dès la connexion puis à chaque fragment de texte : plus de H12.
#  Le décompte du budget IA reste identique (même `ouvrir`, même `terminer`
#  avec l'usage réel du message final, même `echouer` si le flux casse).

def _erreur_ia_depuis_sdk(exc: BaseException) -> IAErreur | None:
    """Même traduction que `_appeler_anthropic`, pour le flux. None = pas une
    erreur du SDK (on laisse alors l'exception d'origine repartir)."""
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return IAConfigurationInvalide("Clé API Anthropic refusée par le fournisseur (vérifie ANTHROPIC_API_KEY).")
    if isinstance(exc, anthropic.RateLimitError):
        return IAQuotaDepasse("Quota Anthropic atteint (429) : réessaie plus tard, ou vérifie le plan de facturation.")
    if isinstance(exc, (anthropic.APITimeoutError, TimeoutError)):
        return IATimeout(f"Le fournisseur IA n'a pas répondu dans le délai imparti ({settings.IA_TIMEOUT_SECONDES}s).")
    if isinstance(exc, anthropic.APIConnectionError):
        return IAErreurFournisseur("Impossible de joindre le fournisseur IA (problème réseau côté serveur).")
    if isinstance(exc, anthropic.APIStatusError):
        return IAErreurFournisseur(f"Le fournisseur IA a répondu une erreur ({exc.status_code}).")
    if isinstance(exc, anthropic.AnthropicError):
        return IAErreurFournisseur("Erreur inattendue côté fournisseur IA.")
    return None


class FluxIA:
    """Appel IA en streaming PRÉPARÉ (clé vérifiée, budget réservé) mais pas
    encore démarré. `deltas()` est un générateur : il produit chaque fragment
    de texte (str non vide) et, de temps en temps, "" pour les événements sans
    texte (battement : permet à l'appelant d'émettre un octet de vie). À la fin
    normale, `reponse` contient la ReponseIA complète (même forme qu'`appeler_ia`)."""

    def __init__(self, client, op, modele: str, system_prompt: str, user_prompt: str, max_tokens: int):
        self._client = client
        self._op = op
        self._modele = modele
        self._system = system_prompt
        self._user = user_prompt
        self._max_tokens = max_tokens
        self.reponse: ReponseIA | None = None

    def deltas(self):
        from budget_ia import service as budget

        solde = False
        try:
            with self._client.messages.stream(
                model=self._modele,
                max_tokens=self._max_tokens,
                system=self._system,
                messages=[{"role": "user", "content": self._user}],
            ) as flux:
                morceaux: list[str] = []
                for evenement in flux:
                    delta = getattr(evenement, "delta", None)
                    if getattr(evenement, "type", None) == "content_block_delta" and getattr(delta, "type", None) == "text_delta":
                        morceaux.append(delta.text)
                        yield delta.text
                    else:
                        yield ""
                final = flux.get_final_message()
            solde = True
            budget.terminer(self._op, budget.usage_de_reponse(final))
        except BaseException as exc:  # noqa: BLE001 : y compris GeneratorExit (client parti) : résultat inconnu
            if not solde:
                budget.echouer(self._op, type(exc).__name__, resultat_inconnu=budget._resultat_inconnu(exc))
            if isinstance(exc, Exception):
                traduite = _erreur_ia_depuis_sdk(exc)
                if traduite is not None:
                    raise traduite from exc
            raise

        texte = "".join(
            bloc.text for bloc in final.content if getattr(bloc, "type", None) == "text"
        ).strip()
        stop_reason = getattr(final, "stop_reason", None)
        if not texte:
            if stop_reason == "max_tokens":
                raise IAReponseVide(
                    "La génération a atteint la limite de tokens (IA_MAX_TOKENS_REPONSE) "
                    "avant de produire le moindre texte. Augmente IA_MAX_TOKENS_REPONSE."
                )
            raise IAReponseVide("Le fournisseur IA a renvoyé une réponse vide.")

        usage = getattr(final, "usage", None)
        tokens_entree = getattr(usage, "input_tokens", None)
        tokens_sortie = getattr(usage, "output_tokens", None)
        logger.info(
            "appel IA anthropic (flux) modele=%s tokens_entree=%s tokens_sortie=%s stop_reason=%s",
            self._modele, tokens_entree, tokens_sortie, stop_reason,
        )
        self.reponse = ReponseIA(
            texte=texte,
            fournisseur='anthropic',
            modele=self._modele,
            tokens_entree=tokens_entree,
            tokens_sortie=tokens_sortie,
            stop_reason=stop_reason,
            tronque=stop_reason == "max_tokens",
        )


def preparer_flux_ia(system_prompt: str, user_prompt: str, *, max_tokens: int | None = None) -> FluxIA:
    """Équivalent streaming d'`appeler_ia`. Fait TOUS les contrôles qui peuvent
    refuser (fournisseur, clé, budget) tout de suite, avant que l'appelant
    n'ouvre la réponse HTTP : un refus reste donc une vraie erreur HTTP JSON."""

    fournisseur = (settings.IA_FOURNISSEUR or '').strip().lower()
    max_tokens = max_tokens or settings.IA_MAX_TOKENS_REPONSE

    if fournisseur != 'anthropic':
        raise IAConfigurationInvalide(
            f"Fournisseur IA inconnu : « {fournisseur or '(vide)'} ». "
            "Vérifie le réglage IA_FOURNISSEUR dans le .env du serveur."
        )
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
    client = anthropic.Anthropic(api_key=cle, timeout=float(settings.IA_TIMEOUT_SECONDES), max_retries=0)

    from budget_ia import service as budget
    op = budget.ouvrir(
        fonctionnalite="contenu_admin", modele=modele, tokens_sortie_max=max_tokens,
        tokens_entree=budget.estimer_entree(message=user_prompt, systeme=system_prompt),
    )
    return FluxIA(client, op, modele, system_prompt, user_prompt, max_tokens)
