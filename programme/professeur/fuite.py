"""
Détection de FUITE : un message destiné à l'élève ne doit pas contenir la
réponse attendue de l'étape en cours (sauf quand l'élève demande, et a le
droit de voir, la solution de cette étape).

Contrôle volontairement simple et prudent : mieux vaut un faux positif (le
message est remplacé par un texte neutre) qu'une réponse divulguée.
"""

from __future__ import annotations

import re

_REMPLACEMENTS = (
    ("²", "^2"), ("³", "^3"), ("−", "-"), ("–", "-"), ("×", "*"), ("·", "*"), ("\\cdot", "*"), ("\\times", "*"),
    ("\\left", ""), ("\\right", ""), ("\\dfrac", "\\frac"), ("\\,", ""), ("\\;", ""), ("\\ ", ""),
)


def normaliser(texte: str) -> str:
    t = (texte or "").lower()
    for ancien, nouveau in _REMPLACEMENTS:
        t = t.replace(ancien, nouveau)
    t = re.sub(r"[\s$\\{}()]", "", t)
    return t.replace("*", "")


def _valeur_isolee(message_norm: str, valeur_norm: str) -> bool:
    return re.search(rf"(?<![\w^.]){re.escape(valeur_norm)}(?![\w.^])", message_norm) is not None


def _sans_echo(message_norm: str, ignorer) -> str:
    """Retire du message ce que l'élève a lui-même écrit : le professeur peut citer sa réponse
    (« ton 3x²+3 »), ce n'est pas une fuite de la réponse attendue."""
    for texte in ignorer or ():
        brut = normaliser(texte)
        morceaux = {brut, brut.split("=")[-1]}
        for morceau in sorted(morceaux, key=len, reverse=True):
            if len(morceau) >= 2:
                message_norm = message_norm.replace(morceau, "")
    return message_norm


def contient_la_reponse(message: str, attendu: dict | None, ignorer=()) -> bool:
    """Vrai si `message` semble divulguer la réponse attendue (None → rien à protéger).
    `ignorer` : textes de l'élève dont la reprise dans le message n'est pas une fuite."""
    if not attendu:
        return False
    m = _sans_echo(normaliser(message), ignorer)
    if attendu["type"] == "ensemble":
        valeurs = [normaliser(v) for v in attendu["valeurs"]]
        if not valeurs:
            return bool(re.search(r"aucunesolution|pasdesolution|ensemblevide", m))
        if any(re.search(rf"[a-z]={re.escape(v)}(?![\w.^])", m) for v in valeurs):
            return True
        return len(valeurs) >= 2 and all(_valeur_isolee(m, v) for v in valeurs)
    valeur = normaliser(attendu["valeur"])
    if not valeur:
        return False
    if len(valeur) >= 3:
        return valeur in m
    return re.search(rf"=\s*{re.escape(valeur)}(?![\w.^])", m) is not None
