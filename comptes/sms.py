"""
Client SMS LAM (L'Africa Mobile / LAMPUSH).

HISTORIQUE IMPORTANT (pour ne pas refaire la même erreur) : la première
version de ce module reproduisait fidèlement utils/sendSMS.js d'aimath
(Basic Auth pour accountid/password, jamais dans le corps JSON) — mais ça
échouait en prod avec "Parameter accountid is required !" renvoyé par LAM.
Vérifié depuis contre la DOC OFFICIELLE LAM actuelle
(developers.lafricamobile.com/docs/sms/endpoint/send-via-JSON) : LAM
authentifie via des PARAMÈTRES DU CORPS JSON (`accountid`, `password`),
PAS via HTTP Basic Auth. L'intégration aimath dont on s'inspirait n'avait
apparemment jamais été vérifiée avec un vrai compte (son échec, comme le
nôtre, est avalé en silence par un try/catch générique) — ne plus lui faire
confiance aveuglément sur ce point précis.

Champs du corps JSON envoyés (les DEUX conventions de nommage, pour
maximiser la compatibilité en un seul essai — LAM ignore sans broncher un
champ qu'il ne reconnaît pas) :
- `accountid` / `password` : la doc officielle (obligatoires, voir ci-dessus).
- `sender` / `text` : noms documentés officiellement.
- `from` / `content` : noms utilisés par aimath — gardés en plus, au cas où
  le compte/la version d'API validerait ceux-là plutôt que sender/text.
- `to`, `dlr`, `dlr-level`, `dlr-method`, `dlr-url` : inchangés, l'erreur
  observée ne les concernait pas.
- Format du numéro pour `to` : "227XXXXXXXX" — SANS "+" ni "00" (voir
  normaliser_telephone_sms ci-dessous). À ne JAMAIS confondre avec
  comptes.nita.normaliser_telephone_nita, qui produit un format différent
  ("00227XXXXXXXX") pour une API différente.

RÈGLE ABSOLUE (comme comptes/nita.py) : envoyer_sms() ne lève JAMAIS
d'exception — un SMS est un bonus, jamais une condition de succès d'une
vente ou d'une activation d'abonnement. Toute erreur est loggée, la
fonction retourne simplement False.
"""

import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDES = 15

# Accusé de réception (DLR) — 3 champs repris tels quels de l'appel aimath
# confirmé fonctionnel ; Fahimta n'exploite pas encore ces accusés
# (pas d'endpoint dédié), ils sont seulement transmis à LAM comme dans
# l'intégration d'origine.
_DLR_URL = "https://sms.ne/dlr"


def normaliser_telephone_sms(telephone: str) -> str:
    """"+22790000000" / "22790000000" / "090000000" / "90000000" →
    "22790000000" — format `to` attendu par LAM (SANS "+"), voir la
    docstring de module. Ne lève jamais : une entrée non reconnue est
    renvoyée "aplatie" (chiffres seuls), LAM la rejettera proprement plutôt
    qu'une exception ici sur un cas limite."""
    chiffres = re.sub(r"\D", "", telephone or "")

    if re.fullmatch(r"0\d{8}", chiffres):
        chiffres = chiffres[1:]

    if chiffres.startswith("00227") and len(chiffres) == 13:
        return chiffres[2:]
    if chiffres.startswith("227") and len(chiffres) == 11:
        return chiffres
    if re.fullmatch(r"\d{8}", chiffres):
        return "227" + chiffres

    return chiffres


def envoyer_sms(telephone: str, texte: str) -> bool:
    """POST vers LAM_SMS_URL — NE LÈVE JAMAIS (voir docstring de module).
    Retourne True si le SMS a été accepté par LAM (ou simulé en mode mock),
    False sinon — jamais d'exception propagée à l'appelant."""
    to = normaliser_telephone_sms(telephone)

    if settings.SMS_MOCK:
        logger.info("[SMS_MOCK] to=%s texte=%r", to, texte)
        return True

    if not all(
        [settings.LAM_SMS_URL, settings.LAM_ACCOUNTID, settings.LAM_PASSWORD, settings.LAM_DEFAULT_SENDER]
    ):
        logger.error(
            "SMS non envoyé à %s : configuration LAM incomplète "
            "(LAM_SMS_URL / LAM_ACCOUNTID / LAM_PASSWORD / LAM_DEFAULT_SENDER).",
            to,
        )
        return False

    payload = {
        # Authentification LAM (doc officielle : dans le corps, PAS Basic Auth).
        "accountid": settings.LAM_ACCOUNTID,
        "password": settings.LAM_PASSWORD,
        # Deux conventions de nommage pour l'expéditeur/le texte (voir
        # docstring de module) — LAM ignore un champ qu'il ne reconnaît pas.
        "sender": settings.LAM_DEFAULT_SENDER,
        "text": texte,
        "from": settings.LAM_DEFAULT_SENDER,
        "content": texte,
        "to": to,
        "dlr": "yes",
        "dlr-level": 3,
        "dlr-method": "GET",
        "dlr-url": _DLR_URL,
    }

    # LOG TEMPORAIRE (WARNING) — à retirer/repasser en INFO une fois l'envoi
    # confirmé fonctionnel : les NOMS des champs envoyés (jamais leurs
    # valeurs, ni le mot de passe ni la clé/l'accountid) + l'URL, pour
    # confirmer ce qui part réellement vers LAM.
    logger.warning(
        "SMS → POST %s avec les champs (noms uniquement, jamais les valeurs) : %s "
        "[Basic Auth également envoyé, conservé par prudence]",
        settings.LAM_SMS_URL, sorted(payload.keys()),
    )

    try:
        reponse = requests.post(
            settings.LAM_SMS_URL,
            json=payload,
            # Gardé en plus du body (voir docstring) : ne peut pas nuire si
            # LAM l'ignore, pourrait aider si le compte le valide malgré tout.
            auth=(settings.LAM_ACCOUNTID, settings.LAM_PASSWORD),
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT_SECONDES,
        )
    except requests.RequestException as exc:
        logger.error("SMS non envoyé à %s (LAM injoignable) : %s", to, exc)
        return False

    if not reponse.ok:
        logger.error("SMS refusé par LAM (HTTP %s) pour %s : %s", reponse.status_code, to, reponse.text[:300])
        return False

    logger.info("SMS envoyé à %s.", to)
    return True
