"""
Contrôle indépendant, par SymPy, des affirmations calculables d'une correction.

Chaque « affirmation » (type + champs texte) est relue par expressions.analyser
(aucune évaluation de code), recalculée par SymPy, puis comparée à ce que la
correction annonce. Résultat d'un contrôle : un VerdictMethode.

  ok            le calcul indépendant confirme l'affirmation ;
  contradiction le calcul indépendant donne autre chose (detail l'explique) ;
  indisponible  type non pris en charge, expression illisible ou calcul
                trop long : on ne dit RIEN de vrai ni de faux.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import sympy as sp

from .expressions import ExpressionInvalide, analyser, symbole

OK, CONTRADICTION, INDISPONIBLE = "ok", "contradiction", "indisponible"

TYPES_SYMPY = ("equation", "derivee", "egalite", "substitution", "extrema", "variations")


@dataclass
class VerdictMethode:
    statut: str
    detail: str = ""
    # Valeurs trouvées par la méthode, en texte lisible (pour l'affichage et le croisement).
    trouve: list[str] = field(default_factory=list)


def _egaux(a: sp.Expr, b: sp.Expr) -> bool:
    """a == b ? Exact (simplify) puis, à défaut, par échantillonnage numérique prudent."""
    difference = sp.simplify(a - b)
    if difference == 0:
        return True
    if difference.is_number:
        return bool(sp.N(difference, 30).equals(0)) if difference.is_real is not False else False
    libres = sorted(difference.free_symbols, key=lambda s: s.name)
    hasard = random.Random(1234)
    accord = 0
    for _ in range(12):
        sub = {s: sp.Rational(hasard.randint(-40, 40), hasard.randint(1, 9)) for s in libres}
        try:
            valeur = sp.N((a - b).subs(sub), 25)
        except (ZeroDivisionError, TypeError, ValueError):
            continue
        if not valeur.is_number or valeur.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
            continue
        if abs(valeur) > sp.Float("1e-12"):
            return False
        accord += 1
    return accord >= 6


def _texte(expr) -> str:
    return sp.sstr(expr).replace("**", "^")


def _liste_texte(valeurs) -> str:
    return ", ".join(_texte(v) for v in valeurs) if valeurs else "aucune"


def _comparer_ensembles(annonces: list[sp.Expr], calcules: list[sp.Expr]) -> bool:
    restants = list(calcules)
    for a in annonces:
        for c in restants:
            if _egaux(a, c):
                restants.remove(c)
                break
        else:
            return False
    return not restants


def _solutions_reelles(gauche: sp.Expr, droite: sp.Expr, x: sp.Symbol):
    """Liste des solutions réelles, ou None si l'ensemble n'est pas fini/calculable."""
    ensemble = sp.solveset(sp.Eq(gauche, droite), x, domain=sp.S.Reals)
    if ensemble == sp.S.EmptySet:
        return []
    if isinstance(ensemble, sp.FiniteSet):
        return sorted(list(ensemble), key=lambda v: float(sp.N(v)))
    return None


def _annonces(champ) -> list[str]:
    if isinstance(champ, str):
        champ = [champ]
    return [s for s in (champ or []) if isinstance(s, str)]


def _sans_solution(texte: str) -> bool:
    return texte.strip().lower() in {"aucune", "aucune solution", "vide", "ensemble vide", "∅", "{}"}


def _verifier_equation(a: dict) -> VerdictMethode:
    x = symbole(a.get("variable") or "x")
    gauche = analyser(a.get("gauche"), (x.name,))
    droite = analyser(a.get("droite") or "0", (x.name,))
    calculees = _solutions_reelles(gauche, droite, x)
    if calculees is None:
        return VerdictMethode(INDISPONIBLE, "L'ensemble des solutions n'est pas un ensemble fini calculable ici.")
    brutes = _annonces(a.get("solutions"))
    annoncees = [] if all(_sans_solution(s) for s in brutes) else [analyser(s, (x.name,)) for s in brutes]
    trouve = [_texte(v) for v in calculees]
    if _comparer_ensembles(annoncees, calculees):
        return VerdictMethode(OK, f"Solutions réelles recalculées : {_liste_texte(calculees)}.", trouve)
    return VerdictMethode(
        CONTRADICTION,
        f"SymPy trouve comme solutions réelles : {_liste_texte(calculees)} ; la correction annonce : "
        f"{_liste_texte(annoncees)}.",
        trouve,
    )


def _verifier_derivee(a: dict) -> VerdictMethode:
    x = symbole(a.get("variable") or "x")
    f = analyser(a.get("fonction"), (x.name,))
    annoncee = analyser(a.get("derivee"), (x.name,))
    calculee = sp.diff(f, x)
    if _egaux(calculee, annoncee):
        return VerdictMethode(OK, f"Dérivée recalculée : {_texte(sp.simplify(calculee))}.", [_texte(sp.simplify(calculee))])
    return VerdictMethode(
        CONTRADICTION,
        f"SymPy trouve f'({x.name}) = {_texte(sp.simplify(calculee))} ; la correction annonce {_texte(annoncee)}.",
        [_texte(sp.simplify(calculee))],
    )


def _verifier_egalite(a: dict) -> VerdictMethode:
    variables = tuple("xyztabcmnkuvw")
    gauche = analyser(a.get("gauche"), variables)
    droite = analyser(a.get("droite"), variables)
    if _egaux(gauche, droite):
        return VerdictMethode(OK, "Égalité confirmée par calcul formel.")
    return VerdictMethode(
        CONTRADICTION,
        f"Les deux membres ne sont pas égaux : {_texte(sp.simplify(gauche))} ≠ {_texte(sp.simplify(droite))}.",
    )


def _verifier_substitution(a: dict) -> VerdictMethode:
    x = symbole(a.get("variable") or "x")
    expression = analyser(a.get("expression"), (x.name,))
    valeur = analyser(a.get("valeur"), (x.name,))
    annonce = analyser(a.get("resultat"), (x.name,))
    calcule = sp.simplify(expression.subs(x, valeur))
    if _egaux(calcule, annonce):
        return VerdictMethode(OK, f"Valeur recalculée : {_texte(calcule)}.", [_texte(calcule)])
    return VerdictMethode(
        CONTRADICTION,
        f"En remplaçant {x.name} par {_texte(valeur)}, SymPy trouve {_texte(calcule)} ; la correction annonce {_texte(annonce)}.",
        [_texte(calcule)],
    )


def _nature(f1: sp.Expr, x: sp.Symbol, x0: sp.Expr) -> str | None:
    """'minimum local', 'maximum local' ou None (pas d'extremum : pas de changement de signe de f')."""
    eps = sp.Rational(1, 1000)
    gauche, droite = f1.subs(x, x0 - eps), f1.subs(x, x0 + eps)
    if not (gauche.is_real and droite.is_real) or gauche == 0 or droite == 0:
        return None
    if gauche < 0 < droite:
        return "minimum local"
    if gauche > 0 > droite:
        return "maximum local"
    return None


def _nature_annoncee(texte: str) -> str | None:
    t = (texte or "").lower()
    if "min" in t:
        return "minimum local"
    if "max" in t:
        return "maximum local"
    return None


def _verifier_extrema(a: dict) -> VerdictMethode:
    x = symbole(a.get("variable") or "x")
    f = analyser(a.get("fonction"), (x.name,))
    f1 = sp.diff(f, x)
    critiques = _solutions_reelles(f1, sp.Integer(0), x)
    if critiques is None:
        return VerdictMethode(INDISPONIBLE, "Les points critiques ne sont pas calculables comme ensemble fini.")
    calcules = []
    for c in critiques:
        nature = _nature(f1, x, c)
        if nature:
            calcules.append((c, sp.simplify(f.subs(x, c)), nature))
    annonces = []
    for e in a.get("extrema") or []:
        if not isinstance(e, dict):
            continue
        annonces.append((analyser(e.get("x"), (x.name,)), analyser(e.get("y"), (x.name,)), _nature_annoncee(e.get("nature", ""))))
    resume = "; ".join(f"{n} en {x.name} = {_texte(c)} (valeur {_texte(v)})" for c, v, n in calcules) or "aucun extremum local"
    restants = list(calcules)
    for xa, ya, na in annonces:
        for item in restants:
            c, v, n = item
            if _egaux(xa, c) and _egaux(ya, v) and na == n:
                restants.remove(item)
                break
        else:
            return VerdictMethode(
                CONTRADICTION,
                f"Extrema annoncés différents du calcul de SymPy. Calcul : {resume}.",
                [_texte(c) for c, _, _ in calcules],
            )
    if restants:
        return VerdictMethode(
            CONTRADICTION, f"Des extrema sont absents de la correction. Calcul : {resume}.", [_texte(c) for c, _, _ in calcules]
        )
    return VerdictMethode(OK, f"Extrema recalculés : {resume}.", [_texte(c) for c, _, _ in calcules])


def _borne(texte: str, x: sp.Symbol):
    t = (texte or "").strip().replace("+∞", "oo").replace("-∞", "-oo").replace("∞", "oo").replace("+oo", "oo")
    return analyser(t, (x.name,))


def _verifier_variations(a: dict) -> VerdictMethode:
    x = symbole(a.get("variable") or "x")
    f = analyser(a.get("fonction"), (x.name,))
    f1 = sp.diff(f, x)
    critiques = _solutions_reelles(f1, sp.Integer(0), x)
    if critiques is None:
        return VerdictMethode(INDISPONIBLE, "Le signe de la dérivée n'est pas calculable ici.")
    intervalles = [i for i in (a.get("intervalles") or []) if isinstance(i, dict)]
    if not intervalles:
        return VerdictMethode(INDISPONIBLE, "Aucun intervalle à contrôler.")
    for i in intervalles:
        inf, sup = _borne(i.get("borne_inf"), x), _borne(i.get("borne_sup"), x)
        sens = (i.get("sens") or "").lower()
        if "croiss" not in sens and "const" not in sens:
            return VerdictMethode(INDISPONIBLE, "Sens de variation non reconnu.")
        if any(inf < c < sup for c in critiques):
            return VerdictMethode(
                CONTRADICTION,
                f"La dérivée s'annule à l'intérieur de ]{_texte(inf)} ; {_texte(sup)}[ : le sens de variation y change.",
            )
        if inf == -sp.oo and sup == sp.oo:
            test = sp.Integer(0)
        elif inf == -sp.oo:
            test = sup - 1
        elif sup == sp.oo:
            test = inf + 1
        else:
            test = (inf + sup) / 2
        signe = f1.subs(x, test)
        if not signe.is_real:
            return VerdictMethode(INDISPONIBLE, "Signe de la dérivée indéterminé.")
        reel = "décroissante" if signe < 0 else "croissante" if signe > 0 else "constante"
        annonce = "décroissante" if "d" in sens[:3] or "décr" in sens or "decr" in sens else "croissante" if "croiss" in sens else "constante"
        if reel != annonce:
            return VerdictMethode(
                CONTRADICTION,
                f"Sur ]{_texte(inf)} ; {_texte(sup)}[ la fonction est {reel} (signe de f' = {'+' if signe > 0 else '-'}), "
                f"pas {annonce}.",
            )
    return VerdictMethode(OK, "Sens de variation confirmé par le signe de la dérivée sur chaque intervalle.")


_VERIFICATEURS = {
    "equation": _verifier_equation,
    "derivee": _verifier_derivee,
    "egalite": _verifier_egalite,
    "substitution": _verifier_substitution,
    "extrema": _verifier_extrema,
    "variations": _verifier_variations,
}


def verifier_avec_sympy(affirmation: dict) -> VerdictMethode:
    verificateur = _VERIFICATEURS.get(affirmation.get("type"))
    if verificateur is None:
        return VerdictMethode(INDISPONIBLE, "Ce type de calcul n'est pas pris en charge par le contrôle automatique.")
    try:
        return verificateur(affirmation)
    except ExpressionInvalide as exc:
        return VerdictMethode(INDISPONIBLE, f"Expression non interprétable pour le contrôle automatique ({exc}).")
    except (sp.SympifyError, TypeError, ValueError, ZeroDivisionError, NotImplementedError, RecursionError, AttributeError) as exc:
        return VerdictMethode(INDISPONIBLE, f"Le contrôle automatique n'a pas pu aboutir ({type(exc).__name__}).")
