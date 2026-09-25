"""
Client SMS LAM (L'Africa Mobile / LAMPUSH). Inspiré de l'intégration aimath
(utils/sendSMS.js, Node) DONT LE FORMAT A ÉTÉ VÉRIFIÉ DIRECTEMENT dans le
code source avant d'écrire ce module — pas seulement supposé depuis la
consigne. Deux écarts par rapport à ce qui était attendu au départ,
confirmés en lisant sendSMS.js :

1. Authentification : LAM utilise du HTTP BASIC AUTH (username/password),
   PAS des champs `accountid`/`password` dans le corps JSON. On garde les
   noms de variables d'env demandés (LAM_ACCOUNTID/LAM_PASSWORD) mais on les
   passe en Basic Auth — c'est ce qui fonctionne réellement côté aimath.
2. Champs du corps JSON : `to`, `from` (PAS `sender`), `content` (PAS
   `text`), plus 3 champs d'accusé de réception (`dlr`, `dlr-level`,
   `dlr-method`, `dlr-url`) repris tels quels — jamais observés comme
   optionnels dans l'intégration source, donc conservés par prudence.
3. Format du numéro pour `to` : "227XXXXXXXX" — SANS "+" ni "00" (voir
   normaliser_telephone_sms ci-dessous), pas "+227XXXXXXXX" comme supposé
   initialement. Confirmé via comptes.paymentController.phoneForSMS côté
   aimath. À ne JAMAIS confondre avec comptes.nita.normaliser_telephone_nita,
   qui produit un format différent ("00227XXXXXXXX") pour une API différente.

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
        "to": to,
        "from": settings.LAM_DEFAULT_SENDER,
        "content": texte,
        "dlr": "yes",
        "dlr-level": 3,
        "dlr-method": "GET",
        "dlr-url": _DLR_URL,
    }

    try:
        reponse = requests.post(
            settings.LAM_SMS_URL,
            json=payload,
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
