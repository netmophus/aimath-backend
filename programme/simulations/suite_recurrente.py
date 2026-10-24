"""
Modèle « suite_recurrente » (étape 9.3) : premiers termes d'une suite définie par une récurrence AFFINE
`u_{n+1} = a·u_n + b` et premier terme `u_0` (ou `u_1`), et diagramme en escalier.

Périmètre volontairement étroit — aucune généralisation abusive :
- seules les récurrences affines à coefficients rationnels sont prises en charge (lues avec l'analyseur à vocabulaire
  fermé du projet, jamais `eval`) ; toute autre récurrence (terme en n, produit u_n·u_n, deux suites, relation
  implicite…) supprime la simulation ;
- le comportement n'est affiché que dans le cadre de ce théorème pour les suites affines : pour |a| < 1, la suite
  converge vers L = b / (1 − a), quel que soit le premier terme. Pour |a| ≥ 1 aucune limite n'est annoncée ;
- le nombre de termes affichés est borné (au plus 10) et s'arrête si les nombres deviennent trop grands.
Les termes sont calculés en arithmétique exacte (Fraction) ET avec SymPy, et revalidés par le front.
Présentations (choisies par le SERVEUR d'après la question confirmée) : `termes` et `escalier`.
"""

from __future__ import annotations

import logging
import re
from fractions import Fraction

import sympy as sp

from ..correction.expressions import ExpressionInvalide, analyser
from ._maths import fraction_en_texte, lire_fraction, minuscules_sans_accents, texte_a_plat
from .catalogue import ContexteSimulation, ModeleSimulation, ParametresInvalides, Proposition, enregistrer

logger = logging.getLogger(__name__)

ID = "suite_recurrente"
VERSION = 1
NB_TERMES_MAX = 10
NB_TERMES_MIN = 3
BORNE_COEFFICIENT = 100  # |a|, |b|, |premier terme| et dénominateurs
BORNE_TERME = 10**6  # on arrête la liste si un terme sort de cette fenêtre lisible
BORNE_DENOMINATEUR = 10**9

TERMES, ESCALIER = "termes", "escalier"
PRESENTATIONS = (TERMES, ESCALIER)

_NOMBRE = r"[-+]?\s*(?:\d{1,6}(?:[.,]\d{1,2})?(?:\s*/\s*\d{1,4})?|\(\d{1,6}\)\s*/\s*\(\d{1,4}\))"
_RE_INITIAL = re.compile(rf"(?<![A-Za-z])([uvw])_\{{?([01])\}}?\s*=\s*({_NOMBRE})(?![\w^*(]|[.,]\d)")
_RE_RECURRENCE = re.compile(
    r"(?<![A-Za-z])([uvw])_\{\s*n\s*\+\s*1\s*\}\s*=\s*"
    r"(.+?)(?=\s*(?:[;]|,\s|\.\s|\.$|$|\bpour\b|\bet\b|\bavec\b|\bsi\b|\bou\b|\bsachant\b))"
)


def _fraction_ecrite(ecriture: str) -> Fraction | None:
    s = re.sub(r"\s+", "", ecriture).replace(",", ".")
    s = re.sub(r"^([-+]?)\((\d+)\)/\((\d+)\)$", r"\1\2/\3", s)
    m = re.fullmatch(r"([-+]?)(\d+(?:\.\d+)?)(?:/(\d+))?", s)
    if not m:
        return None
    valeur = Fraction(m.group(2))
    if m.group(3):
        if int(m.group(3)) == 0:
            return None
        valeur /= int(m.group(3))
    return -valeur if m.group(1) == "-" else valeur


def _dans_les_bornes(f: Fraction) -> bool:
    return abs(f) <= BORNE_COEFFICIENT and f.denominator <= BORNE_COEFFICIENT


def extraire_suite(sources: tuple[str, ...]) -> tuple[dict, str] | None:
    """({nom, n0, u0, a, b}, '') si l'énoncé définit UNE suite affine sans ambiguïté, sinon None."""
    initiaux: dict[tuple[str, int], set[Fraction]] = {}
    recurrences: dict[str, set[tuple[Fraction, Fraction]]] = {}
    for source in sources:
        t = texte_a_plat(source)
        for nom, indice, ecriture in _RE_INITIAL.findall(t):
            valeur = _fraction_ecrite(ecriture)
            if valeur is None:
                return None
            initiaux.setdefault((nom, int(indice)), set()).add(valeur)
        for nom, droite in _RE_RECURRENCE.findall(t):
            lue = _lire_affine(nom, droite)
            if lue is None:
                return None  # une récurrence non prise en charge rend tout l'énoncé ambigu
            recurrences.setdefault(nom, set()).add(lue)
    if len(recurrences) != 1:
        return None
    nom = next(iter(recurrences))
    couples = recurrences[nom]
    if len(couples) != 1:
        return None
    a, b = next(iter(couples))
    candidats = {(n, i): v for (n, i), v in initiaux.items() if n == nom}
    if len(candidats) != 1 or any(len(v) != 1 for v in candidats.values()):
        return None
    (_, n0), valeurs = next(iter(candidats.items()))
    u0 = next(iter(valeurs))
    if not (_dans_les_bornes(a) and _dans_les_bornes(b) and _dans_les_bornes(u0)) or a == 0:
        return None
    return {"nom": nom, "n0": n0, "u0": u0, "a": a, "b": b}, ""


def _lire_affine(nom: str, droite: str) -> tuple[Fraction, Fraction] | None:
    """`a·y + b` lu avec l'analyseur fermé (u_n → y) ; None si la récurrence n'est pas affine à coefficients rationnels."""
    expression = re.sub(rf"(?<![A-Za-z]){nom}_\{{?\s*n\s*\}}?", "y", droite)
    expression = re.sub(r"[{}]", "", expression).strip().rstrip(".")
    if re.search(r"[A-Za-z]", expression.replace("y", "")) or "y" not in expression:
        return None
    try:
        expr = analyser(expression, ("y",))
        y = sp.Symbol("y", real=True)
        poly = sp.Poly(expr, y)
    except (ExpressionInvalide, sp.PolynomialError, TypeError, ValueError):
        return None
    if poly.degree() != 1:
        return None
    a, b = poly.coeff_monomial(y), poly.coeff_monomial(1)
    if not (a.is_Rational and b.is_Rational):
        return None
    return Fraction(int(a.p), int(a.q)), Fraction(int(b.p), int(b.q))


def termes_exacts(u0: Fraction, a: Fraction, b: Fraction) -> list[Fraction]:
    """Au plus NB_TERMES_MAX termes, exacts ; la liste s'arrête avant un terme hors de la fenêtre lisible."""
    termes = [u0]
    while len(termes) < NB_TERMES_MAX:
        suivant = a * termes[-1] + b
        if abs(suivant) > BORNE_TERME or suivant.denominator > BORNE_DENOMINATEUR:
            break
        termes.append(suivant)
    return termes


def _termes_sympy(u0: Fraction, a: Fraction, b: Fraction, n: int) -> list[Fraction] | None:
    """Même calcul avec SymPy (rationnels) : les deux doivent concorder."""
    u, ra, rb = sp.Rational(u0.numerator, u0.denominator), sp.Rational(a.numerator, a.denominator), sp.Rational(b.numerator, b.denominator)
    sortie = []
    for _ in range(n):
        sortie.append(Fraction(int(u.p), int(u.q)))
        u = ra * u + rb
    return sortie


def limite_theorique(a: Fraction, b: Fraction) -> Fraction | None:
    """Limite d'une suite affine u_{n+1} = a·u_n + b : b / (1 − a) quand |a| < 1 (théorème), sinon aucune limite annoncée."""
    return b / (1 - a) if abs(a) < 1 else None


def _lecture_de_la_question(texte: str, nom: str) -> str | None:
    t = minuscules_sans_accents(texte)
    t_plat = re.sub(r"[{}]", "", t)
    if not re.search(rf"\bsuite\b|\bpremiers\s+termes\b|(?<![a-z]){nom}\s*(?:_|\()|\({nom}\s*_", t_plat):
        return None  # la question ne parle pas de cette suite
    if re.search(r"escalier|toile\s+d.araignee|diagramme|cobweb", t):
        return ESCALIER
    if re.search(r"comportement|monoton|croissan|decroissan|variation|limite|converg|diverg|tend\s+vers|etudier", t):
        return ESCALIER
    if re.search(r"graphiquement|represent|trace|premiers\s+termes|nuage|calculer|determiner|donner|termes", t):
        return TERMES
    return None


def valider(parametres: object) -> dict:
    """Refuse tout paramètre hors cadre ; renvoie la forme normalisée, termes et limite RECALCULÉS (jamais fiés).

    Forme COMPLÈTE (correction) : 3 à 10 termes, `limite` (b/(1−a) si |a| < 1, sinon null) et `demande`. Forme RÉDUITE
    (divulgation progressive du Professeur particulier, voir `projeter`) : présentation `termes`, SANS clé `limite` (la
    limite est la réponse de l'étude du comportement) ; avec `demande` = d, seulement les d + 1 premiers termes."""
    if not isinstance(parametres, dict) or not {"nom", "n0", "a", "b", "termes", "demande", "presentation"} <= set(parametres):
        raise ParametresInvalides("Paramètres inattendus.")
    reduite = "limite" not in parametres
    if set(parametres) != {"nom", "n0", "a", "b", "termes", "demande", "presentation"} | (set() if reduite else {"limite"}):
        raise ParametresInvalides("Paramètres inattendus.")
    if parametres["presentation"] not in PRESENTATIONS:
        raise ParametresInvalides("Présentation inconnue.")
    if parametres["nom"] not in ("u", "v", "w") or parametres["n0"] not in (0, 1) or isinstance(parametres["n0"], bool):
        raise ParametresInvalides("Suite mal nommée.")
    demande = parametres["demande"]
    if demande is not None and (isinstance(demande, bool) or not isinstance(demande, int) or not 1 <= demande <= NB_TERMES_MAX - 1 or parametres["presentation"] != TERMES):
        raise ParametresInvalides("Demande invalide.")
    if reduite and parametres["presentation"] != TERMES:
        raise ParametresInvalides("Forme réduite réservée aux termes.")
    partielle = reduite and demande is not None  # seulement les d + 1 premiers termes
    a, b = lire_fraction(parametres["a"], BORNE_COEFFICIENT), lire_fraction(parametres["b"], BORNE_COEFFICIENT)
    termes = parametres["termes"]
    minimum = 2 if partielle else NB_TERMES_MIN
    if not isinstance(termes, list) or not minimum <= len(termes) <= NB_TERMES_MAX or (partielle and len(termes) != demande + 1):
        raise ParametresInvalides("Nombre de termes hors bornes.")
    u0 = lire_fraction(termes[0], BORNE_COEFFICIENT)
    if a == 0 or not (_dans_les_bornes(a) and _dans_les_bornes(b) and _dans_les_bornes(u0)):
        raise ParametresInvalides("Coefficients hors bornes.")
    attendus = termes_exacts(u0, a, b)
    if [lire_fraction(t, BORNE_DENOMINATEUR * BORNE_TERME) for t in termes] != attendus[: len(termes)] or (not partielle and len(termes) != len(attendus)):
        raise ParametresInvalides("Termes incohérents avec la récurrence.")
    if _termes_sympy(u0, a, b, len(termes)) != attendus[: len(termes)]:
        raise ParametresInvalides("Calculs SymPy et exact divergents.")
    sortie = {
        "nom": parametres["nom"], "n0": parametres["n0"], "a": fraction_en_texte(a), "b": fraction_en_texte(b),
        "termes": [fraction_en_texte(t) for t in attendus[: len(termes)]], "demande": demande, "presentation": parametres["presentation"],
    }
    if not reduite:
        limite = limite_theorique(a, b)
        if parametres["limite"] != (None if limite is None else fraction_en_texte(limite)):
            raise ParametresInvalides("Limite incohérente.")
        sortie["limite"] = parametres["limite"]
    return sortie


def proposer(contexte: ContexteSimulation) -> Proposition | None:
    if contexte.matiere != "mathematiques":
        return None
    lue = extraire_suite(contexte.sources)
    if lue is None:
        return None
    suite = lue[0]
    presentation = _lecture_de_la_question(contexte.question_texte, suite["nom"])
    if presentation is None:
        return None
    termes = termes_exacts(suite["u0"], suite["a"], suite["b"])
    if len(termes) < NB_TERMES_MIN:
        return None
    if _termes_sympy(suite["u0"], suite["a"], suite["b"], len(termes)) != termes:
        logger.error("simulation suite_recurrente : calculs SymPy et exact divergents")
        return None
    limite = limite_theorique(suite["a"], suite["b"])
    parametres = valider({
        "nom": suite["nom"], "n0": suite["n0"], "a": fraction_en_texte(suite["a"]), "b": fraction_en_texte(suite["b"]),
        "termes": [fraction_en_texte(t) for t in termes], "limite": None if limite is None else fraction_en_texte(limite),
        "demande": _demande_bornee(contexte.question_texte, suite["nom"], suite["n0"], len(termes)) if presentation == TERMES else None,
        "presentation": presentation,
    })
    titre = (f"Premiers termes de la suite ({suite['nom']}ₙ)" if presentation == TERMES else f"Diagramme en escalier de la suite ({suite['nom']}ₙ)")
    return Proposition(
        parametres=parametres, titre=titre,
        verification={"methodes": ["SymPy", "Calcul exact"], "concordance_correction": "non_applicable"},
    )


_NOMBRES_EN_LETTRES = {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10}


def _termes_demandes(question: str, nom: str, n0: int) -> int | None:
    """Pour une question de CALCUL de termes (« Calculer u₁ et u₂ »), nombre d de termes à calculer après le premier (le
    Professeur ne montrera que les d + 1 premiers) ; None pour une représentation graphique ou toute autre question."""
    t = minuscules_sans_accents(question)
    if re.search(r"represent|trac|graph|nuage|escalier|diagramme|dessin|comportement|limite|converg", t) or not re.search(r"calcul|determin|donner|trouver|ecrire|expliciter", t):
        return None
    plat = texte_a_plat(question)
    indices = [int(i) for i in re.findall(rf"(?<![A-Za-z]){nom}_\{{?(\d{{1,2}})\}}?", plat)]
    if indices:
        d = max(indices) - n0
    else:
        m = re.search(r"(\d{1,2}|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s+premiers\s+termes", t)
        d = (int(m.group(1)) if m.group(1).isdigit() else _NOMBRES_EN_LETTRES[m.group(1)]) - 1 if m else 2
    return min(max(d, 1), NB_TERMES_MAX - 1)


def _demande_bornee(question: str, nom: str, n0: int, nb_termes: int) -> int | None:
    d = _termes_demandes(question, nom, n0)
    return None if d is None else min(d, nb_termes - 1)


def projeter(parametres: dict) -> dict:
    """Projection de divulgation progressive (Professeur particulier, étape 9.4). Les présentations `termes` ne montrent
    JAMAIS la limite (réponse de l'étude du comportement) ; une question de CALCUL de termes ne reçoit de plus que les
    d + 1 premiers termes (les suivants donneraient la tendance). `escalier` est envoyé entier : il est la réponse de
    sa question et reste retenu par `revelatrice` tant que celle-ci n'est pas prouvée."""
    complets = valider(parametres)
    if complets["presentation"] != TERMES:
        return complets
    sortie = {k: v for k, v in complets.items() if k != "limite"}
    if complets["demande"] is not None:
        sortie["termes"] = complets["termes"][: complets["demande"] + 1]
    return sortie


def revelatrice(parametres: dict) -> bool:
    """Toutes les présentations montrent un résultat calculé : termes (réponse du calcul), limite et escalier (réponse de
    l'étude du comportement). Aucune n'est envoyée sur le seul avis de l'IA."""
    return True


_RE_AFFECTATION = r"(?<![A-Za-z])({nom})_\{{?(\d{{1,2}})\}}?\s*="
_RE_COUPURE = re.compile(r"\s(?:et|puis|donc|soit|ou|car|alors)\s|[;,]\s|\.\s|\.$")
_RE_LIMITE = re.compile(
    r"(?:\bvers\s+|\blimite\s*(?:est|=|:|egale?|vaut)?\s*|\blim\w*(?:_\{[^}]*\})?\s*(?:u_\{?n\}?)?\s*=\s*|(?<![A-Za-z])L\s*=\s*)"
    r"(-?\s*(?:\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?|\(\s*-?\d+\s*\)\s*/\s*\(\s*\d+\s*\)))"
)


def _valeur_rationnelle(ecriture: str) -> Fraction | None:
    """Valeur exacte d'un calcul purement numérique (« 5,5 », « 1/2*5+3 », « (11)/(2) »), sinon None."""
    texte = ecriture.strip().rstrip(".").strip()
    if not texte or re.search(r"[A-Za-z]", texte):
        return None
    try:
        valeur = analyser(texte, ())
    except (ExpressionInvalide, TypeError, ValueError, RecursionError):
        return None
    return Fraction(int(valeur.p), int(valeur.q)) if getattr(valeur, "is_Rational", False) else None


def _termes_ecrits(texte: str, nom: str) -> dict[int, Fraction]:
    """{indice: valeur finale} des affectations « u_k = … » PUREMENT numériques de la réponse. Un « u_1 − u_0 = … »
    (précédé d'un opérateur) n'est pas une affectation du terme."""
    plat = texte_a_plat(texte)
    sortie: dict[int, Fraction] = {}
    entetes = list(re.finditer(_RE_AFFECTATION.format(nom=re.escape(nom)), plat))
    for i, m in enumerate(entetes):
        avant = plat[: m.start()].rstrip()
        if avant and avant[-1] in "-+*/(^":
            continue
        fin = entetes[i + 1].start() if i + 1 < len(entetes) else len(plat)
        reste = _RE_COUPURE.split(re.split(r"[;\n]", plat[m.end():fin])[0], maxsplit=1)[0]
        valeurs = [v for v in (_valeur_rationnelle(seg) for seg in reste.split("=")) if v is not None]
        if valeurs:
            sortie[int(m.group(2))] = valeurs[-1]
    return sortie


def controler(parametres: dict, texte: str) -> str | None:
    """Contrôle déterministe INDÉPENDANT d'une réponse d'élève (jamais l'avis de l'IA) :
    - `termes` : les valeurs écrites pour u_k sont comparées aux termes recalculés (« contredit » si l'une diffère ;
      « confirme » si TOUS les termes demandés sont écrits et justes) ;
    - `escalier` : la valeur écrite après « converge vers / limite » est comparée à b/(1 − a) (si la suite en a une) ;
    - None : rien d'exploitable."""
    try:
        valides = valider(parametres)
    except ParametresInvalides:
        return None
    nom, n0 = valides["nom"], valides["n0"]
    termes = [lire_fraction(t, BORNE_DENOMINATEUR * BORNE_TERME) for t in valides["termes"]]
    if valides["presentation"] == ESCALIER:
        if valides.get("limite") is None:
            return None
        trouvees = [_valeur_rationnelle(m.group(1)) for m in _RE_LIMITE.finditer(texte_a_plat(texte))]
        trouvees = [v for v in trouvees if v is not None]
        if not trouvees:
            return None
        return "confirme" if trouvees[-1] == lire_fraction(valides["limite"]) else "contredit"
    ecrits = _termes_ecrits(texte, nom)
    connus = {k: v for k, v in ecrits.items() if 0 <= k - n0 < len(termes)}
    if any(v != termes[k - n0] for k, v in connus.items()):
        return "contredit"
    demande = valides["demande"]
    if demande is not None and all(k in connus for k in range(n0 + 1, n0 + demande + 1)):
        return "confirme"
    return None


MODELE = enregistrer(ModeleSimulation(
    id=ID,
    version=VERSION,
    titre="Suite récurrente affine : termes et diagramme en escalier",
    matieres=frozenset({"mathematiques"}),
    notions=("suites numériques", "suites récurrentes", "convergence", "diagramme en escalier"),
    parametres={
        "nom": "u, v ou w ; n0 : indice du premier terme (0 ou 1)",
        "a": "coefficient (fraction exacte, |a| ≤ 100)",
        "b": "constante (fraction exacte, |b| ≤ 100)",
        "termes": "3 à 10 premiers termes exacts (recalculés)",
        "limite": "b/(1−a) si |a| < 1 (suite affine), sinon null",
        "presentation": "« termes » ou « escalier » : choisi par le serveur d'après la question confirmée",
    },
    conditions=(
        "une seule suite définie par u_{n+1} = a·u_n + b (affine, coefficients rationnels) et son premier terme u_0 ou u_1",
        "la question parle de cette suite (calcul des premiers termes, représentation graphique, comportement)",
        "au moins 3 termes affichables sans dépasser les bornes",
    ),
    proposer=proposer,
    valider=valider,
    projeter=projeter,
    revelatrice=revelatrice,
    controler=controler,
))
