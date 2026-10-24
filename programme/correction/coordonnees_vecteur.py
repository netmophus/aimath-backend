"""
Lecture STRICTE des coordonnées d'un vecteur dans un texte (étape 9.1.1) : analyseur à VOCABULAIRE FERMÉ.

Aucun `eval`, aucune exécution, aucun appel IA : uniquement des expressions régulières bornées et de l'arithmétique
exacte (`Fraction`). Le texte lu (rédaction de l'IA, énoncé) est une donnée, jamais du code.

Écritures reconnues pour les coordonnées (x ; y) :
- `(3 ; 1)` — point-virgule, toujours non ambigu ;
- `(3 , 1)` / `(3, 1)` — virgule SEULEMENT entre deux entiers et avec au moins une espace (sinon « 3,1 » pourrait
  être un décimal : l'écriture est jugée ambiguë et rien n'est lu) ;
- `\\begin{pmatrix} 3 \\\\ 1 \\end{pmatrix}`, `bmatrix`, `\\begin{array}{c} … \\end{array}` (colonne) ;
- `\\binom{3}{1}` / `\\dbinom{3}{1}`.
Nombres : entiers, décimaux (point ou virgule), fractions `\\frac{a}{b}`, signe `-`, `−`, `+`.
Le nom du vecteur peut précéder : `AB`, `\\vec{AB}`, `\\overrightarrow{AB}`, `vecteur AB`.

Règle de prudence : tout ce qui n'est pas reconnu SANS AMBIGUÏTÉ reste « non lu » (jamais deviné) : plusieurs
écritures différentes, écriture portant sur un autre vecteur, virgule ambiguë, forme inconnue.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

import sympy as sp

_TAILLE_MAX = 5000  # au-delà, le texte n'est pas analysé (la rédaction est déjà bornée en amont)

# --- Nombres ----------------------------------------------------------------

_DECIMAL = r"\d+(?:[.,]\d{1,6})?"
_FRACTION = r"\\frac\{\d{1,6}\}\{\d{1,6}\}"
_NOMBRE = rf"[-+]?\s?(?:{_DECIMAL}|{_FRACTION})"
_ENTIER = r"[-+]?\s?\d{1,9}"

_RE_VALEUR = re.compile(rf"^([-+]?)\s?(?:({_DECIMAL})|\\frac\{{(\d{{1,6}})\}}\{{(\d{{1,6}})\}})$")


def valeur_exacte(texte: str) -> Fraction | None:
    """Valeur exacte d'un nombre écrit dans le vocabulaire fermé, sinon None."""
    m = _RE_VALEUR.match(texte.strip())
    if not m:
        return None
    signe, decimal, num, den = m.groups()
    if decimal is not None:
        valeur = Fraction(Decimal(decimal.replace(",", ".")))
    else:
        if int(den) == 0:
            return None
        valeur = Fraction(int(num), int(den))
    return -valeur if signe == "-" else valeur


# --- Normalisation du texte -------------------------------------------------

def normaliser(texte: str) -> str:
    """Texte à plat : sans `$`, sans mise en forme LaTeX courante, `−` → `-`, `\\vec{AB}` → `vecteur AB`.

    Les commandes d'espacement `\\,` `\\;` `\\:` `\\!` `\\ ` sont retirées SAUF lorsqu'elles forment la fin d'un
    saut de ligne `\\\\` (colonne d'une matrice) : `3 \\\\ 1` doit rester `3 \\\\ 1`.
    """
    t = texte.replace("−", "-").replace("–", "-").replace("\u00a0", " ").replace("\u202f", " ")
    t = re.sub(r"\\(?:left|right)\s*", "", t)
    t = re.sub(r"(?<!\\)\\[,;:! ]", " ", t)
    t = t.replace("{,}", ",").replace("~", " ")
    t = re.sub(r"\\[dt]frac", r"\\frac", t)
    t = re.sub(r"\\(?:overrightarrow|vec)\s*\{?\s*([A-Z])\s*([A-Z])\s*\}?", r"vecteur \1\2", t)
    return t.replace("$", " ")


def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c))


# --- Écritures de coordonnées -----------------------------------------------

_RE_PAIRE_PV = re.compile(rf"\(\s*({_NOMBRE})\s*;\s*({_NOMBRE})\s*\)")
_RE_PAIRE_VIRGULE = re.compile(rf"\(\s*({_ENTIER})(?:\s+,\s*|\s*,\s+)({_ENTIER})\s*\)")
_RE_COLONNE = re.compile(
    rf"\\begin\{{(p?matrix|bmatrix|array)\}}(?:\{{c\}})?\s*({_NOMBRE})\s*\\\\\s*({_NOMBRE})\s*\\end\{{\1\}}"
)
_RE_BINOME = re.compile(rf"\\d?binom\s*\{{\s*({_NOMBRE})\s*\}}\s*\{{\s*({_NOMBRE})\s*\}}")
_RE_VIRGULE_AMBIGUE = re.compile(r"\(\s*[-+]?\s?\d+,\d+\s*\)")

_RE_NOM_VECTEUR = re.compile(r"vecteur\s+([A-Z])([A-Z])\b")
_RE_PREFIXE_VECTEUR = re.compile(r"(?:vecteur\s+([A-Z])([A-Z])|(?<![A-Za-z])([A-Z])([A-Z]))\s*(?:=\s*)?$")
_RE_PREFIXE_POINT = re.compile(r"(?<![A-Za-z])[A-Z]\s*(?:=\s*)?$")


# Écritures de type code ou commande : jamais interprétées (le texte est une donnée), et une écriture qui en contient
# ne peut pas servir à « confirmer » une réponse, même si elle renferme par hasard les bons nombres.
_RE_SUSPECT = re.compile(
    r"""["`<>]|['’]\s*[()]|[()]\s*['’]|__|\{\{|\$\(\s*[A-Za-z]|\\(?:input|include|write|immediate|openout|read|def|csname|catcode|newcommand)(?![A-Za-z])|\b[a-z]{2,}\s*\("""
)


@dataclass(frozen=True)
class LectureCoordonnees:
    """statut : `lue` (valeur renseignée) | `absente` | `ambigue` | `autre_vecteur`."""

    statut: str
    valeur: tuple[Fraction, Fraction] | None
    raison: str


def _paires(texte: str) -> list[tuple[int, int, Fraction, Fraction]]:
    """Toutes les écritures de coordonnées reconnues : (début, fin, x, y)."""
    trouvees: list[tuple[int, int, Fraction, Fraction]] = []
    for motif, g1, g2 in (
        (_RE_PAIRE_PV, 1, 2), (_RE_PAIRE_VIRGULE, 1, 2), (_RE_COLONNE, 2, 3), (_RE_BINOME, 1, 2),
    ):
        for m in motif.finditer(texte):
            x, y = valeur_exacte(m.group(g1)), valeur_exacte(m.group(g2))
            if x is not None and y is not None:
                trouvees.append((m.start(), m.end(), x, y))
    return trouvees


def _prefixe(texte: str, debut: int) -> tuple[str, str | None]:
    """Ce qui précède une écriture : (`vecteur`, nom) | (`point`, None) | (`aucun`, None). Saute une « ( » ouvrante."""
    avant = re.sub(r"\(\s*$", "", texte[:debut])
    m = _RE_PREFIXE_VECTEUR.search(avant)
    if m:
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        return "vecteur", a + b
    if _RE_PREFIXE_POINT.search(avant):
        return "point", None
    return "aucun", None


def lire_coordonnees(texte: str, nom: str) -> LectureCoordonnees:
    """Coordonnées du vecteur `nom` (ex. « AB ») écrites dans `texte`, ou la raison pour laquelle on ne les lit pas."""
    if not isinstance(texte, str) or not texte.strip() or len(texte) > _TAILLE_MAX:
        return LectureCoordonnees("absente", None, "Aucune réponse rédigée exploitable.")
    t = normaliser(texte)
    brut = re.sub(r"\\(?:left|right)", "", texte)
    if _RE_SUSPECT.search(brut) or _RE_SUSPECT.search(t):  # texte brut aussi : `normaliser` retire les « $ »
        return LectureCoordonnees("absente", None, "Le texte contient des éléments non reconnus (commande, code) : il n'est pas interprété.")
    paires = _paires(t)

    nommees: list[tuple[Fraction, Fraction]] = []
    sans_nom: list[tuple[Fraction, Fraction]] = []
    autres = False
    for debut, _fin, x, y in paires:
        genre, nom_trouve = _prefixe(t, debut)
        if genre == "point":
            continue  # coordonnées d'un POINT, pas d'un vecteur
        if genre == "vecteur":
            if nom_trouve == nom:
                nommees.append((x, y))
            else:
                autres = True
        else:
            sans_nom.append((x, y))

    if nommees:
        distinctes = set(nommees)
        if len(distinctes) == 1:
            return LectureCoordonnees("lue", nommees[0], "")
        return LectureCoordonnees("ambigue", None, f"Plusieurs coordonnées différentes sont données pour le vecteur {nom}.")

    mentions = {a + b for a, b in _RE_NOM_VECTEUR.findall(t)}
    if autres or (mentions - {nom}):
        if sans_nom or autres:
            return LectureCoordonnees("autre_vecteur", None, f"La réponse rédigée ne porte pas clairement sur le vecteur {nom}.")

    if sans_nom:
        distinctes = set(sans_nom)
        if len(distinctes) == 1:
            return LectureCoordonnees("lue", sans_nom[0], "")
        return LectureCoordonnees("ambigue", None, "Plusieurs coordonnées différentes apparaissent dans la réponse rédigée.")

    if _RE_VIRGULE_AMBIGUE.search(t):
        return LectureCoordonnees("ambigue", None, "Écriture ambiguë : la virgule peut séparer les coordonnées ou être décimale (écris « (3 ; 1) »).")
    return LectureCoordonnees("absente", None, "Aucune écriture reconnue des coordonnées du vecteur dans la réponse rédigée.")


# --- Calcul indépendant -----------------------------------------------------

def vecteur_exact(a: tuple[Fraction, Fraction], b: tuple[Fraction, Fraction]) -> tuple[Fraction, Fraction] | None:
    """AB = B − A en arithmétique exacte ET avec SymPy ; None si les deux calculs divergent (jamais silencieux)."""
    direct = (b[0] - a[0], b[1] - a[1])
    ma = sp.Matrix([sp.Rational(a[0].numerator, a[0].denominator), sp.Rational(a[1].numerator, a[1].denominator)])
    mb = sp.Matrix([sp.Rational(b[0].numerator, b[0].denominator), sp.Rational(b[1].numerator, b[1].denominator)])
    v = mb - ma
    avec_sympy = (Fraction(int(v[0].p), int(v[0].q)), Fraction(int(v[1].p), int(v[1].q)))
    return direct if avec_sympy == direct else None


def formater_nombre(valeur: Fraction) -> str:
    """Écriture française lisible : « 3 », « −1,5 », « 1/3 »."""
    if valeur.denominator == 1:
        texte = str(valeur.numerator)
    else:
        d = valeur.denominator
        while d % 2 == 0:
            d //= 2
        while d % 5 == 0:
            d //= 5
        texte = str(float(valeur)).replace(".", ",") if d == 1 else f"{valeur.numerator}/{valeur.denominator}"
    return texte.replace("-", "−")


def formater_paire(paire: tuple[Fraction, Fraction]) -> str:
    return f"({formater_nombre(paire[0])} ; {formater_nombre(paire[1])})"


# --- Données de l'énoncé confirmé ---------------------------------------------

_NOMBRE_ENONCE = r"[-+]?\d+(?:[.,]\d{1,2})?"  # au plus 2 décimales (fenêtre GeoGebra et comparaisons exactes)
_RE_NOMBRE_ENONCE = re.compile(rf"^{_NOMBRE_ENONCE}$")
_RE_POINT = re.compile(r"(?<![A-Za-z\\])([A-Z])\s*\(([^()]*)\)")


def _fraction_enonce(texte: str) -> Fraction:
    return Fraction(Decimal(texte.replace(",", ".")))


def extraire_points(sources: tuple[str, ...]) -> tuple[dict[str, tuple[Fraction, Fraction]], set[str]]:
    """(points sans ambiguïté, lettres ambiguës). Un point s'écrit `Lettre(x ; y)` ; une lettre définie deux fois
    différemment, avec 3 coordonnées, des lettres ou une virgule ambiguë est AMBIGUË."""
    points: dict[str, tuple[Fraction, Fraction]] = {}
    ambigus: set[str] = set()
    for source in sources:
        for lettre, interieur in _RE_POINT.findall(normaliser(source)):
            morceaux = [m.strip() for m in interieur.split(";")]
            if len(morceaux) == 1:
                # « A(1,5) » ou « A(1 , 2) » : séparateur ambigu ; « F(x) » : fonction, pas un point
                if re.search(r"\d", interieur) and "," in interieur:
                    ambigus.add(lettre)
                continue
            if len(morceaux) != 2 or not all(_RE_NOMBRE_ENONCE.match(m) for m in morceaux):
                ambigus.add(lettre)  # 3 coordonnées, lettres, coordonnée vide…
                continue
            coord = (_fraction_enonce(morceaux[0]), _fraction_enonce(morceaux[1]))
            if lettre in points and points[lettre] != coord:
                ambigus.add(lettre)
            points[lettre] = coord
    return points, ambigus


def vecteur_demande(texte: str) -> tuple[str, str] | None:
    """Le SEUL vecteur de deux points nommé dans le texte d'une question, sinon None (aucun ou plusieurs)."""
    trouves = {(a, b) for a, b in _RE_NOM_VECTEUR.findall(normaliser(texte))}
    if len(trouves) != 1:
        return None
    a, b = next(iter(trouves))
    return (a, b) if a != b else None


def demande_les_coordonnees(texte: str) -> bool:
    """La question demande-t-elle des coordonnées / composantes (et non un tracé ou une représentation) ?"""
    return bool(re.search(r"\b(?:coordonnee|composante)s?\b", sans_accents(texte).casefold()))
