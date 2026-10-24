"""
Étude STRUCTURÉE d'une fonction polynomiale d'une variable (étape 8A) : dérivée,
points critiques, signe de la dérivée, extrema, variations, limites, et les
données nécessaires pour tracer la courbe et le tableau de variations.

Tout est calculé ICI, par SymPy en calcul exact (rationnels et radicaux) — jamais
déduit d'une description écrite par l'IA : la seule entrée est l'expression de la
fonction, lue par l'analyseur SÛR de `expressions.py` (ni eval ni sympify).
Le résultat est ensuite contrôlé numériquement (échantillonnage indépendant) ;
au moindre désaccord, ou si la fonction sort du périmètre pris en charge,
`statut` vaut « non_pris_en_charge » et AUCUNE donnée de tracé n'est fournie :
l'interface affiche alors une explication, jamais un graphique approximatif.

Périmètre de la première version : polynômes à coefficients rationnels, degré
≤ 6, dont les points critiques s'écrivent avec des rationnels ou des radicaux
carrés (facteurs de la dérivée de degré ≤ 2 sur Q).
"""

from __future__ import annotations

import math

import sympy as sp

from .expressions import ExpressionInvalide, analyser, symbole

DEGRE_MAX = 6
COEFFICIENT_MAX = 10 ** 6
LATEX_MOINS_INF, LATEX_PLUS_INF = "-\\infty", "+\\infty"
METHODE = "SymPy (calcul exact) puis contrôle numérique indépendant"


class _NonPrisEnCharge(Exception):
    """La fonction sort du périmètre fiable : on explique, on ne trace rien."""


def _non_pris_en_charge(raison: str, texte: str = "") -> dict:
    return {"statut": "non_pris_en_charge", "raison": raison, "fonction_texte": texte[:120]}


# --- Formats ---------------------------------------------------------------------------------

def _latex(valeur) -> str:
    return sp.latex(valeur)


def _plat(valeur: sp.Expr) -> str:
    """Texte plat « 3*x^2 - 3 » lisible par function-plot (caractères 0-9 x + - * / ^ ( ) . seulement)."""
    return sp.sstr(valeur).replace("**", "^")


def _nombre(valeur: sp.Expr) -> str:
    """Valeur pour une étiquette de graphique : exacte si entière ou fractionnaire, approchée (≈) sinon."""
    if valeur.is_Rational:
        texte = str(valeur)
        return texte.replace("-", "−")
    approx = f"{float(sp.N(valeur, 15)):.3f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")
    return f"≈ {approx}"


def _borne_latex(borne) -> str:
    if borne == -sp.oo:
        return LATEX_MOINS_INF
    if borne == sp.oo:
        return LATEX_PLUS_INF
    return _latex(borne)


def _intervalle_latex(a, b) -> str:
    """Intervalle de variation : borne fermée en un réel (f est continue), ouverte en l'infini."""
    gauche = "]" if a == -sp.oo else "["
    droite = "[" if b == sp.oo else "]"
    return f"{gauche}{_borne_latex(a).lstrip('+')} ; {_borne_latex(b)}{droite}"


# --- Racines exactes -------------------------------------------------------------------------

def _racines_exactes(poly_expr: sp.Expr, x: sp.Symbol, *, tolerer_degre_eleve: bool) -> list[tuple[sp.Expr, int]]:
    """Racines réelles (valeur exacte, multiplicité) d'un polynôme à coefficients rationnels.
    Facteurs irréductibles de degré ≥ 3 : NonPrisEnCharge (ou ignorés si `tolerer_degre_eleve`)."""
    _, facteurs = sp.factor_list(poly_expr, x)
    racines: list[tuple[sp.Expr, int]] = []
    for facteur, mult in facteurs:
        p = sp.Poly(facteur, x)
        d = p.degree()
        if d == 0:
            continue
        if d == 1:
            a, b = p.all_coeffs()
            racines.append((sp.nsimplify(-b / a), mult))
        elif d == 2:
            a, b, c = p.all_coeffs()
            delta = b * b - 4 * a * c
            if delta < 0:
                continue
            for signe in (1, -1):
                racines.append((sp.radsimp(sp.simplify((-b + signe * sp.sqrt(delta)) / (2 * a))), mult))
        elif not tolerer_degre_eleve:
            raise _NonPrisEnCharge(
                "Un facteur de la dérivée est de degré 3 ou plus et irréductible : ses racines ne s'écrivent pas "
                "simplement, le tableau n'est pas construit automatiquement."
            )
    racines.sort(key=lambda r: float(sp.N(r[0], 30)))
    for (a, _), (b, _) in zip(racines, racines[1:]):
        if abs(float(sp.N(a - b, 30))) < 1e-12:
            raise _NonPrisEnCharge("Deux points critiques sont indiscernables : étude non fiable.")
    return racines


def _test_dans(a, b) -> sp.Rational:
    """Un rationnel strictement entre a et b (bornes éventuellement infinies)."""
    if a == -sp.oo and b == sp.oo:
        return sp.Integer(0)
    if a == -sp.oo:
        return sp.Integer(math.floor(float(sp.N(b, 30)))) - 1
    if b == sp.oo:
        return sp.Integer(math.ceil(float(sp.N(a, 30)))) + 1
    milieu = sp.Rational(str(sp.N((a + b) / 2, 40)))
    if not (a < milieu < b):
        raise _NonPrisEnCharge("Points critiques trop proches pour être séparés de façon fiable.")
    return milieu


def _signe(valeur: sp.Expr) -> str:
    s = sp.sign(valeur)
    return "+" if s > 0 else "-" if s < 0 else "0"


# --- Étude -----------------------------------------------------------------------------------

def _etudier(texte: str, variable: str) -> dict:
    x = symbole(variable or "x")
    f = analyser(texte, (x.name,))
    if f.free_symbols - {x}:
        raise _NonPrisEnCharge("La fonction contient une autre variable ou un paramètre : étude non automatique.")
    if not f.is_polynomial(x):
        raise _NonPrisEnCharge("La fonction n'est pas un polynôme (fraction, racine, exponentielle, trigonométrie…) : "
                               "cette première version ne construit pas de tableau pour ce type de fonction.")
    poly = sp.Poly(f, x)
    if poly.domain not in (sp.QQ, sp.ZZ):
        raise _NonPrisEnCharge("Les coefficients ne sont pas rationnels.")
    if poly.degree() > DEGRE_MAX:
        raise _NonPrisEnCharge(f"Le degré dépasse {DEGRE_MAX} : étude non automatique.")
    for c in poly.all_coeffs():
        if abs(c.p) > COEFFICIENT_MAX or c.q > COEFFICIENT_MAX:
            raise _NonPrisEnCharge("Les coefficients sont trop grands pour un tracé lisible.")
    f = poly.as_expr()
    deg = poly.degree()
    f1 = sp.diff(f, x)

    # -- points critiques, signe de f' --
    critiques = _racines_exactes(f1, x, tolerer_degre_eleve=False) if f1 != 0 else []
    bornes = [-sp.oo] + [r for r, _ in critiques] + [sp.oo]
    signes_bruts = []
    for a, b in zip(bornes, bornes[1:]):
        t = _test_dans(a, b)
        signes_bruts.append(_signe(f1.subs(x, t)) if f1 != 0 else "0")

    # -- fusion des intervalles de même signe (un point critique sans changement de signe n'est pas un extremum) --
    colonnes_x: list = [-sp.oo]
    signes: list[str] = [signes_bruts[0]]
    extrema, sans_extremum = [], []
    valeurs_critiques = []  # f(r) pour CHAQUE zéro de f', avec ou sans changement de signe
    for i, (r, mult) in enumerate(critiques):
        avant, apres = signes_bruts[i], signes_bruts[i + 1]
        valeur = sp.radsimp(sp.simplify(f.subs(x, r)))
        valeurs_critiques.append(valeur)
        if avant != apres:
            nature = "maximum local" if avant == "+" else "minimum local"
            extrema.append({"x": r, "y": valeur, "nature": nature})
            colonnes_x.append(r)
            signes.append(apres)
        else:
            sans_extremum.append({"x": r, "y": valeur})
    colonnes_x.append(sp.oo)

    # -- limites --
    if deg == 0:
        lim_moins = lim_plus = poly.all_coeffs()[0]
    else:
        c = poly.LC()
        lim_plus = sp.oo if c > 0 else -sp.oo
        lim_moins = lim_plus if deg % 2 == 0 else -lim_plus
    # Tableau affiché : TOUS les zéros de f' y figurent (ex. x³ en 0 : f' = 0 sans changement de signe).
    colonnes_tableau = [-sp.oo] + [r for r, _ in critiques] + [sp.oo]
    valeurs_f = [lim_moins] + valeurs_critiques + [lim_plus]
    zeros_derivee = list(range(1, len(colonnes_tableau) - 1))

    # -- intervalles de variation (fusionnés) --
    sens = {"+": "croissante", "-": "décroissante", "0": "constante"}
    intervalles = []
    for a, b, s in zip(colonnes_x, colonnes_x[1:], signes):
        intervalles.append({
            "borne_inf": _borne_latex(a), "borne_sup": _borne_latex(b), "signe": s, "sens": sens[s],
            "intervalle_latex": _intervalle_latex(a, b),
        })

    # -- contrôle numérique indépendant (échantillonnage flottant, hors SymPy exact) --
    controles = _controler_numeriquement(f, f1, x, colonnes_tableau, signes_bruts, extrema, valeurs_critiques, deg)

    # -- tracé --
    courbe = _donnees_courbe(f, x, extrema, deg)

    return {
        "statut": "verifie",
        "verification": {"methode": METHODE, "controles_numeriques": controles},
        "variable": x.name,
        "fonction": {"latex": _latex(f), "texte": _plat(f)},
        "derivee": {"latex": _latex(f1), "texte": _plat(f1)},
        "degre": deg,
        "constante": deg == 0,
        "points_critiques": [
            {"x_latex": _latex(r), "x": float(sp.N(r, 15)), "multiplicite": int(m)} for r, m in critiques
        ],
        "extrema": [
            {"x_latex": _latex(e["x"]), "y_latex": _latex(e["y"]), "x": float(sp.N(e["x"], 15)), "y": float(sp.N(e["y"], 15)),
             "nature": e["nature"]} for e in extrema
        ],
        "sans_extremum": [
            {"x_latex": _latex(e["x"]), "y_latex": _latex(e["y"]), "x": float(sp.N(e["x"], 15))} for e in sans_extremum
        ],
        "intervalles": intervalles,
        "limites": {"moins_infini": _borne_latex(lim_moins), "plus_infini": _borne_latex(lim_plus)},
        "tableau": {
            "x": [_borne_latex(c) for c in colonnes_tableau],
            "signes": signes_bruts,
            "f": [_borne_latex(v) for v in valeurs_f],
            "zeros_derivee": zeros_derivee,
        },
        "courbe": courbe,
    }


def _controler_numeriquement(f, f1, x, colonnes_x, signes, extrema, valeurs_critiques, deg) -> int:
    """Revérifie le tableau par échantillonnage flottant ; lève NonPrisEnCharge au moindre désaccord."""
    ff = sp.lambdify(x, f, "math")
    fd = sp.lambdify(x, f1, "math")
    nb = 0
    cols = [float(sp.N(c, 20)) if c not in (-sp.oo, sp.oo) else None for c in colonnes_x]
    for i, s in enumerate(signes):
        a, b = cols[i], cols[i + 1]
        lo = (a if a is not None else (b - 6 if b is not None else -6)) + (1e-3 if a is not None else 0)
        hi = (b if b is not None else (a + 6 if a is not None else 6)) - (1e-3 if b is not None else 0)
        if a is not None and b is not None:
            lo, hi = a + (b - a) * 0.02, b - (b - a) * 0.02
        pas = (hi - lo) / 20
        valeurs = [fd(lo + k * pas) for k in range(21)]
        if s == "+" and not all(v > -1e-9 for v in valeurs):
            raise _NonPrisEnCharge("Contrôle numérique en désaccord avec le signe calculé : étude non fiable.")
        if s == "-" and not all(v < 1e-9 for v in valeurs):
            raise _NonPrisEnCharge("Contrôle numérique en désaccord avec le signe calculé : étude non fiable.")
        if s == "0" and not all(abs(v) < 1e-9 for v in valeurs):
            raise _NonPrisEnCharge("Contrôle numérique en désaccord avec le signe calculé : étude non fiable.")
        nb += 1
    for r, y in zip(colonnes_x[1:-1], valeurs_critiques):
        xr, yr = float(sp.N(r, 20)), float(sp.N(y, 20))
        if abs(fd(xr)) > 1e-7 or abs(ff(xr) - yr) > 1e-7 * max(1.0, abs(yr)):
            raise _NonPrisEnCharge("Un zéro de la dérivée n'est pas confirmé numériquement : étude non fiable.")
        nb += 1
    for e in extrema:
        xe, ye = float(sp.N(e["x"], 20)), float(sp.N(e["y"], 20))
        if abs(ff(xe) - ye) > 1e-7 * max(1.0, abs(ye)):
            raise _NonPrisEnCharge("La valeur de l'extremum ne correspond pas à f : étude non fiable.")
        voisins = [ff(xe - 0.01), ff(xe + 0.01)]
        bon = all(v < ye for v in voisins) if e["nature"] == "maximum local" else all(v > ye for v in voisins)
        if not bon:
            raise _NonPrisEnCharge("L'extremum n'est pas confirmé par les valeurs voisines : étude non fiable.")
        nb += 1
    return nb


def _donnees_courbe(f, x, extrema, deg) -> dict:
    """Fenêtre de tracé et points remarquables VÉRIFIÉS (extrema, intersection avec l'axe des ordonnées,
    zéros exacts de f). Aucune expression venue de l'extérieur : `expr` est régénérée depuis le polynôme."""
    points, deja = [], []

    def ajouter(px, py, etiquette):
        """Point remarquable ; `etiquette` vide = point marqué sans texte (les zéros sont listés à part, pour
        éviter des étiquettes qui se chevauchent)."""
        fx, fy = float(sp.N(px, 15)), float(sp.N(py, 15))
        if any(abs(fx - ux) < 1e-9 and abs(fy - uy) < 1e-9 for ux, uy in deja):
            return
        deja.append((fx, fy))
        points.append({"x": fx, "y": fy, "etiquette": f"{etiquette} ({_nombre(px)} ; {_nombre(py)})" if etiquette else ""})

    for e in extrema:
        ajouter(e["x"], e["y"], "Max. local" if e["nature"] == "maximum local" else "Min. local")
    try:
        zeros = _racines_exactes(f, x, tolerer_degre_eleve=True) if deg >= 1 else []
    except _NonPrisEnCharge:
        zeros = []
    for r, _ in zeros:
        ajouter(r, sp.Integer(0), "")
    ajouter(sp.Integer(0), f.subs(x, 0), "")

    speciaux = [p["x"] for p in points]
    bas, haut = min(speciaux), max(speciaux)
    marge = max(1.0, (haut - bas) * 0.6)
    domaine_x = [round(bas - marge, 6), round(haut + marge, 6)]
    if haut - bas < 1e-9:  # un seul point remarquable : fenêtre centrée dessus
        domaine_x = [round(bas - 4, 6), round(bas + 4, 6)]
    ff = sp.lambdify(x, f, "math")
    echantillon = [ff(domaine_x[0] + (domaine_x[1] - domaine_x[0]) * k / 200) for k in range(201)]
    ys_points = [p["y"] for p in points]
    if extrema:
        # Fenêtre centrée sur ce qui compte (extrema, zéros) plutôt que sur les extrémités qui s'envolent.
        ymin, ymax = min(ys_points), max(ys_points)
    else:
        ymin, ymax = min(echantillon + ys_points), max(echantillon + ys_points)
        if ymax - ymin > 24:  # courbe très raide : on cadre autour du centre, le zoom fait le reste
            centre = ff((domaine_x[0] + domaine_x[1]) / 2)
            ymin, ymax = centre - 8, centre + 8
    if ymax - ymin < 1e-9:
        ymin, ymax = ymin - 2, ymax + 2
    marge_y = max(1.0, (ymax - ymin) * 0.3)
    return {
        "expr": _plat(f),
        "domaine_x": domaine_x,
        "domaine_y": [round(ymin - marge_y, 6), round(ymax + marge_y, 6)],
        "points": points,
        "zeros": [{"x_latex": _latex(r), "x": float(sp.N(r, 15))} for r, _ in zeros],
        "ordonnee_origine_latex": _latex(f.subs(x, 0)),
    }


# --- Point d'entrée --------------------------------------------------------------------------

def etudier_fonction(texte: str, variable: str = "x") -> dict:
    """Étude complète d'un polynôme, ou {"statut": "non_pris_en_charge", "raison": …} — jamais d'exception."""
    try:
        return _etudier(texte or "", variable or "x")
    except _NonPrisEnCharge as exc:
        return _non_pris_en_charge(str(exc), texte or "")
    except ExpressionInvalide as exc:
        return _non_pris_en_charge(f"Expression non interprétable pour une étude automatique ({exc}).", texte or "")
    except (sp.SympifyError, sp.PolynomialError, TypeError, ValueError, ZeroDivisionError, NotImplementedError,
            RecursionError, AttributeError, OverflowError):
        return _non_pris_en_charge("L'étude automatique de cette fonction n'a pas pu aboutir.", texte or "")


TYPES_ETUDE = ("extrema", "variations")


def etude_pour_affirmations(affirmations: list[dict]) -> dict | None:
    """Étude de la fonction visée par la PREMIÈRE affirmation d'extrema ou de variations (None s'il n'y en a
    pas). `demande` : ce que la question traite (« variations » → tableau, « extrema » → courbe et extrema),
    pour que l'interface n'affiche pas deux fois la même chose."""
    visees = [a for a in affirmations or [] if isinstance(a, dict) and a.get("type") in TYPES_ETUDE and a.get("fonction")]
    if not visees:
        return None
    premiere = visees[0]
    etude = etudier_fonction(premiere["fonction"], premiere.get("variable") or "x")
    etude["demande"] = sorted({a["type"] for a in visees if a["fonction"] == premiere["fonction"]})
    return etude
