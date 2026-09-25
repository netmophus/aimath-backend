"""
Client NITA (paiement mobile par référence) — auth, création d'achat,
vérification de statut. Regroupé ici (comme comptes/cartes.py pour les
cartes Fahimta) pour être réutilisé identiquement par comptes/nita_views.py
(initier/callback/vérifier), jamais dupliqué.

RÈGLES DE SÉCURITÉ appliquées ici (voir aussi nita_views.py) :
- AUCUNE clé en dur, aucun fallback "|| valeur" : les 4 réglages NITA_* sont
  lus depuis l'environnement (config/settings.py, python-decouple), avec un
  défaut vide (jamais une vraie valeur) — un appel réel sans configuration
  échoue proprement via NitaError, jamais silencieusement avec une clé
  secrète codée en dur (c'était LA faille du projet dont on s'inspire ici).
- Normalisation du téléphone CENTRALISÉE dans une seule fonction
  (normaliser_telephone_nita) — contrairement à l'intégration source qui en
  avait trois éparpillées avec des règles légèrement différentes.
- Mode simulé (NITA_MOCK=1, jamais à activer en production) : aucun appel
  réseau réel n'est fait. Voir la section "MODE SIMULÉ" plus bas pour le
  détail du mécanisme.

JOURNALISATION (ajoutée suite à un 502 muet en prod, aucune trace dans les
logs Heroku) : chaque appel réseau logge l'URL exacte appelée, le statut
HTTP et le corps de réponse NITA en cas d'échec (ERROR/WARNING) — INDISPENSABLE
pour diagnostiquer une intégration tierce dont le comportement réel diffère
parfois de sa documentation. JAMAIS le mot de passe ni la clé API en clair :
seul un booléen "renseigné/manquant" est loggé pour ces deux-là, jamais la
valeur (voir _diagnostiquer_config ci-dessous). Le nom d'utilisateur NITA
(NITA_USERNAME) n'est, lui, pas un secret à proprement parler (un
identifiant de compte, pas un mot de passe) mais n'est pas non plus loggé
par prudence, par défense en profondeur.
"""

import logging
import re
import uuid

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class NitaError(Exception):
    """Toute erreur d'appel à l'API NITA (config manquante, timeout, HTTP
    en erreur, réponse inattendue) — un seul type d'exception, à charge de
    l'appelant (comptes/nita_views.py) de choisir le message/status HTTP
    renvoyé à l'élève ou à NITA. Le DÉTAIL diagnostique est déjà dans les
    logs au moment où cette exception est levée (voir les logger.error()
    juste avant chaque `raise` dans ce module) — le message de l'exception
    elle-même reste court, c'est le log qui porte le détail complet."""


# ============================================================
#  Normalisation du téléphone — UNE seule fonction, tous les formats
#  d'entrée possibles (saisie élève / User.telephone) vers le format que
#  NITA attend en paramètre `phoneClient` : "00227XXXXXXXX".
# ============================================================

def normaliser_telephone_nita(telephone: str) -> str:
    """"+22790000000" / "22790000000" / "090000000" / "90000000" →
    "0022790000000". Ne lève jamais : une entrée qui ne correspond à aucun
    format connu est renvoyée "aplatie" (chiffres seuls, préfixée 00 si
    besoin) — l'appelant (l'achat NITA lui-même) échouera alors côté NITA
    avec un message clair, plutôt qu'une exception ici sur un cas limite."""
    chiffres = re.sub(r"\D", "", telephone or "")

    # Retire un 0 initial de type "090000000" (8 chiffres locaux précédés
    # d'un 0) avant d'appliquer l'indicatif — un 09XXXXXXX ne doit jamais
    # devenir 0022709XXXXXXX.
    if re.fullmatch(r"0\d{8}", chiffres):
        chiffres = chiffres[1:]

    if chiffres.startswith("00227") and len(chiffres) == 13:
        return chiffres
    if chiffres.startswith("227") and len(chiffres) == 11:
        return "00" + chiffres
    if re.fullmatch(r"\d{8}", chiffres):
        return "00227" + chiffres

    # Format non reconnu : "00" + tel quel, plutôt que planter — NITA
    # rejettera proprement un numéro mal formé.
    return "00" + chiffres if not chiffres.startswith("00") else chiffres


# ============================================================
#  Catalogue de plans — structure explicite (PAS de seuil magique du type
#  "montant >= 15000 => annuel"), facile à étendre (trimestriel, annuel…)
#  sans toucher à la logique des vues.
# ============================================================

PLANS_NITA: dict[str, dict] = {
    "mensuel": {"label": "Mensuel", "montant": 2000, "duree_jours": 30},
}


def generer_request_id() -> str:
    """"FAH-<hex unique>" — un UUID4 rend une collision non-nulle mais
    astronomiquement improbable (contrairement aux codes de carte Fahimta,
    tirés d'un petit alphabet, aucune boucle de re-génération n'est
    nécessaire ici)."""
    return f"FAH-{uuid.uuid4().hex.upper()}"


# ============================================================
#  Client HTTP NITA — chaque fonction bascule sur une réponse SIMULÉE si
#  settings.NITA_MOCK est vrai, sans jamais toucher au réseau dans ce cas.
# ============================================================

def _config_requise() -> tuple[str, str, str, str]:
    """Lève NitaError si un seul des 4 réglages NITA_* manque — jamais de
    valeur par défaut secrète, l'appel échoue proprement à la place. Logge
    PRÉCISÉMENT quelle(s) variable(s) manque(nt) (juste le NOM, jamais la
    valeur) — sans ça, un 502 "Configuration NITA manquante" en prod ne dit
    pas LAQUELLE des 4 variables Heroku n'a en fait jamais été configurée."""
    base_url = settings.NITA_BASE_URL
    api_key = settings.NITA_API_KEY
    username = settings.NITA_USERNAME
    password = settings.NITA_PASSWORD

    manquantes = [
        nom
        for nom, valeur in [
            ("NITA_BASE_URL", base_url),
            ("NITA_API_KEY", api_key),
            ("NITA_USERNAME", username),
            ("NITA_PASSWORD", password),
        ]
        if not valeur
    ]
    if manquantes:
        logger.error(
            "Configuration NITA incomplète — variable(s) manquante(s) : %s. "
            "Vérifie les config vars Heroku (heroku config) pour cette app.",
            ", ".join(manquantes),
        )
        raise NitaError(
            "Configuration NITA manquante (NITA_BASE_URL / NITA_API_KEY / "
            "NITA_USERNAME / NITA_PASSWORD) — voir .env.example."
        )
    return base_url.rstrip("/"), api_key, username, password


def _lire_json_ou_texte(reponse: requests.Response, contexte: str) -> dict:
    """`.json()` protégée : si NITA renvoie un corps non-JSON (page d'erreur
    HTML, texte brut d'un proxy/passerelle en amont…), `.json()` lève une
    exception qui n'était PAS rattrapée avant cet ajout — elle remontait
    alors telle quelle, non gérée, jusqu'à devenir un 502 opaque sans
    aucune trace exploitable. Ici : le corps brut (tronqué) est loggé et une
    NitaError normale est levée à la place, comme toute autre erreur NITA."""
    if not reponse.content:
        return {}
    try:
        return reponse.json()
    except ValueError:
        logger.error(
            "%s : réponse NITA non-JSON (HTTP %s) — corps brut (tronqué) : %r",
            contexte, reponse.status_code, reponse.text[:500],
        )
        raise NitaError(f"{contexte} : réponse NITA illisible (pas du JSON).")


def nita_auth() -> str:
    """POST {NITA_BASE_URL}/api/authenticate → JWT. Le nom du champ porteur
    du jeton varie selon la doc/les retours observés (token / access_token
    / jwt / data.token) — on teste les variantes plutôt que d'en figer une."""
    if settings.NITA_MOCK:
        return "MOCK-JWT-TOKEN"

    base_url, api_key, username, password = _config_requise()
    url = f"{base_url}/api/authenticate"
    logger.info("NITA auth → POST %s (X-NT-API-KEY: %s, username: %s)",
                url, "renseignée" if api_key else "MANQUANTE", "renseigné" if username else "MANQUANT")

    try:
        reponse = requests.post(
            url,
            json={"username": username, "password": password},
            headers={"X-NT-API-KEY": api_key, "Accept": "application/json"},
            timeout=settings.NITA_TIMEOUT_SECONDES,
        )
    except requests.RequestException as exc:
        logger.exception("NITA auth → %s injoignable", url)
        raise NitaError(f"NITA injoignable (authentification) : {exc}") from exc

    if not reponse.ok:
        logger.error(
            "NITA auth ← HTTP %s pour %s — corps (tronqué) : %r",
            reponse.status_code, url, reponse.text[:500],
        )
        raise NitaError(f"Authentification NITA refusée (HTTP {reponse.status_code}).")

    donnees = _lire_json_ou_texte(reponse, "NITA auth")
    jeton = (
        donnees.get("token")
        or donnees.get("access_token")
        or donnees.get("jwt")
        or (donnees.get("data") or {}).get("token")
    )
    if not jeton:
        logger.error(
            "NITA auth ← HTTP %s OK mais aucun jeton trouvé dans la réponse — corps : %r",
            reponse.status_code, donnees,
        )
        raise NitaError("Authentification NITA : jeton introuvable dans la réponse.")

    logger.info("NITA auth ← OK (HTTP %s)", reponse.status_code)
    return jeton


def nita_creer_achat(
    *, request_id: str, montant: int, motif: str, telephone_nita: str, url_callback: str
) -> str:
    """POST .../achatEnLigne/saveAchatEnLigne → référence d'achat NITA
    (à communiquer à l'élève). `telephone_nita` DOIT déjà être au format
    NITA (voir normaliser_telephone_nita) — cette fonction ne renormalise
    rien, pour garder une seule source de vérité sur le format."""
    if settings.NITA_MOCK:
        return f"MOCK-REF-{request_id}"

    base_url, api_key, _, _ = _config_requise()
    jeton = nita_auth()

    payload = {
        "descriptionAchat": [motif],
        "montantTransaction": montant,
        "motifTransaction": motif,
        "requestId": request_id,
        "adresseIp": "102.45.67.89",
        "phoneClient": telephone_nita,
        "urlCallback": url_callback,
    }
    url = f"{base_url}/api/nitaServices/achatEnLigne/saveAchatEnLigne"
    # Rien de secret dans le payload lui-même (la clé/le jeton sont dans les
    # en-têtes, jamais loggés ici) — sûr à logger tel quel pour diagnostic.
    logger.info("NITA créer achat → POST %s payload=%r", url, payload)

    try:
        reponse = requests.post(
            url,
            json=payload,
            headers={
                "X-NT-API-KEY": api_key,
                "Authorization": f"Bearer {jeton}",
                "Accept": "application/json",
            },
            timeout=settings.NITA_TIMEOUT_SECONDES,
        )
    except requests.RequestException as exc:
        logger.exception("NITA créer achat → %s injoignable", url)
        raise NitaError(f"NITA injoignable (création d'achat) : {exc}") from exc

    donnees = _lire_json_ou_texte(reponse, "NITA créer achat")

    if not reponse.ok or int(donnees.get("code", 0) or 0) != 200:
        logger.error(
            "NITA créer achat ← HTTP %s pour %s — corps : %r",
            reponse.status_code, url, donnees,
        )
        message = donnees.get("message") or f"HTTP {reponse.status_code}"
        raise NitaError(f"Création d'achat NITA refusée : {message}")

    reference = (
        donnees.get("referenceAchat")
        or donnees.get("codeAchat")
        or donnees.get("reference")
        or (donnees.get("data") or {}).get("referenceAchat")
        or (donnees.get("data") or {}).get("codeAchat")
    )
    if not reference:
        logger.error(
            "NITA créer achat ← HTTP %s OK (code=200) mais aucune référence trouvée — corps : %r",
            reponse.status_code, donnees,
        )
        raise NitaError("Création d'achat NITA : référence introuvable dans la réponse.")

    logger.info("NITA créer achat ← OK, référence=%s", reference)
    return reference


_STATUTS_PAYES = {"1", "ok", "success", "succès", "paid"}


def nita_check_status(*, request_id: str, reference: str | None, telephone_nita: str) -> bool:
    """POST .../achatEnLigne/checkAchatStatus → True si NITA confirme le
    paiement. C'EST la vérification qui fait foi — voir nita_views.py, qui
    l'appelle TOUJOURS avant de créditer quoi que ce soit, qu'il s'agisse
    du webhook (qui ne fait jamais confiance au statut qu'il reçoit) ou du
    filet de secours "Vérifier maintenant"."""
    if settings.NITA_MOCK:
        # Voir nita_views.NitaMockConfirmerView : seul moyen de faire
        # basculer ce résultat à True en test, sans aucun appel réseau réel.
        return bool(cache.get(f"nita_mock_paye_{request_id}", False))

    base_url, api_key, _, _ = _config_requise()
    jeton = nita_auth()

    payload = {
        "requestId": request_id,
        "referenceAchat": reference,
        "codeAchat": reference,
        "phoneClient": telephone_nita,
        "adresseIp": "102.45.67.89",
    }
    url = f"{base_url}/api/nitaServices/achatEnLigne/checkAchatStatus"
    logger.info("NITA check status → POST %s payload=%r", url, payload)

    try:
        reponse = requests.post(
            url,
            json=payload,
            headers={
                "X-NT-API-KEY": api_key,
                "Authorization": f"Bearer {jeton}",
                "Accept": "application/json",
            },
            timeout=settings.NITA_TIMEOUT_SECONDES,
        )
    except requests.RequestException as exc:
        logger.exception("NITA check status → %s injoignable", url)
        raise NitaError(f"NITA injoignable (vérification de statut) : {exc}") from exc

    if not reponse.ok:
        logger.error(
            "NITA check status ← HTTP %s pour %s — corps (tronqué) : %r",
            reponse.status_code, url, reponse.text[:500],
        )
        raise NitaError(f"Vérification de statut NITA refusée (HTTP {reponse.status_code}).")

    donnees = _lire_json_ou_texte(reponse, "NITA check status")
    brut = str(
        donnees.get("status")
        or donnees.get("code")
        or (donnees.get("data") or {}).get("status")
        or donnees.get("statusTransaction")
        or donnees.get("etat")
        or ""
    ).strip().lower()

    paye = brut in _STATUTS_PAYES
    logger.info("NITA check status ← HTTP %s, statut brut=%r → payé=%s", reponse.status_code, brut, paye)
    return paye
