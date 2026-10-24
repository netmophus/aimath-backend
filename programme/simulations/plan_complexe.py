"""
Modèle « plan_complexe » (étape 9.3) : un nombre complexe z = a + bi, son image M(a ; b) dans le plan complexe, son
conjugué, son module et son argument.

Extraction STRICTE à partir de l'énoncé confirmé :
- z doit être défini par `z = a + bi` (parties réelle et imaginaire ENTIÈRES, |valeur| ≤ 50, forme algébrique complète :
  `3 + 2i`, `-1 - i`, `2i`) ; une définition contradictoire, plusieurs nombres sans désignation claire, ou toute autre
  écriture (fraction, produit, quotient, partie décimale) supprime la simulation ;
- la question choisit la PRÉSENTATION (vocabulaire fermé, décidée par le SERVEUR, jamais par l'IA) :
  `point` (« Représenter z »), `conjugue`, `module`, `argument` (module + argument, forme trigonométrique) ;
- les résultats sont CALCULÉS : module par SymPy et en arithmétique entière (√(a² + b²) = coef·√rad), conjugué par SymPy,
  argument par SymPy (exact lorsque c'est un multiple rationnel de π, sinon valeur approchée).
Les commandes GeoGebra sont des constantes écrites dans le front, qui revalide tout.
"""

from __future__ import annotations

import logging
import math
import re

import sympy as sp

from ._maths import entier_borne, minuscules_sans_accents, racine_simplifiee, texte_a_plat
from .catalogue import ContexteSimulation, ModeleSimulation, ParametresInvalides, Proposition, enregistrer

logger = logging.getLogger(__name__)

ID = "plan_complexe"
VERSION = 1
BORNE = 50

POINT, CONJUGUE, MODULE, ARGUMENT = "point", "conjugue", "module", "argument"
PRESENTATIONS = (POINT, CONJUGUE, MODULE, ARGUMENT)

_NOM = r"[zw](?:_\{?\d\}?)?"
_RE_DEFINITION = re.compile(
    rf"(?<![A-Za-z\\])({_NOM})\s*=\s*"
    r"([-+]?\s*\d{1,3}\s*[-+]\s*(?:\d{1,3}\s*)?\*?\s*i|[-+]?\s*(?:\d{1,3}\s*)?\*?\s*i)"
    r"(?![A-Za-z0-9^*/(])"
)
_RE_ALGEBRIQUE = re.compile(r"^([-+]?\d+)([-+])(\d*)i$")
_RE_IMAGINAIRE_PUR = re.compile(r"^([-+]?)(\d*)i$")
_RE_ARGUMENT_EXACT = re.compile(r"^(?:0|-?(?:\d{1,2})?π(?:/\d{1,2})?)$")


def _nom_canonique(nom: str) -> str:
    return re.sub(r"[{}]", "", nom)


def _lire_nombre(ecriture: str) -> tuple[int, int] | None:
    s = re.sub(r"\s+", "", ecriture).replace("*", "")
    m = _RE_ALGEBRIQUE.fullmatch(s)
    if m:
        a = int(m.group(1))
        b = (-1 if m.group(2) == "-" else 1) * (int(m.group(3)) if m.group(3) else 1)
        return a, b
    m = _RE_IMAGINAIRE_PUR.fullmatch(s)
    if m:
        return 0, (-1 if m.group(1) == "-" else 1) * (int(m.group(2)) if m.group(2) else 1)
    return None


def extraire_nombres(sources: tuple[str, ...]) -> tuple[dict[str, tuple[int, int]], set[str]]:
    """(nombres définis sans ambiguïté {nom: (a, b)}, noms ambigus)."""
    nombres: dict[str, tuple[int, int]] = {}
    ambigus: set[str] = set()
    for source in sources:
        for nom, ecriture in _RE_DEFINITION.findall(texte_a_plat(source)):
            nom = _nom_canonique(nom)
            lu = _lire_nombre(ecriture)
            if lu is None or max(abs(lu[0]), abs(lu[1])) > BORNE:
                ambigus.add(nom)
                continue
            if nom in nombres and nombres[nom] != lu:
                ambigus.add(nom)
            nombres[nom] = lu
    return nombres, ambigus


def _lecture_de_la_question(texte: str) -> str | None:
    """Présentation d'après le texte CONFIRMÉ de la question, sinon None (aucune consigne reconnue ou ambiguïté)."""
    t = minuscules_sans_accents(texte)
    demandes = set()
    if re.search(r"conjugu", t):
        demandes.add(CONJUGUE)
    if re.search(r"\bmodule\b|\|\s*[zw]", t):
        demandes.add(MODULE)
    if re.search(r"\bargument\b|forme\s+(?:trigonometrique|exponentielle|polaire)", t):
        demandes.add(ARGUMENT)
    if demandes in ({CONJUGUE}, {MODULE}, {ARGUMENT}):
        return next(iter(demandes))
    if demandes == {MODULE, ARGUMENT}:
        return ARGUMENT  # la présentation « argument » montre aussi le module
    if demandes:
        return None  # conjugué + module : plusieurs consignes à la fois, pas de figure unique
    if re.search(r"\b(?:representer|representez|placer|placez|construire|construisez|situer|situez|tracer|visualiser)\b", t) and (
        re.search(r"plan\s+complexe|affixe|\bimage\b|\b[zw]\b", t)
    ):
        return POINT
    return None


def _cible(nombres: dict[str, tuple[int, int]], ambigus: set[str], texte: str) -> tuple[str, tuple[int, int]] | None:
    """Le nombre dont parle la question : l'unique nombre défini, ou celui que la question nomme (et lui seul)."""
    if ambigus or not nombres:
        return None
    if len(nombres) == 1:
        return next(iter(nombres.items()))
    plat = re.sub(r"[{}]", "", texte_a_plat(texte))
    cites = [n for n in nombres if re.search(rf"(?<![A-Za-z]){re.escape(n)}(?![A-Za-z0-9_])", plat)]
    return (cites[0], nombres[cites[0]]) if len(cites) == 1 else None


def _calculs(a: int, b: int) -> dict | None:
    """Module, conjugué et argument de a + bi, par SymPy ET en arithmétique entière ; None si les calculs divergent."""
    z = sp.Integer(a) + sp.Integer(b) * sp.I
    coef, rad = racine_simplifiee(a * a + b * b)
    if sp.simplify(sp.Abs(z) - coef * sp.sqrt(rad)) != 0:
        return None
    if sp.conjugate(z) != sp.Integer(a) - sp.Integer(b) * sp.I:
        return None
    theta = sp.arg(z)
    radians = float(theta)
    exact = None
    ratio = sp.nsimplify(theta / sp.pi, rational=True, tolerance=1e-12)
    if ratio.is_Rational and ratio.q <= 12:
        exact = _ecrire_argument(int(ratio.p), int(ratio.q))
    if abs(math.cos(radians) * math.sqrt(a * a + b * b) - a) > 1e-9 or abs(math.sin(radians) * math.sqrt(a * a + b * b) - b) > 1e-9:
        return None
    return {"module": {"coef": coef, "rad": rad}, "argument": {"exact": exact, "radians": round(radians, 6)}}


def _ecrire_argument(p: int, q: int) -> str:
    """p/q × π écrit « π/4 », « -2π/3 », « π », « 0 »."""
    if p == 0:
        return "0"
    signe = "-" if p < 0 else ""
    p = abs(p)
    numerateur = "π" if p == 1 else f"{p}π"
    return f"{signe}{numerateur}" if q == 1 else f"{signe}{numerateur}/{q}"


def valider(parametres: object) -> dict:
    """Refuse tout paramètre hors cadre ; renvoie la forme normalisée, résultats RECALCULÉS (jamais fiés)."""
    if not isinstance(parametres, dict) or {"nom", "a", "b", "presentation"} - set(parametres):
        raise ParametresInvalides("Paramètres inattendus.")
    presentation = parametres["presentation"]
    if presentation not in PRESENTATIONS:
        raise ParametresInvalides("Présentation inconnue.")
    attendus = {"nom", "a", "b", "presentation"} | ({"module"} if presentation in (MODULE, ARGUMENT) else set()) | (
        {"argument"} if presentation == ARGUMENT else set())
    if set(parametres) != attendus:
        raise ParametresInvalides("Paramètres inattendus.")
    nom = parametres["nom"]
    if not isinstance(nom, str) or not re.fullmatch(r"[zw](?:_\d)?", nom):
        raise ParametresInvalides("Nom de nombre complexe invalide.")
    a, b = entier_borne(parametres["a"], BORNE), entier_borne(parametres["b"], BORNE)
    if a == 0 and b == 0:
        raise ParametresInvalides("Nombre nul : pas de figure.")
    calcul = _calculs(a, b)
    if calcul is None:
        raise ParametresInvalides("Calculs divergents.")
    sortie = {"nom": nom, "a": a, "b": b, "presentation": presentation}
    if presentation in (MODULE, ARGUMENT):
        if parametres["module"] != calcul["module"]:
            raise ParametresInvalides("Module incohérent.")
        sortie["module"] = calcul["module"]
    if presentation == ARGUMENT:
        donne = parametres["argument"]
        if not isinstance(donne, dict) or set(donne) != {"exact", "radians"} or donne != calcul["argument"]:
            raise ParametresInvalides("Argument incohérent.")
        if donne["exact"] is not None and not _RE_ARGUMENT_EXACT.fullmatch(donne["exact"]):
            raise ParametresInvalides("Argument exact mal écrit.")
        sortie["argument"] = calcul["argument"]
    return sortie


def _titre(presentation: str, nom: str) -> str:
    return {
        POINT: f"Image du nombre complexe {nom} dans le plan complexe",
        CONJUGUE: f"Le nombre {nom} et son conjugué",
        MODULE: f"Module du nombre complexe {nom}",
        ARGUMENT: f"Module et argument de {nom}",
    }[presentation]


def proposer(contexte: ContexteSimulation) -> Proposition | None:
    if contexte.matiere != "mathematiques":
        return None
    presentation = _lecture_de_la_question(contexte.question_texte)
    if presentation is None:
        return None
    nombres, ambigus = extraire_nombres(contexte.sources)
    cible = _cible(nombres, ambigus, contexte.question_texte)
    if cible is None:
        return None
    nom, (a, b) = cible
    if a == 0 and b == 0:
        return None
    calcul = _calculs(a, b)
    if calcul is None:
        logger.error("simulation plan_complexe : calculs SymPy et entiers divergents")
        return None
    brut = {"nom": nom, "a": a, "b": b, "presentation": presentation}
    if presentation in (MODULE, ARGUMENT):
        brut["module"] = calcul["module"]
    if presentation == ARGUMENT:
        brut["argument"] = calcul["argument"]
    return Proposition(
        parametres=valider(brut),
        titre=_titre(presentation, nom),
        verification={"methodes": ["SymPy", "Calcul exact"], "concordance_correction": "non_applicable"},
    )


def projeter(parametres: dict) -> dict:
    """Projection de divulgation progressive (Professeur particulier, étape 9.4) : paramètres validés. Chaque
    présentation ne contient déjà QUE ce qu'elle montre (`point` : a et b, données de l'énoncé ; `conjugue` : a et b ;
    `module` : + module ; `argument` : + module et argument) : jamais le résultat d'une autre question. Ce qui est
    révélateur est retenu par `revelatrice` tant que la réponse n'est pas prouvée ou la solution débloquée."""
    return valider(parametres)


def revelatrice(parametres: dict) -> bool:
    """Seule la présentation `point` (représenter z : données de l'énoncé) ne montre aucun résultat calculé. Le conjugué
    (point M′ symétrique), le module (longueur du vecteur OM) et l'argument (arc) sont la RÉPONSE de leur question,
    même sans nombre affiché."""
    return parametres.get("presentation") != POINT


_RE_COMPLEXE_ECRIT = re.compile(r"(?<![\w.^])([-+]?\d{1,3})\s*([-+])\s*(\d{0,3})\s*\*?\s*i(?![\w])")
_RE_COUPLE = re.compile(r"\(\s*([-+]?\d{1,3})\s*;\s*([-+]?\d{1,3})\s*\)")
_RE_COUPLE_M = re.compile(r"(?<![\w'’])M\s*\(\s*([-+]?\d{1,3})\s*;\s*([-+]?\d{1,3})\s*\)")
_RE_RACINE = re.compile(
    r"(?<![\w.])(?:(\d{1,3})\s*\*?\s*)?(?:√|\\?sqrt)\s*(?:\(\s*(\d{1,6})\s*\)|\{\s*(\d{1,6})\s*\}|(\d{1,6})(?![\d^]))"
)


def _valeurs_complexes(texte: str) -> list[tuple[int, int]]:
    """Nombres complexes (a, b) ÉCRITS dans la réponse (3 - 2i, couples (3 ; -2)), dans l'ordre d'apparition."""
    t = texte_a_plat(texte)
    trouves: list[tuple[int, tuple[int, int]]] = []
    for m in _RE_COMPLEXE_ECRIT.finditer(t):
        b = (-1 if m.group(2) == "-" else 1) * (int(m.group(3)) if m.group(3) else 1)
        trouves.append((m.start(), (int(m.group(1)), b)))
    for m in _RE_COUPLE.finditer(t):
        trouves.append((m.start(), (int(m.group(1)), int(m.group(2)))))
    return [v for _, v in sorted(trouves)]


def controler(parametres: dict, texte: str) -> str | None:
    """Contrôle déterministe INDÉPENDANT d'une réponse d'élève (jamais l'avis de l'IA), d'après l'énoncé confirmé :
    - `module` : la dernière racine écrite est-elle √(a² + b²) ? (« confirme » / « contredit ») ;
    - `conjugue` : le dernier nombre écrit, hors z lui-même, est-il a − bi ? ;
    - `point` : jamais « confirme » ; « contredit » si « M(x ; y) » diffère de (a ; b) ;
    - `argument` et réponses sans écriture exploitable : None."""
    try:
        valides = valider(parametres)
    except ParametresInvalides:
        return None
    a, b, presentation = valides["a"], valides["b"], valides["presentation"]
    if presentation == MODULE:
        racines = []
        for m in _RE_RACINE.finditer(texte_a_plat(texte)):
            coef = int(m.group(1)) if m.group(1) else 1
            rad = int(next(g for g in m.groups()[1:] if g is not None))
            racines.append(coef * coef * rad)
        if not racines:
            return None
        return "confirme" if racines[-1] == a * a + b * b else "contredit"
    if presentation == CONJUGUE:
        if a == 0:
            return None  # imaginaire pur : écritures trop variées pour un contrôle fiable
        restantes = [v for v in _valeurs_complexes(texte) if v != (a, b)]
        if not restantes:
            return None
        return "confirme" if restantes[-1] == (a, -b) else "contredit"
    if presentation == POINT:
        for m in _RE_COUPLE_M.finditer(texte_a_plat(texte)):
            if (int(m.group(1)), int(m.group(2))) != (a, b):
                return "contredit"
        return None
    return None


MODELE = enregistrer(ModeleSimulation(
    id=ID,
    version=VERSION,
    titre="Plan complexe : image, conjugué, module et argument",
    matieres=frozenset({"mathematiques"}),
    notions=("nombres complexes", "plan complexe", "conjugué", "module", "argument"),
    parametres={
        "nom": "z ou w (indice éventuel)",
        "a": "partie réelle (entier, |a| ≤ 50)",
        "b": "partie imaginaire (entier, |b| ≤ 50)",
        "presentation": "« point », « conjugue », « module » ou « argument » : choisi par le serveur d'après la question confirmée",
        "module": "√(a² + b²) = coef·√rad (SymPy et entiers)",
        "argument": "exact (multiple rationnel de π) ou approché, calculé par SymPy",
    },
    conditions=(
        "z est défini sans ambiguïté par `z = a + bi` avec a et b entiers dans l'énoncé confirmé",
        "la question demande de représenter z, son conjugué, son module ou son argument",
        "plusieurs nombres définis : la question en nomme un seul",
    ),
    proposer=proposer,
    valider=valider,
    projeter=projeter,
    revelatrice=revelatrice,
    controler=controler,
))
