"""
Petits outils partagés par les modèles de simulation (étape 9.3) : fractions exactes lisibles, racines simplifiées et
vocabulaire fermé de lecture du texte CONFIRMÉ. Aucun appel IA, aucun `eval`.
"""

from __future__ import annotations

import re
from fractions import Fraction

from ..correction.coordonnees_vecteur import normaliser, sans_accents
from .catalogue import ParametresInvalides

_RE_FRACTION = re.compile(r"^(-?\d{1,12})(?:/(\d{1,12}))?$")

_INDICES = str.maketrans({
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4", "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
    "ₙ": "n", "₊": "+", "₋": "-",
})
_RE_RUN_INDICES = re.compile(r"[₀-₉ₙ₊₋]+")


def texte_a_plat(texte: str) -> str:
    """Texte confirmé à plat : sans `$`, `−` → `-`, `\\vec{AB}` → `vecteur AB`, indices Unicode → `_{…}`, `\\frac{a}{b}` → `(a)/(b)`,
    `\\mathrm{i}` → `i`, `\\times` / `\\cdot` → `*`."""
    t = normaliser(texte or "")
    t = _RE_RUN_INDICES.sub(lambda m: "_{" + m.group(0).translate(_INDICES) + "}", t)
    for _ in range(4):  # fractions imbriquées : de l'intérieur vers l'extérieur
        t = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\(?:mathrm|text|mathit)\s*\{\s*i\s*\}", "i", t)
    t = re.sub(r"\\(?:times|cdot)", "*", t)
    t = t.replace("×", "*").replace("·", "*").replace("²", "^2")
    return t


def minuscules_sans_accents(texte: str) -> str:
    return sans_accents(texte_a_plat(texte)).casefold()


def fraction_en_texte(f: Fraction) -> str:
    """« 5 », « 11/2 », « -3/4 » : écriture exacte et canonique, relue par `lire_fraction`."""
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def lire_fraction(valeur: object, borne: int = 10**12) -> Fraction:
    """Fraction exacte écrite « n » ou « n/d » (vocabulaire fermé) ; ParametresInvalides sinon."""
    if not isinstance(valeur, str):
        raise ParametresInvalides("Nombre exact attendu (texte).")
    m = _RE_FRACTION.fullmatch(valeur)
    if not m:
        raise ParametresInvalides("Écriture de nombre invalide.")
    den = int(m.group(2)) if m.group(2) else 1
    if den == 0:
        raise ParametresInvalides("Dénominateur nul.")
    f = Fraction(int(m.group(1)), den)
    if f.numerator > borne or f.numerator < -borne or f.denominator > borne:
        raise ParametresInvalides("Nombre hors des bornes.")
    if fraction_en_texte(f) != valeur:
        raise ParametresInvalides("Écriture non canonique.")
    return f


def racine_simplifiee(n: int) -> tuple[int, int]:
    """√n = coef·√rad avec rad sans facteur carré (n entier ≥ 0)."""
    if n < 0:
        raise ValueError("racine d'un négatif")
    coef, rad, p = 1, n, 2
    while p * p <= rad:
        while rad % (p * p) == 0:
            rad //= p * p
            coef *= p
        p += 1
    if n == 0:
        return 0, 1
    return coef, rad


def entier_borne(valeur: object, borne: int) -> int:
    if isinstance(valeur, bool) or not isinstance(valeur, int) or abs(valeur) > borne:
        raise ParametresInvalides("Entier hors des bornes.")
    return valeur
