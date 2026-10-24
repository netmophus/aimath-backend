"""
Second avis INDÉPENDANT : Wolfram Alpha (API « Full Results », App ID du .env).

Seuls les types d'affirmations dont la réponse Wolfram est lisible sans
ambiguïté sont interrogés (equation, derivee, extrema). Pour tous les autres,
le verdict est « indisponible » : on ne prétend pas avoir vérifié.

L'App ID n'apparaît jamais dans les journaux ni dans les messages d'erreur
(il est dans l'URL de la requête : on ne journalise jamais l'URL). Les
réponses de Wolfram sont du texte non fiable : elles passent par
expressions.analyser comme tout le reste, jamais par eval.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

import sympy as sp
from django.conf import settings

from .expressions import ExpressionInvalide, analyser, symbole
from .verification import CONTRADICTION, INDISPONIBLE, OK, VerdictMethode, _annonces, _comparer_ensembles, _egaux, _sans_solution, _texte

logger = logging.getLogger(__name__)

URL = "https://api.wolframalpha.com/v2/query"
TYPES_WOLFRAM = ("equation", "derivee", "extrema")


class WolframIndisponible(Exception):
    """Wolfram n'a pas pu répondre (réseau, délai, clé refusée, réponse invalide)."""


def wolfram_configure() -> bool:
    return bool(getattr(settings, "WOLFRAM_APP_ID", ""))


def _requete_http(requete: str) -> dict:
    """UN appel à l'API. Fonction de remplacement des tests (aucun appel réel en test)."""
    adresse = URL + "?" + urllib.parse.urlencode(
        {"appid": settings.WOLFRAM_APP_ID, "input": requete, "output": "json", "format": "plaintext", "reinterpret": "true"}
    )
    try:
        with urllib.request.urlopen(adresse, timeout=float(settings.WOLFRAM_TIMEOUT_SECONDES)) as reponse:  # noqa: S310 - URL fixe https
            donnees = json.load(reponse)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise WolframIndisponible(f"Wolfram Alpha injoignable ({type(exc).__name__}).") from None
    resultat = donnees.get("queryresult") if isinstance(donnees, dict) else None
    if not isinstance(resultat, dict) or resultat.get("error") not in (False, None):
        raise WolframIndisponible("Réponse Wolfram Alpha invalide ou refusée.")
    return resultat


def _pods(resultat: dict, *identifiants: str) -> list[str]:
    """Textes (lignes) des pods dont l'id commence par l'un des identifiants, dans l'ordre."""
    lignes: list[str] = []
    for pod in resultat.get("pods") or []:
        if any(str(pod.get("id", "")).startswith(i) for i in identifiants):
            for sous in pod.get("subpods") or []:
                texte = sous.get("plaintext")
                if isinstance(texte, str) and texte.strip():
                    lignes.append(texte.strip())
            if lignes:
                return lignes
    return lignes


def _valeurs_de_ligne(ligne: str, variable: str) -> list[sp.Expr]:
    """« x = 2 » → [2] ; « x = ±1 » → [1, -1] ; « x = (3 ± sqrt(5))/2 » → deux valeurs."""
    morceau = ligne.split("=", 1)[1].strip() if "=" in ligne else ligne.strip()
    morceau = re.sub(r"\s*(?:\(.*?\)|and|or)\s*$", "", morceau).strip()
    candidats = [morceau]
    if "±" in morceau:
        candidats = [morceau.replace("±", "+"), morceau.replace("±", "-")]
        if morceau.strip().startswith("±"):
            candidats = [morceau.replace("±", "", 1), morceau.replace("±", "-", 1)]
    return [analyser(c, (variable,)) for c in candidats]


def _solutions(resultat: dict, variable: str) -> list[sp.Expr] | None:
    lignes = _pods(resultat, "ResultOverTheReals", "Result", "Solution", "RealSolution")
    if not lignes:
        return None
    if any("no solution" in l.lower() or "no real" in l.lower() for l in lignes):
        return []
    valeurs: list[sp.Expr] = []
    for ligne in lignes:
        valeurs.extend(_valeurs_de_ligne(ligne, variable))
    return valeurs


def _extraire_derivee(resultat: dict, variable: str) -> sp.Expr | None:
    for ligne in _pods(resultat, "Input", "Derivative"):
        if "=" in ligne:
            return analyser(ligne.rsplit("=", 1)[1], (variable,))
    return None


def _interroger(requete: str) -> dict:
    resultat = _requete_http(requete)
    if resultat.get("success") is not True:
        raise WolframIndisponible("Wolfram Alpha n'a pas compris la requête.")
    return resultat


def verifier_avec_wolfram(affirmation: dict) -> tuple[VerdictMethode, bool]:
    """(verdict, a_interroge_wolfram). N'interroge Wolfram que pour les types pris en charge."""
    type_ = affirmation.get("type")
    if type_ not in TYPES_WOLFRAM:
        return VerdictMethode(INDISPONIBLE, "Type de calcul non soumis à Wolfram Alpha."), False
    if not wolfram_configure():
        return VerdictMethode(INDISPONIBLE, "Wolfram Alpha n'est pas configuré sur le serveur."), False
    try:
        x = symbole(affirmation.get("variable") or "x")
        if type_ == "equation":
            gauche = analyser(affirmation.get("gauche"), (x.name,))
            droite = analyser(affirmation.get("droite") or "0", (x.name,))
            resultat = _interroger(f"solve {_texte(gauche)} = {_texte(droite)} for {x.name} over the reals")
            calculees = _solutions(resultat, x.name)
            if calculees is None:
                return VerdictMethode(INDISPONIBLE, "Réponse Wolfram Alpha non exploitable."), True
            brutes = _annonces(affirmation.get("solutions"))
            annoncees = [] if all(_sans_solution(s) for s in brutes) else [analyser(s, (x.name,)) for s in brutes]
            liste = ", ".join(_texte(v) for v in calculees) or "aucune"
            if _comparer_ensembles(annoncees, calculees):
                return VerdictMethode(OK, f"Wolfram Alpha trouve les mêmes solutions : {liste}.", [_texte(v) for v in calculees]), True
            annoncees_txt = ", ".join(_texte(v) for v in annoncees) or "aucune"
            return VerdictMethode(
                CONTRADICTION,
                f"Wolfram Alpha trouve comme solutions : {liste} ; la correction annonce : {annoncees_txt}.",
                [_texte(v) for v in calculees],
            ), True

        if type_ == "derivee":
            f = analyser(affirmation.get("fonction"), (x.name,))
            annoncee = analyser(affirmation.get("derivee"), (x.name,))
            calculee = _extraire_derivee(_interroger(f"derivative of {_texte(f)} with respect to {x.name}"), x.name)
            if calculee is None:
                return VerdictMethode(INDISPONIBLE, "Réponse Wolfram Alpha non exploitable."), True
            if _egaux(calculee, annoncee):
                return VerdictMethode(OK, f"Wolfram Alpha trouve la même dérivée : {_texte(calculee)}.", [_texte(calculee)]), True
            return VerdictMethode(
                CONTRADICTION,
                f"Wolfram Alpha trouve f'({x.name}) = {_texte(calculee)} ; la correction annonce {_texte(annoncee)}.",
                [_texte(calculee)],
            ), True

        # extrema : Wolfram confirme que les abscisses annoncées sont des points critiques (f' = 0).
        f = analyser(affirmation.get("fonction"), (x.name,))
        resultat = _interroger(f"solve d/d{x.name}({_texte(f)}) = 0 for {x.name} over the reals")
        critiques = _solutions(resultat, x.name)
        if critiques is None:
            return VerdictMethode(INDISPONIBLE, "Réponse Wolfram Alpha non exploitable."), True
        abscisses = [analyser(e.get("x"), (x.name,)) for e in affirmation.get("extrema") or [] if isinstance(e, dict)]
        liste = ", ".join(_texte(v) for v in critiques) or "aucun"
        for a in abscisses:
            if not any(_egaux(a, c) for c in critiques):
                return VerdictMethode(
                    CONTRADICTION,
                    f"{x.name} = {_texte(a)} n'annule pas la dérivée d'après Wolfram Alpha (points critiques : {liste}).",
                    [_texte(c) for c in critiques],
                ), True
        return VerdictMethode(
            OK, f"Wolfram Alpha confirme les points critiques (f' = 0) : {liste}. La nature des extrema n'est contrôlée que par SymPy.",
            [_texte(c) for c in critiques],
        ), True
    except WolframIndisponible as exc:
        return VerdictMethode(INDISPONIBLE, str(exc)), True
    except ExpressionInvalide as exc:
        return VerdictMethode(INDISPONIBLE, f"Réponse ou expression non interprétable ({exc})."), True
    except (TypeError, ValueError, AttributeError, sp.SympifyError) as exc:
        logger.warning("wolfram : exploitation impossible (%s)", type(exc).__name__)
        return VerdictMethode(INDISPONIBLE, "Réponse Wolfram Alpha non exploitable."), True
