"""
Modèle « vecteur_deux_points » : deux points A et B d'un repère orthonormé et le vecteur AB.

Extraction STRICTE à partir de l'énoncé confirmé :
- chaque point doit être défini par `Lettre(x ; y)` avec deux nombres décimaux (au plus 2 chiffres après la
  virgule) séparés par un point-virgule ; toute autre écriture (3 coordonnées, lettres, séparateur ambigu,
  définitions contradictoires) rend le point AMBIGU et supprime la simulation ;
- la question doit nommer un seul vecteur de ces deux points (« vecteur AB », `\\overrightarrow{AB}`, `\\vec{AB}`)
  ou demander de placer deux points (« Placer les points A et B ») ;
- l'énoncé doit préciser « repère orthonormé » (sinon le dessin pourrait être faux).
Les coordonnées du vecteur sont recalculées avec SymPy ET en arithmétique exacte, puis recoupées avec le
résultat de la correction (lecteur strict de `correction/coordonnees_vecteur.py`) lorsqu'il s'écrit sans
ambiguïté : une contradiction supprime la simulation.

PRÉSENTATION (étape 9.1.2) : paramètre `presentation`, choisi par le SERVEUR d'après le texte confirmé de la
question — jamais par l'IA — parmi un vocabulaire fermé :
- `points` : seulement A et B (« Placer les points A et B ») ;
- `vecteur` : A, B et le vecteur AB orienté de A vers B (« Représenter le vecteur AB ») ;
- `composantes` : le vecteur et ses composantes horizontale Δx et verticale Δy (« Déterminer les coordonnées… »).
Les commandes GeoGebra de chaque présentation sont des constantes écrites dans le front.
"""

from __future__ import annotations

import logging
import math
import re
from decimal import Decimal
from fractions import Fraction

from ..correction.coordonnees_vecteur import (
    demande_les_coordonnees,
    extraire_points,
    lire_coordonnees,
    normaliser,
    sans_accents,
    vecteur_demande,
    vecteur_exact,
)
from .catalogue import ContexteSimulation, ModeleSimulation, ParametresInvalides, Proposition, enregistrer

logger = logging.getLogger(__name__)

ID = "vecteur_deux_points"
VERSION = 2  # 2 : ajout du paramètre `presentation`
BORNE = 50  # |coordonnée| maximale acceptée (fenêtre GeoGebra lisible)

POINTS, VECTEUR, COMPOSANTES = "points", "vecteur", "composantes"
PRESENTATIONS = (POINTS, VECTEUR, COMPOSANTES)

_RE_VERBE_PLACEMENT = re.compile(
    r"\b(?:placer|placez|placons|marquer|marquez|situer|situez|positionner|positionnez|construire|construisez|representer|representez)\b",
    re.I,
)
_RE_POINTS_NOMMES = re.compile(r"\b[Pp]oints?\s+([A-Z])\s*(?:et|,)\s*([A-Z])\b(?!\s*(?:,|et)\s*[A-Z]\b)")
_RE_MENTION_POINT = re.compile(r"\b[Pp]oints?\s+[A-Z]\b")  # « point A », « points A et B » : une mention par groupe
_RE_UN_VECTEUR = re.compile(r"vecteur\s+[A-Z][A-Z]\b")


def _repere_orthonorme(sources: tuple[str, ...]) -> bool:
    t = sans_accents(" ".join(sources)).casefold()
    return bool(re.search(r"\brepere\s+orthonorm", t)) and not re.search(r"non\s+orthonorm", t)


def _lecture_de_la_question(texte: str) -> tuple[str, tuple[str, str]] | None:
    """(présentation, (nom du 1er point, nom du 2e point)) d'après le texte CONFIRMÉ de la question, sinon None.

    - un seul vecteur nommé : `composantes` si la question demande des coordonnées/composantes, sinon `vecteur` ;
    - aucun vecteur mais « Placer les points A et B » (verbe de placement + exactement deux points nommés) : `points` ;
    - tout le reste (plusieurs vecteurs, aucune consigne reconnue) : pas de simulation.
    """
    nommes = vecteur_demande(texte)
    if nommes is not None:
        return (COMPOSANTES if demande_les_coordonnees(texte) else VECTEUR), nommes
    plat = normaliser(texte)
    if _RE_UN_VECTEUR.search(plat):
        return None  # plusieurs vecteurs nommés : ambigu
    paires = {(a, b) for a, b in _RE_POINTS_NOMMES.findall(plat)}
    if len(paires) != 1 or len(_RE_MENTION_POINT.findall(plat)) != 1 or not _RE_VERBE_PLACEMENT.search(sans_accents(plat)):
        return None
    a, b = next(iter(paires))
    return (POINTS, (a, b)) if a != b else None


def _nombre_json(valeur: Fraction) -> int | float:
    return int(valeur) if valeur.denominator == 1 else float(valeur)


def _fraction_de(valeur: object) -> Fraction:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not math.isfinite(valeur):
        raise ParametresInvalides("Coordonnée non numérique.")
    f = Fraction(Decimal(repr(valeur)))
    if abs(f) > BORNE or (f * 100).denominator != 1:
        raise ParametresInvalides("Coordonnée hors des bornes ou trop précise.")
    return f


def valider(parametres: object) -> dict:
    """Refuse tout paramètre hors cadre ; renvoie la forme normalisée.

    Forme COMPLÈTE (correction) : points, vecteur {nom, x, y}, presentation. Formes RÉDUITES (divulgation progressive du
    Professeur particulier, voir `projeter`) : `points` sans vecteur ; `vecteur` avec seulement son nom. La
    présentation `composantes` exige toujours la forme complète."""
    if not isinstance(parametres, dict) or not {"points", "presentation"} <= set(parametres) or set(parametres) - {"points", "vecteur", "presentation"}:
        raise ParametresInvalides("Paramètres inattendus.")
    presentation = parametres["presentation"]
    if presentation not in PRESENTATIONS:
        raise ParametresInvalides("Présentation inconnue.")
    points, vecteur = parametres["points"], parametres.get("vecteur")
    if not isinstance(points, list) or len(points) != 2:
        raise ParametresInvalides("Il faut exactement deux points.")
    if vecteur is None and "vecteur" in parametres:
        raise ParametresInvalides("Vecteur mal formé.")
    if vecteur is None and presentation != POINTS:
        raise ParametresInvalides("Cette présentation exige le vecteur.")
    if vecteur is not None and not isinstance(vecteur, dict):
        raise ParametresInvalides("Vecteur mal formé.")
    noms, coord = [], []
    for p in points:
        if not isinstance(p, dict) or set(p) != {"nom", "x", "y"}:
            raise ParametresInvalides("Point mal formé.")
        if not isinstance(p["nom"], str) or not re.fullmatch(r"[A-Z]", p["nom"]):
            raise ParametresInvalides("Nom de point invalide.")
        noms.append(p["nom"])
        coord.append((_fraction_de(p["x"]), _fraction_de(p["y"])))
    if noms[0] == noms[1]:
        raise ParametresInvalides("Les deux points doivent être distincts.")
    sortie = {
        "points": [{"nom": n, "x": _nombre_json(c[0]), "y": _nombre_json(c[1])} for n, c in zip(noms, coord)],
        "presentation": presentation,
    }
    if vecteur is None:
        return sortie
    nom_vecteur = noms[0] + noms[1]
    attendu = (coord[1][0] - coord[0][0], coord[1][1] - coord[0][1])
    if set(vecteur) == {"nom"} and presentation == VECTEUR:  # forme réduite : le nom seulement, aucune coordonnée
        if vecteur["nom"] != nom_vecteur:
            raise ParametresInvalides("Vecteur incohérent avec les points.")
        sortie["vecteur"] = {"nom": nom_vecteur}
        return sortie
    if set(vecteur) != {"nom", "x", "y"} or vecteur["nom"] != nom_vecteur:
        raise ParametresInvalides("Vecteur incohérent avec les points.")
    if (_fraction_de(vecteur["x"]), _fraction_de(vecteur["y"])) != attendu:
        raise ParametresInvalides("Les coordonnées du vecteur ne correspondent pas à B − A.")
    sortie["vecteur"] = {"nom": nom_vecteur, "x": _nombre_json(attendu[0]), "y": _nombre_json(attendu[1])}
    return sortie


def projeter(parametres: dict) -> dict:
    """Projection de DIVULGATION PROGRESSIVE (Professeur particulier) : paramètres validés, sans ce qui donnerait la
    réponse d'une question non encore dévoilée. Les coordonnées du vecteur sont la réponse de « Déterminer les
    coordonnées » : elles ne partent donc que pour la présentation `composantes`. La présentation `vecteur` (tracé
    de AB de A vers B) n'en a pas besoin ; `points` non plus."""
    complets = valider(parametres)
    if complets["presentation"] == POINTS:
        return {"points": complets["points"], "presentation": POINTS}
    if complets["presentation"] == VECTEUR:
        return {"points": complets["points"], "vecteur": {"nom": complets["vecteur"]["nom"]}, "presentation": VECTEUR}
    return complets


def revelatrice(parametres: dict) -> bool:
    """Seule la présentation `composantes` montre un RÉSULTAT calculé (coordonnées de AB, Δx, Δy). `points` et `vecteur`
    n'affichent que des données de l'énoncé et le tracé demandé, sans aucune valeur calculée."""
    return parametres.get("presentation") == COMPOSANTES


_NUM = r"[-−–]?\s*\d+(?:[.,]\d+)?"
_PAIRE = re.compile(
    rf"(?:\b([A-Z]{{1,2}})\s*=?\s*)?\(\s*({_NUM})\s*;\s*({_NUM})\s*\)"  # (x ; y), décimaux admis
    rf"|(?:\b([A-Z]{{1,2}})\s*=?\s*)?\(\s*([-−–]?\d+)\s*,\s*([-−–]?\d+)\s*\)"  # (x, y) entiers
    r"|\\begin\{[pb]matrix\}\s*([-−–]?\d+(?:[.,]\d+)?)\s*\\\\\s*([-−–]?\d+(?:[.,]\d+)?)\s*\\end\{[pb]matrix\}"
)
_ETIQUETTE = re.compile(rf"(?:Δ|delta\s*|\b)([xy])\s*=\s*({_NUM})", re.I)


def _decimal(texte: str) -> Fraction:
    return Fraction(texte.replace("−", "-").replace("–", "-").replace(" ", "").replace(",", "."))


def _lire_paires(texte: str) -> list[tuple[str, Fraction, Fraction]]:
    """Couples lus dans la réponse : (nom éventuel, x, y). Écritures reconnues : A(1 ; 2), AB = (3 ; 1), (3, 1), pmatrix."""
    sortie = []
    for m in _PAIRE.finditer(texte):
        g = m.groups()
        try:
            if g[1] is not None:
                sortie.append((g[0] or "", _decimal(g[1]), _decimal(g[2])))
            elif g[4] is not None:
                sortie.append((g[3] or "", _decimal(g[4]), _decimal(g[5])))
            else:
                sortie.append(("", _decimal(g[6]), _decimal(g[7])))
        except (ValueError, ZeroDivisionError):
            continue
    return sortie


def controler(parametres: dict, texte: str) -> str | None:
    """Contrôle déterministe INDÉPENDANT d'une réponse d'élève (jamais l'avis de l'IA) : compare les coordonnées écrites
    aux valeurs recalculées depuis l'énoncé confirmé (B − A en arithmétique exacte).

    - `composantes` : « confirme » si le résultat écrit est (Δx ; Δy) ; « contredit » s'il en diffère ;
    - `points` / `vecteur` : jamais « confirme » (ces questions n'attendent pas de résultat chiffré), mais « contredit »
      si une coordonnée écrite contredit l'énoncé (ex. « B(9 ; 9) » alors que B(4 ; 3)) ;
    - None : la réponse ne contient aucune coordonnée exploitable."""
    try:
        valides = valider(parametres)
        (pa, pb) = valides["points"]
        a = (_fraction_de(pa["x"]), _fraction_de(pa["y"]))
        b = (_fraction_de(pb["x"]), _fraction_de(pb["y"]))
    except (ParametresInvalides, ValueError, TypeError, KeyError):
        return None
    d = (b[0] - a[0], b[1] - a[1])
    donnees = {pa["nom"]: a, pb["nom"]: b}
    nom_vecteur = pa["nom"] + pb["nom"]
    resultats, contredit = [], False
    for nom, x, y in _lire_paires(texte):
        if nom in donnees:  # « A(1 ; 2) » : donnée de l'énoncé
            contredit = contredit or (x, y) != donnees[nom]
        elif nom in ("", nom_vecteur):
            resultats.append((x, y))
        # autre nom (ex. « M(…) ») : sans rapport avec cet exercice, ignoré
    etiquettes = {}
    for m in _ETIQUETTE.finditer(texte):
        try:
            etiquettes.setdefault(m.group(1).lower(), _decimal(m.group(2)))
        except (ValueError, ZeroDivisionError):
            continue
    if valides["presentation"] != COMPOSANTES:
        # Une coordonnée sans nom peut désigner A, B ou le vecteur AB.
        permis = {a, b, d}
        if contredit or any(r not in permis for r in resultats):
            return "contredit"
        return None
    if contredit:
        return "contredit"
    if resultats:
        return "confirme" if all(r == d for r in resultats) else "contredit"
    if "x" in etiquettes and "y" in etiquettes:
        return "confirme" if (etiquettes["x"], etiquettes["y"]) == d else "contredit"
    if etiquettes:
        valeur = etiquettes.get("x", etiquettes.get("y"))
        attendu = d[0] if "x" in etiquettes else d[1]
        return "contredit" if valeur != attendu else None  # une moitié juste ne confirme rien
    return None


def _titre(presentation: str, na: str, nb: str) -> str:
    if presentation == POINTS:
        return f"Points {na} et {nb}"
    if presentation == COMPOSANTES:
        return f"Vecteur {na}{nb} et ses composantes"
    return f"Points {na}, {nb} et vecteur {na}{nb}"


def proposer(contexte: ContexteSimulation) -> Proposition | None:
    if contexte.matiere != "mathematiques":
        return None
    lu = _lecture_de_la_question(contexte.question_texte)
    if lu is None or not _repere_orthonorme(contexte.sources):
        return None
    presentation, (na, nb) = lu
    points, ambigus = extraire_points(contexte.sources)
    if na in ambigus or nb in ambigus or na not in points or nb not in points:
        return None
    a, b = points[na], points[nb]
    if a == b:
        return None
    if max(abs(c) for c in (*a, *b)) > BORNE:
        return None

    direct = vecteur_exact(a, b)  # B − A en arithmétique exacte ET avec SymPy : les deux doivent concorder
    if direct is None:
        logger.error("simulation vecteur_deux_points : calculs SymPy et exact divergents")
        return None

    # Recoupement avec la réponse rédigée (lecteur strict) : seule une lecture SANS ambiguïté peut contredire, et la
    # simulation n'établit rien. Le statut de concordance affiché à l'élève est calculé à part
    # (correction/concordance.py) et ne dépend jamais de la présence d'une simulation. Il n'a de sens que lorsque la
    # question demande les coordonnées (`composantes`) ; ailleurs la mention est « non applicable ».
    concordance = "non_applicable"
    if presentation != POINTS:
        lecture = lire_coordonnees(contexte.resultat, na + nb)
        if lecture.statut == "lue" and lecture.valeur != direct:
            logger.warning("simulation vecteur_deux_points supprimée : le résultat de la correction contredit B - A")
            return None
        if presentation == COMPOSANTES:
            concordance = "confirmee" if lecture.statut == "lue" else "non_verifiee"

    parametres = valider({
        "points": [
            {"nom": na, "x": _nombre_json(a[0]), "y": _nombre_json(a[1])},
            {"nom": nb, "x": _nombre_json(b[0]), "y": _nombre_json(b[1])},
        ],
        "vecteur": {"nom": na + nb, "x": _nombre_json(direct[0]), "y": _nombre_json(direct[1])},
        "presentation": presentation,
    })
    return Proposition(
        parametres=parametres,
        titre=_titre(presentation, na, nb),
        verification={"methodes": ["SymPy", "Calcul exact"], "concordance_correction": concordance},
    )


MODELE = enregistrer(ModeleSimulation(
    id=ID,
    version=VERSION,
    titre="Deux points et le vecteur qui les joint",
    matieres=frozenset({"mathematiques"}),
    notions=("vecteurs", "coordonnées d'un vecteur", "composantes d'un vecteur", "géométrie analytique plane"),
    parametres={
        "points": "deux points distincts, nom (une majuscule) et coordonnées décimales (≤ 2 décimales, |valeur| ≤ 50)",
        "vecteur": "nom = AB et coordonnées = B − A (recalculées et vérifiées) ; Δx et Δy sont ses coordonnées",
        "presentation": "« points », « vecteur » ou « composantes » : choisi par le serveur d'après la question confirmée",
    },
    conditions=(
        "la question nomme un seul vecteur de deux points (« vecteur AB ») ou demande de placer deux points (« points A et B »)",
        "les deux points sont définis sans ambiguïté par Lettre(x ; y) dans l'énoncé confirmé",
        "le repère est précisé « orthonormé »",
        "le résultat de la correction, s'il s'écrit sans ambiguïté, concorde avec B − A",
    ),
    proposer=proposer,
    valider=valider,
    projeter=projeter,
    revelatrice=revelatrice,
    controler=controler,
))
