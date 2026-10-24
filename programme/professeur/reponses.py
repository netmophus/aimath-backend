"""
Vérification MATHÉMATIQUE de la réponse d'un élève, sans IA et sans eval.

La réponse (texte libre : « f'(x) = 3x² + 3 », « x = 2 ou x = 3 », LaTeX
simple) est lue par programme.correction.expressions.analyser — un analyseur à
vocabulaire fermé, jamais eval/exec/sympify — puis comparée par SymPy à la
réponse attendue de l'étape. Deux expressions équivalentes (3(x²−1) et
3x²−3) sont toutes deux acceptées.

Le verdict est la SEULE source de vérité du « juste/faux » : l'IA rédige le
retour pédagogique, elle ne décide jamais si la réponse est correcte.

  correct        équivalent à la réponse attendue (référence elle-même vérifiée)
  incorrect      lue correctement mais différente (diagnostic factuel joint)
  non_verifiable étape sans calcul vérifiable, ou réponse non lisible
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp

from ..correction.expressions import ExpressionInvalide, analyser
from ..correction.verification import _comparer_ensembles, _egaux, _texte

CORRECT, INCORRECT, NON_VERIFIABLE = "correct", "incorrect", "non_verifiable"

VARIABLES = ("x", "y", "z", "t", "u", "a", "b", "c", "k", "m", "n")
LONGUEUR_MAX_REPONSE = 1500

_SANS_SOLUTION = re.compile(r"^(?:aucune?|pas)\s+(?:de\s+)?solution|^ensemble\s+vide|^∅|^s\s*=\s*(?:∅|\\emptyset|\{\s*\})\s*$", re.I)


@dataclass
class Verdict:
    statut: str
    detail: str = ""
    # Ce que le système a compris de la réponse (texte), pour l'afficher et l'envoyer au retour pédagogique.
    lecture: str = ""
    # Constat factuel et SANS la valeur attendue (« diffère par une constante »…).
    diagnostic: str = ""
    # « calcul » quand l'écart ressemble à une étourderie (signe, constante), sinon vide.
    erreur_probable: str = ""
    # Ce qui est correct dans la réponse (« le terme en $x^2$ »), jamais la valeur attendue.
    acquis: list = field(default_factory=list)
    # Ce qui est à revoir : [{"element": "le terme constant", "nature": "signe"|"coefficient"|"manquant"|"en_trop"}].
    a_revoir: list = field(default_factory=list)


def nettoyer_saisie(texte: str) -> str:
    """LaTeX simple et variantes typographiques → notation lue par `analyser`."""
    t = texte.replace("$", " ")
    for ancien, nouveau in (
        ("\\left", ""), ("\\right", ""), ("\\cdot", "*"), ("\\times", "*"), ("\\pi", "pi"), ("\\infty", "oo"),
        ("\\,", " "), ("\\;", " "), ("\\!", ""), ("\\dfrac", "\\frac"), ("\\leq", "<="), ("\\geq", ">="),
        ("\\Rightarrow", "="), ("\\iff", "="), ("⇔", "="), ("⟺", "="), ("⇒", "="), ("\\ln", "ln"), ("\\exp", "exp"),
        ("\\sin", "sin"), ("\\cos", "cos"), ("\\tan", "tan"), ("\\{", "{"), ("\\}", "}"),
    ):
        t = t.replace(ancien, nouveau)
    for _ in range(6):  # fractions et racines imbriquées : on résout de l'intérieur
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"((\1)/(\2))", t)
        t = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", t)
        t = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", t)
    t = re.sub(r"\\text\{([^{}]*)\}", r" \1 ", t)
    return t.strip().rstrip(".").strip()


def _lire_expression(texte: str):
    brut = nettoyer_saisie(texte)
    membres = [m.strip() for m in re.split(r"=", brut) if m.strip()]
    if not membres:
        raise ExpressionInvalide("réponse vide")
    return analyser(membres[-1], VARIABLES), membres[-1]


def _decouper_ensemble(texte: str) -> list[str]:
    t = nettoyer_saisie(texte)
    t = re.sub(r"^\s*S\s*=\s*", "", t, flags=re.I)
    t = t.replace("{", " ").replace("}", " ")
    pieces = re.split(r"\s*(?:;|\bou\b|\bet\b|,\s|\bor\b|\band\b)\s*", t)
    sortie = []
    for p in pieces:
        p = re.sub(r"^\s*[A-Za-z]\s*=\s*", "", p.strip())
        if p:
            sortie.append(p)
    return sortie


def _nom_terme(degre: int, variable: sp.Symbol) -> str:
    if degre == 0:
        return "le terme constant"
    if degre == 1:
        return f"le terme en ${variable}$"
    return f"le terme en ${variable}^{degre}$"


def comparer_termes(etudiant: sp.Expr, attendu: sp.Expr) -> tuple[list[str], list[dict]]:
    """Comparaison terme à terme de deux polynômes en une variable : ce qui est juste et ce qui ne
    l'est pas, SANS révéler le coefficient attendu. Hors polynômes (ou plusieurs variables) : ([], [])."""
    try:
        variables = (etudiant.free_symbols | attendu.free_symbols)
        if len(variables) > 1 or not (etudiant.is_polynomial() and attendu.is_polynomial()):
            return [], []
        variable = next(iter(variables), sp.Symbol("x"))
        e = sp.Poly(sp.expand(etudiant), variable)
        a = sp.Poly(sp.expand(attendu), variable)
        acquis, a_revoir = [], []
        for degre in sorted(set(range(e.degree() + 1)) | set(range(a.degree() + 1)), reverse=True):
            ce, ca = e.coeff_monomial(variable ** degre), a.coeff_monomial(variable ** degre)
            nom = _nom_terme(degre, variable)
            if sp.simplify(ce - ca) == 0:
                if ca != 0:
                    acquis.append(nom)
            elif ce == 0:
                a_revoir.append({"element": nom, "nature": "manquant"})
            elif ca == 0:
                a_revoir.append({"element": nom, "nature": "en_trop"})
            elif sp.simplify(ce + ca) == 0:
                a_revoir.append({"element": nom, "nature": "signe"})
            else:
                a_revoir.append({"element": nom, "nature": "coefficient"})
        return acquis, a_revoir
    except (TypeError, ValueError, ZeroDivisionError, NotImplementedError, sp.PolynomialError, StopIteration):
        return [], []


_PHRASE_NATURE = {
    "signe": "a le mauvais signe",
    "coefficient": "n'a pas le bon coefficient",
    "manquant": "est absent de ta réponse",
    "en_trop": "ne devrait pas apparaître",
}


def _phrase_termes(acquis: list[str], a_revoir: list[dict]) -> str:
    morceaux = []
    if acquis:
        morceaux.append(("Sont corrects : " if len(acquis) > 1 else "Est correct : ") + " ; ".join(acquis) + ".")
    for item in a_revoir:
        morceaux.append(f"{item['element'][0].upper()}{item['element'][1:]} {_PHRASE_NATURE[item['nature']]}.")
    return " ".join(morceaux)


def _diagnostic_expression(etudiant: sp.Expr, attendu: sp.Expr) -> tuple[str, str]:
    try:
        ecart = sp.simplify(etudiant - attendu)
        if ecart.is_number and ecart != 0:
            return "Ta réponse ne diffère de la bonne que par une constante (terme constant).", "calcul"
        if sp.simplify(etudiant + attendu) == 0:
            return "Ta réponse est l'opposée de la bonne (problème de signe).", "calcul"
        if attendu != 0:
            quotient = sp.simplify(etudiant / attendu)
            if quotient.is_number and quotient not in (0, 1):
                return "Ta réponse est proportionnelle à la bonne (un facteur est faux).", "calcul"
        d_e, d_a = sp.degree(sp.expand(etudiant)) if etudiant.is_polynomial() else None, sp.degree(sp.expand(attendu)) if attendu.is_polynomial() else None
        if d_e is not None and d_a is not None and d_e != d_a:
            return "Le degré de ta réponse n'est pas celui attendu.", ""
    except (TypeError, ValueError, ZeroDivisionError, NotImplementedError, sp.PolynomialError):
        pass
    return "Ta réponse n'est pas équivalente à celle attendue.", ""


def _verifier_expression(attendu: dict, texte: str) -> Verdict:
    try:
        etudiant, lecture = _lire_expression(texte)
        reference = analyser(attendu["valeur"], VARIABLES)
    except ExpressionInvalide as exc:
        return Verdict(NON_VERIFIABLE, f"Réponse non lisible comme expression mathématique ({exc}).")
    lecture = _texte(etudiant)
    if attendu.get("depart"):  # factorisation, développement : recopier l'expression de départ ne suffit pas
        try:
            depart = analyser(attendu["depart"], VARIABLES)
            if _egaux(etudiant, depart) and sp.srepr(etudiant) == sp.srepr(depart):
                return Verdict(INCORRECT, "Expression équivalente mais non transformée.", lecture,
                               "Tu as recopié l'expression de départ sans la transformer.", "")
        except ExpressionInvalide:
            pass
    try:
        if _egaux(etudiant, reference):
            return Verdict(CORRECT, "Expression équivalente à la réponse attendue (calcul formel).", lecture)
    except (TypeError, ValueError, ZeroDivisionError, NotImplementedError):
        return Verdict(NON_VERIFIABLE, "La comparaison automatique n'a pas pu aboutir.", lecture)
    diagnostic, erreur = _diagnostic_expression(etudiant, reference)
    acquis, a_revoir = comparer_termes(etudiant, reference)
    if a_revoir:  # constat précis, terme par terme (aucune valeur attendue révélée)
        diagnostic = _phrase_termes(acquis, a_revoir)
        # « calcul » seulement si l'écart est un simple signe ; un coefficient faux peut venir d'une règle mal appliquée.
        erreur = "calcul" if all(i["nature"] == "signe" for i in a_revoir) else ""
    return Verdict(INCORRECT, "Expression différente de la réponse attendue.", lecture, diagnostic, erreur, acquis, a_revoir)


def _verifier_ensemble(attendu: dict, texte: str) -> Verdict:
    brut = nettoyer_saisie(texte)
    try:
        reference = [analyser(v, VARIABLES) for v in attendu["valeurs"]]
        if _SANS_SOLUTION.search(brut):
            etudiant: list = []
        else:
            etudiant = [analyser(p, VARIABLES) for p in _decouper_ensemble(texte)]
            if not etudiant:
                raise ExpressionInvalide("aucune valeur")
    except ExpressionInvalide as exc:
        return Verdict(NON_VERIFIABLE, f"Réponse non lisible comme liste de solutions ({exc}).")
    lecture = ", ".join(_texte(v) for v in etudiant) or "aucune solution"
    if _comparer_ensembles(etudiant, reference):
        return Verdict(CORRECT, "Ensemble de solutions identique à celui attendu (calcul formel).", lecture)
    manquantes = [r for r in reference if not any(_egaux(r, e) for e in etudiant)]
    en_trop = [e for e in etudiant if not any(_egaux(r, e) for r in reference)]
    justes = [e for e in etudiant if any(_egaux(r, e) for r in reference)]
    acquis = [f"${_texte(e)}$ est bien une solution" for e in justes]
    morceaux = []
    if manquantes:
        morceaux.append(f"il manque {len(manquantes)} solution{'s' if len(manquantes) > 1 else ''}")
    if en_trop:
        morceaux.append(f"{len(en_trop)} valeurs proposées ne sont pas solutions" if len(en_trop) > 1 else "une valeur proposée n'est pas solution")
    return Verdict(INCORRECT, "Ensemble de solutions différent.", lecture, "Dans ta réponse, " + " et ".join(morceaux) + ".", "", acquis,
                   ([{"element": "l'ensemble des solutions", "nature": "manquant"}] if manquantes else []) +
                   ([{"element": "une des valeurs proposées", "nature": "en_trop"}] if en_trop else []))


def verifier_reponse(attendu: dict | None, texte: str) -> Verdict:
    """`attendu` : None (étape sans calcul vérifiable) ou {"type": "expression"|"ensemble", ...}."""
    if not attendu:
        return Verdict(NON_VERIFIABLE, "Étape sans calcul vérifiable automatiquement.")
    if len(texte) > LONGUEUR_MAX_REPONSE:
        return Verdict(NON_VERIFIABLE, "Réponse trop longue.")
    try:
        if attendu["type"] == "ensemble":
            return _verifier_ensemble(attendu, texte)
        return _verifier_expression(attendu, texte)
    except (RecursionError, sp.SympifyError, TypeError, ValueError, ZeroDivisionError, NotImplementedError, AttributeError):
        return Verdict(NON_VERIFIABLE, "La vérification automatique n'a pas pu aboutir.")
