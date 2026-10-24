"""
Modèle « geometrie_triangle » (étape 9.3) : points, segments, triangle, distances et nature d'un triangle dans un repère
orthonormé.

Extraction STRICTE à partir de l'énoncé confirmé :
- chaque point doit être défini par `Lettre(x ; y)` avec deux ENTIERS (|valeur| ≤ 50) ; un point défini deux fois
  différemment, avec 3 coordonnées, des lettres ou un séparateur ambigu rend la simulation impossible ;
- le repère doit être précisé « orthonormé » (sinon les distances dessinées seraient fausses) ;
- les points concernés viennent de la question confirmée (`triangle ABC`, segments `AB`, `AC`, « les points A, B et C »)
  ou, à défaut, des trois seuls points de l'énoncé ; trois points alignés ne forment pas un triangle (pas de figure) ;
- les distances sont calculées en arithmétique entière ET avec SymPy (AB = coef·√rad, rad sans facteur carré) ; la nature
  (rectangle, isocèle, équilatéral…) est déduite des carrés des côtés (réciproque de Pythagore) et recalculée par le front.
Présentations (choisies par le SERVEUR d'après la question confirmée, vocabulaire fermé) : `points` (3 points),
`triangle` (3 points et ses côtés), `distances` (côtés et longueurs des segments demandés), `nature` (distances, angle droit
et nature). Les commandes GeoGebra sont des constantes écrites dans le front, qui revalide tout.
"""

from __future__ import annotations

import logging
import re
from fractions import Fraction
from itertools import combinations

import sympy as sp

from ..correction.coordonnees_vecteur import extraire_points, sans_accents
from ._maths import entier_borne, minuscules_sans_accents, racine_simplifiee, texte_a_plat
from .catalogue import ContexteSimulation, ModeleSimulation, ParametresInvalides, Proposition, enregistrer

logger = logging.getLogger(__name__)

ID = "geometrie_triangle"
VERSION = 1
BORNE = 50

POINTS, TRIANGLE, DISTANCES, NATURE = "points", "triangle", "distances", "nature"
PRESENTATIONS = (POINTS, TRIANGLE, DISTANCES, NATURE)
TYPES_NATURE = ("quelconque", "isocele", "rectangle", "rectangle_isocele", "equilateral")

_RE_REPERE = re.compile(r"\brepere\s+orthonorm")
_RE_TRIANGLE_NOMME = re.compile(r"\btriangle\s+([A-Z])([A-Z])([A-Z])\b")
_RE_TROIS_POINTS = re.compile(r"\bpoints?\s+([A-Z])\s*(?:,|et)\s*([A-Z])\s*(?:,|et)\s*([A-Z])\b(?!\s*(?:,|et)\s*[A-Z]\b)")
_RE_SEGMENT = re.compile(r"(?<![A-Za-z])([A-Z])([A-Z])(?![A-Za-z])")
_RE_EXCLUSION = re.compile(r"\b(?:vecteur|coordonnee|composante|milieu|parallelogramme|cercle|aire|perimetre|angle)s?\b")


def _repere_orthonorme(sources: tuple[str, ...]) -> bool:
    t = minuscules_sans_accents(" ".join(sources))
    return bool(_RE_REPERE.search(t)) and not re.search(r"non\s+orthonorm", t)


def _entier(f) -> int | None:
    return int(f) if f.denominator == 1 and abs(f) <= BORNE else None


def _carre(p: tuple[int, int], q: tuple[int, int]) -> int:
    return (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2


def _longueur(carre: int) -> dict:
    """Longueur = coef·√rad, par entiers ET par SymPy ; ValueError si les deux calculs divergent."""
    coef, rad = racine_simplifiee(carre)
    if sp.simplify(sp.sqrt(carre) - coef * sp.sqrt(rad)) != 0:
        raise ValueError("racine : calculs divergents")
    return {"coef": coef, "rad": rad}


def _nature(carres: dict[str, int], noms: list[str]) -> dict:
    """Nature d'un triangle à partir des carrés de ses côtés (clés « AB », « AC », « BC »)."""
    a, b, c = (noms[0], noms[1], noms[2])
    cotes = {frozenset((a, b)): carres[a + b], frozenset((a, c)): carres[a + c], frozenset((b, c)): carres[b + c]}
    valeurs = sorted(cotes.values())
    droit = None
    if valeurs[0] + valeurs[1] == valeurs[2]:
        plus_long = next(k for k, v in cotes.items() if v == valeurs[2])
        droit = next(n for n in noms if n not in plus_long)  # le sommet opposé au plus grand côté
    egaux = len(set(valeurs)) < 3
    if len(set(valeurs)) == 1:
        type_ = "equilateral"
    elif droit and egaux:
        type_ = "rectangle_isocele"
    elif droit:
        type_ = "rectangle"
    elif egaux:
        type_ = "isocele"
    else:
        type_ = "quelconque"
    return {"type": type_, "sommet_droit": droit}


def _lecture_de_la_question(texte: str, definis: set[str]) -> tuple[str, list[str], list[str]] | None:
    """(présentation, noms ordonnés des points, segments demandés) d'après le texte CONFIRMÉ de la question, sinon None."""
    t = minuscules_sans_accents(texte)
    brut = texte_a_plat(texte)
    if _RE_EXCLUSION.search(t):
        return None  # vecteurs, coordonnées… : modèle vectoriel ; cercles, aires… : hors périmètre
    nomme = _RE_TRIANGLE_NOMME.search(brut)
    trois = _RE_TROIS_POINTS.search(brut)
    segments = [a + b for a, b in _RE_SEGMENT.findall(brut)]
    noms: list[str] = []
    if nomme:
        noms = list(nomme.groups())
    elif trois:
        noms = list(trois.groups())
    elif segments:
        lettres: list[str] = []
        for s in segments:
            for ch in s:
                if ch not in lettres:
                    lettres.append(ch)
        noms = lettres
    elif len(definis) == 3:
        noms = sorted(definis)  # « la nature du triangle » : les trois seuls points de l'énoncé
    if len(set(noms)) != len(noms) or len(noms) not in (2, 3):
        return None
    demandes = [s for s in dict.fromkeys(segments) if set(s) <= set(noms) and len(set(s)) == 2]

    veut_nature = bool(re.search(r"\bnature\b|\b(?:rectangle|isocele|equilateral)\b", t))
    veut_distances = bool(re.search(r"\b(?:longueur|distance|calculer|determiner|mesurer|calcule|donner)s?\b", t)) and bool(demandes or re.search(r"longueurs?|distances?|cotes", t))
    veut_triangle = bool(re.search(r"\b(?:construire|construisez|tracer|tracez|dessiner|dessinez|representer|representez)\b.*\btriangle\b", t))
    veut_points = bool(re.search(r"\b(?:placer|placez|marquer|marquez|situer|situez|representer|representez)\b", t)) and bool(trois)
    if len(noms) == 3 and veut_nature:
        return NATURE, noms, demandes
    if veut_distances and not veut_triangle:
        if not demandes:
            demandes = [noms[0] + noms[1], noms[0] + noms[2], noms[1] + noms[2]] if len(noms) == 3 else [noms[0] + noms[1]]
        return DISTANCES, noms, demandes
    if len(noms) == 3 and veut_triangle:
        return TRIANGLE, noms, []
    if len(noms) == 3 and veut_points:
        return POINTS, noms, []
    return None


def _segments_possibles(noms: list[str]) -> list[str]:
    return [a + b for a, b in combinations(noms, 2)]


def valider(parametres: object) -> dict:
    """Refuse tout paramètre hors cadre ; renvoie la forme normalisée, distances et nature RECALCULÉES (jamais fiées)."""
    if not isinstance(parametres, dict) or {"points", "presentation"} - set(parametres):
        raise ParametresInvalides("Paramètres inattendus.")
    presentation = parametres["presentation"]
    if presentation not in PRESENTATIONS:
        raise ParametresInvalides("Présentation inconnue.")
    # Forme RÉDUITE de la nature (Professeur particulier, voir `projeter`) : points et nature SANS les longueurs (réponse de
    # la question précédente) ; reconnue à l'absence de `demandes`.
    reduite = presentation == NATURE and "demandes" not in parametres
    requis = {"points", "presentation"} | ({"demandes"} if presentation in (DISTANCES, NATURE) and not reduite else set()) | ({"nature"} if reduite else set())
    facultatifs = {DISTANCES: {"longueurs"}, NATURE: set() if reduite else {"longueurs", "nature"}}.get(presentation, set())  # résultats : recalculés puis comparés
    if not requis <= set(parametres) or set(parametres) - requis - facultatifs:
        raise ParametresInvalides("Paramètres inattendus.")
    points = parametres["points"]
    if not isinstance(points, list) or len(points) not in (2, 3) or (len(points) == 2 and presentation != DISTANCES):
        raise ParametresInvalides("Nombre de points invalide.")
    noms, coord = [], []
    for p in points:
        if not isinstance(p, dict) or set(p) != {"nom", "x", "y"} or not isinstance(p["nom"], str) or not re.fullmatch(r"[A-Z]", p["nom"]):
            raise ParametresInvalides("Point mal formé.")
        noms.append(p["nom"])
        coord.append((entier_borne(p["x"], BORNE), entier_borne(p["y"], BORNE)))
    if len(set(noms)) != len(noms) or len(set(coord)) != len(coord):
        raise ParametresInvalides("Points confondus.")
    if len(coord) == 3 and (coord[1][0] - coord[0][0]) * (coord[2][1] - coord[0][1]) - (coord[1][1] - coord[0][1]) * (coord[2][0] - coord[0][0]) == 0:
        raise ParametresInvalides("Points alignés : pas de triangle.")
    sortie = {"points": [{"nom": n, "x": c[0], "y": c[1]} for n, c in zip(noms, coord)], "presentation": presentation}
    if reduite:
        carres = {a + b: _carre(coord[noms.index(a)], coord[noms.index(b)]) for a, b in combinations(noms, 2)}
        sortie["nature"] = _nature(carres, noms)
        if parametres["nature"] != sortie["nature"]:
            raise ParametresInvalides("Résultat incohérent avec le calcul.")
        return sortie
    if presentation in (DISTANCES, NATURE):
        possibles = _segments_possibles(noms)
        demandes = parametres["demandes"]
        if presentation == NATURE:
            demandes = possibles
        if not isinstance(demandes, list) or not demandes or len(set(demandes)) != len(demandes) or any(d not in possibles for d in demandes):
            raise ParametresInvalides("Segments demandés invalides.")
        carres = {a + b: _carre(coord[noms.index(a)], coord[noms.index(b)]) for a, b in combinations(noms, 2)}
        try:
            sortie["demandes"] = [d for d in possibles if d in demandes]
            sortie["longueurs"] = {d: _longueur(carres[d]) for d in sortie["demandes"]}
            if len(noms) == 3:
                sortie["nature"] = _nature(carres, noms)
        except ValueError as exc:
            raise ParametresInvalides(str(exc)) from exc
        if presentation == DISTANCES:
            sortie.pop("nature", None)
        for cle in facultatifs & set(parametres):
            if parametres[cle] != sortie[cle]:
                raise ParametresInvalides("Résultat incohérent avec le calcul.")
    return sortie


def _titre(presentation: str, noms: list[str]) -> str:
    triangle = "".join(noms)
    return {
        POINTS: f"Les points {', '.join(noms[:-1])} et {noms[-1]}",
        TRIANGLE: f"Le triangle {triangle}",
        DISTANCES: f"Distances dans {'le triangle ' + triangle if len(noms) == 3 else 'le segment ' + triangle}",
        NATURE: f"Nature du triangle {triangle}",
    }[presentation]


def proposer(contexte: ContexteSimulation) -> Proposition | None:
    if contexte.matiere != "mathematiques" or not _repere_orthonorme(contexte.sources):
        return None
    points, ambigus = extraire_points(contexte.sources)
    lu = _lecture_de_la_question(contexte.question_texte, set(points) - ambigus)
    if lu is None:
        return None
    presentation, noms, demandes = lu
    if any(n in ambigus or n not in points for n in noms):
        return None
    coord = []
    for n in noms:
        x, y = _entier(points[n][0]), _entier(points[n][1])
        if x is None or y is None:
            return None  # seules les coordonnées entières sont prises en charge
        coord.append((x, y))
    brut = {"points": [{"nom": n, "x": c[0], "y": c[1]} for n, c in zip(noms, coord)], "presentation": presentation}
    if presentation == NATURE:
        brut["demandes"] = _segments_possibles(noms)  # la nature s'appuie sur les trois côtés
    elif presentation == DISTANCES:
        brut["demandes"] = demandes
    try:
        parametres = valider(brut)
    except ParametresInvalides:
        return None  # points confondus ou alignés, distance introuvable : pas de simulation
    return Proposition(
        parametres=parametres,
        titre=_titre(presentation, noms),
        verification={"methodes": ["SymPy", "Calcul exact"], "concordance_correction": "non_applicable"},
    )


def projeter(parametres: dict) -> dict:
    """Projection de divulgation progressive (Professeur particulier, étape 9.4). `points` et `triangle` n'ont ni
    longueurs ni nature (données de l'énoncé et tracé demandé) ; `distances` n'a ni nature ni sommet de l'angle droit ;
    `nature` perd les LONGUEURS (réponse de la question précédente) et ne garde que le type et le sommet de l'angle
    droit, qui sont la réponse de sa propre question."""
    complets = valider(parametres)
    if complets["presentation"] == NATURE and "longueurs" in complets:
        return {"points": complets["points"], "presentation": NATURE, "nature": complets["nature"]}
    return complets


def revelatrice(parametres: dict) -> bool:
    """`distances` (longueurs en étiquettes) et `nature` (angle droit, nature) montrent un RÉSULTAT calculé. `points` et
    `triangle` ne montrent que les données de l'énoncé et la construction demandée, sans longueur, sans marque d'angle
    droit et sans conclusion."""
    return parametres.get("presentation") in (DISTANCES, NATURE)


_RE_LONGUEUR_ECRITE = re.compile(r"(?<![A-Za-z^])([A-Z])([A-Z])\s*=")
_RE_COUPURE = re.compile(r"\s(?:et|puis|donc|soit|ou|car|alors)\s|[;,]\s|\.\s|\.$")
_RE_RACINE_SEULE = re.compile(r"^(?:(\d{1,3})\s*\*?\s*)?(?:√|\\?sqrt)\s*(?:\(\s*(\d{1,6})\s*\)|\{\s*(\d{1,6})\s*\}|(\d{1,6}))$")
_RE_UNITE = re.compile(r"\s*(?:cm|mm|m|km|u\.?l\.?|unites?)\s*\.?$")
_RE_POINT_ECRIT = re.compile(r"(?<![A-Za-z'’])([A-Z])\s*\(\s*([-+]?\d{1,3})\s*;\s*([-+]?\d{1,3})\s*\)")
_RE_NEGATION = re.compile(r"\b(?:pas|non|ni|jamais|aucun)\b|n'est")


def _carre_ecrit(segment: str) -> int | None:
    """Carré de la longueur écrite (« 4 », « √5 », « 2√5 », « 4 cm ») ; None si ce n'est pas un nombre simple."""
    s = _RE_UNITE.sub("", sans_accents(segment.strip().rstrip(".")))
    m = _RE_RACINE_SEULE.fullmatch(s)
    if m:
        coef = int(m.group(1)) if m.group(1) else 1
        return coef * coef * int(next(g for g in m.groups()[1:] if g is not None))
    if not re.fullmatch(r"\d{1,6}(?:[.,]\d{1,3})?", s):
        return None
    valeur = Fraction(s.replace(",", "."))
    carre = valeur * valeur
    return int(carre) if carre.denominator == 1 else None  # un décimal non entier au carré : on ne conclut pas


def _longueurs_ecrites(texte: str) -> dict[str, list[int]]:
    """{segment trié « AB » : carrés écrits} des égalités « AB = … » (valeur finale de chaque chaîne)."""
    sortie: dict[str, list[int]] = {}
    plat = texte_a_plat(texte)
    entetes = list(_RE_LONGUEUR_ECRITE.finditer(plat))
    for i, m in enumerate(entetes):
        fin = entetes[i + 1].start() if i + 1 < len(entetes) else len(plat)
        reste = _RE_COUPURE.split(re.split(r"[;\n]", plat[m.end():fin])[0], maxsplit=1)[0]
        carres = [c for c in (_carre_ecrit(seg) for seg in reste.split("=")) if c is not None]
        if carres and m.group(1) != m.group(2):
            sortie.setdefault("".join(sorted(m.group(1) + m.group(2))), []).append(carres[-1])
    return sortie


def _controler_nature(valides: dict, texte: str) -> str | None:
    nature = valides["nature"]
    t = minuscules_sans_accents(texte)
    if _RE_NEGATION.search(t):
        return None  # « n'est pas rectangle » : aucune confirmation par mot-clé
    dit = set()
    if re.search(r"\brectangle", t):
        dit.add("rectangle")
    if re.search(r"\bisocele", t):
        dit.add("isocele")
    if re.search(r"\bequilateral", t):
        dit.add("equilateral")
    if "quelconque" in t:
        dit.add("quelconque")
    if not dit:
        return None
    attendu = {"quelconque": {"quelconque"}, "isocele": {"isocele"}, "rectangle": {"rectangle"},
               "rectangle_isocele": {"rectangle", "isocele"}, "equilateral": {"equilateral"}}[nature["type"]]
    if nature["type"] == "equilateral":
        dit.discard("isocele")  # un triangle équilatéral est aussi isocèle
    if dit != attendu:
        return "contredit"
    if nature["sommet_droit"]:
        sommets = set(re.findall(r"\ben\s+([a-z])\b", texte_a_plat(texte).casefold()))  # « rectangle en A »
        sommets = {s.upper() for s in sommets} & {p["nom"] for p in valides["points"]}
        if not sommets:
            return None  # le sommet de l'angle droit n'est pas précisé : rien à confirmer
        return "confirme" if sommets == {nature["sommet_droit"]} else "contredit"
    return "confirme"


def controler(parametres: dict, texte: str) -> str | None:
    """Contrôle déterministe INDÉPENDANT d'une réponse d'élève (jamais l'avis de l'IA), d'après l'énoncé confirmé :
    - `distances` : les longueurs écrites (4, √5, 2√5…) sont comparées aux distances recalculées ; « confirme » si TOUS
      les segments demandés sont écrits et justes, « contredit » si l'un diffère ;
    - `nature` : le type écrit (rectangle, isocèle…) et le sommet de l'angle droit sont comparés à la nature recalculée ;
    - `points` / `triangle` : jamais « confirme » ; « contredit » si une coordonnée écrite contredit l'énoncé ;
    - None : rien d'exploitable (ou négation : aucune confirmation par mot-clé)."""
    try:
        valides = valider(parametres)
    except ParametresInvalides:
        return None
    presentation = valides["presentation"]
    coordonnees = {p["nom"]: (p["x"], p["y"]) for p in valides["points"]}
    for m in _RE_POINT_ECRIT.finditer(texte_a_plat(texte)):
        if m.group(1) in coordonnees and coordonnees[m.group(1)] != (int(m.group(2)), int(m.group(3))):
            return "contredit"
    if presentation == NATURE:
        verdict = _controler_nature(valides, texte)
        if verdict is not None:
            return verdict
    if presentation in (DISTANCES, NATURE):
        ecrites = _longueurs_ecrites(texte)
        attendus = {}
        for segment, l in valides["longueurs"].items():
            attendus["".join(sorted(segment))] = l["coef"] ** 2 * l["rad"]
        if any(carres[-1] != attendus[segment] for segment, carres in ecrites.items() if segment in attendus):
            return "contredit"
        demandes = {"".join(sorted(s)) for s in valides["demandes"]}
        if presentation == DISTANCES and demandes and all(s in ecrites for s in demandes):
            return "confirme"
    return None


MODELE = enregistrer(ModeleSimulation(
    id=ID,
    version=VERSION,
    titre="Géométrie plane : points, triangle, distances et nature",
    matieres=frozenset({"mathematiques"}),
    notions=("géométrie analytique plane", "distance entre deux points", "triangle", "réciproque du théorème de Pythagore"),
    parametres={
        "points": "2 ou 3 points distincts, nom (une majuscule) et coordonnées ENTIÈRES (|valeur| ≤ 50)",
        "presentation": "« points », « triangle », « distances » ou « nature » : choisi par le serveur d'après la question confirmée",
        "demandes": "segments dont la longueur est demandée (distances ; tous les côtés pour la nature)",
        "longueurs": "coef·√rad par côté (entiers et SymPy)",
        "nature": "type et sommet de l'angle droit, déduits des carrés des côtés",
    },
    conditions=(
        "chaque point est défini sans ambiguïté par `Lettre(x ; y)` avec deux entiers dans l'énoncé confirmé",
        "le repère est précisé « orthonormé »",
        "la question demande de placer 3 points, de construire un triangle, de calculer des distances ou de trouver sa nature",
        "trois points non alignés pour tout triangle",
    ),
    proposer=proposer,
    valider=valider,
    projeter=projeter,
    revelatrice=revelatrice,
    controler=controler,
))
