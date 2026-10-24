"""
Lecture SÛRE d'expressions mathématiques écrites en texte (« x^2 - 5x + 6 »).

Les expressions viennent d'un modèle d'IA ou de Wolfram Alpha : elles sont
NON FIABLES. On n'utilise donc ni eval, ni exec, ni sympify, ni parse_expr
(qui évaluent du Python) : un petit analyseur à descente récursive, à
vocabulaire fermé, construit directement les objets SymPy. Tout ce qui n'est
pas reconnu lève ExpressionInvalide.

Syntaxe acceptée : nombres (1, 2.5, 1,5), variables d'UNE lettre, pi, e,
+ - * / ^ **, parenthèses, multiplication implicite (3x, 2(x+1), (x+1)(x-1),
x sin(x)), fonctions sqrt, cbrt, sin, cos, tan, ln, log (décimal), exp, abs,
et les signes ² ³ × · ÷ − √ π.
"""

from __future__ import annotations

import re

import sympy as sp

LONGUEUR_MAX = 300
PROFONDEUR_MAX = 40
EXPOSANT_MAX = 60

FONCTIONS = {
    "sqrt": sp.sqrt,
    "cbrt": sp.cbrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "ln": sp.log,
    "log": lambda u: sp.log(u, 10),
    "exp": sp.exp,
    "abs": sp.Abs,
}
CONSTANTES = {"pi": sp.pi, "e": sp.E}

_REMPLACEMENTS = (
    ("−", "-"), ("–", "-"), ("×", "*"), ("·", "*"), ("÷", "/"), ("²", "^2"), ("³", "^3"),
    ("√", "sqrt"), ("π", "pi"), ("∞", "oo"), ("**", "^"), (" ", " "), (" ", " "),
)
_JETON = re.compile(r"\s*(?:(?P<nombre>\d+(?:[.,]\d+)?)|(?P<mot>[A-Za-z]+)|(?P<op>[-+*/^(),]))")


class ExpressionInvalide(ValueError):
    """Expression absente du vocabulaire accepté, trop longue ou mal formée."""


def _jetons(texte: str) -> list[tuple[str, str]]:
    for ancien, nouveau in _REMPLACEMENTS:
        texte = texte.replace(ancien, nouveau)
    texte = texte.strip().strip("$").strip()
    if not texte:
        raise ExpressionInvalide("expression vide")
    if len(texte) > LONGUEUR_MAX:
        raise ExpressionInvalide("expression trop longue")
    jetons, position = [], 0
    while position < len(texte):
        correspondance = _JETON.match(texte, position)
        if not correspondance or correspondance.end() == position:
            if texte[position:].strip() == "":
                break
            raise ExpressionInvalide(f"caractère non accepté près de « {texte[position:position + 8].strip()} »")
        position = correspondance.end()
        if correspondance.group("nombre"):
            jetons.append(("nombre", correspondance.group("nombre").replace(",", ".")))
        elif correspondance.group("mot"):
            jetons.append(("mot", correspondance.group("mot")))
        else:
            jetons.append(("op", correspondance.group("op")))
    return jetons


class _Analyseur:
    def __init__(self, jetons, variables: dict[str, sp.Symbol]):
        self.jetons = jetons
        self.i = 0
        self.variables = variables
        self.profondeur = 0

    def _pic(self):
        return self.jetons[self.i] if self.i < len(self.jetons) else (None, None)

    def _op(self, symbole: str) -> bool:
        return self._pic() == ("op", symbole)

    def _entrer(self):
        self.profondeur += 1
        if self.profondeur > PROFONDEUR_MAX:
            raise ExpressionInvalide("expression trop imbriquée")

    def analyser(self):
        valeur = self.somme()
        if self.i != len(self.jetons):
            raise ExpressionInvalide("fin d'expression inattendue")
        return valeur

    def somme(self):
        self._entrer()
        valeur = self.produit()
        while self._op("+") or self._op("-"):
            signe = self.jetons[self.i][1]
            self.i += 1
            terme = self.produit()
            valeur = valeur + terme if signe == "+" else valeur - terme
        self.profondeur -= 1
        return valeur

    def _debut_facteur(self) -> bool:
        genre, valeur = self._pic()
        return genre in ("nombre", "mot") or (genre == "op" and valeur == "(")

    def produit(self):
        valeur = self.unaire()
        while True:
            if self._op("*") or self._op("/"):
                signe = self.jetons[self.i][1]
                self.i += 1
                facteur = self.unaire()
                valeur = valeur * facteur if signe == "*" else valeur / facteur
            elif self._debut_facteur():  # multiplication implicite : 3x, 2(x+1), (a)(b)
                valeur = valeur * self.puissance()
            else:
                return valeur

    def unaire(self):
        if self._op("-"):
            self.i += 1
            return -self.unaire()
        if self._op("+"):
            self.i += 1
            return self.unaire()
        return self.puissance()

    def puissance(self):
        base = self.atome()
        if self._op("^"):
            self.i += 1
            self._entrer()
            exposant = self.unaire_exposant()
            self.profondeur -= 1
            if exposant.is_number and abs(exposant) > EXPOSANT_MAX:
                raise ExpressionInvalide("exposant trop grand")
            return base ** exposant
        return base

    def unaire_exposant(self):
        if self._op("-"):
            self.i += 1
            return -self.unaire_exposant()
        return self.puissance()

    def atome(self):
        genre, valeur = self._pic()
        if genre == "nombre":
            self.i += 1
            return sp.Rational(valeur) if "." in valeur else sp.Integer(valeur)
        if genre == "op" and valeur == "(":
            self.i += 1
            interieur = self.somme()
            if not self._op(")"):
                raise ExpressionInvalide("parenthèse fermante manquante")
            self.i += 1
            return interieur
        if genre == "mot":
            return self.mot(valeur)
        raise ExpressionInvalide("expression incomplète")

    def mot(self, mot: str):
        minuscule = mot.lower()
        if minuscule in FONCTIONS:
            self.i += 1
            if self._op("("):
                self.i += 1
                argument = self.somme()
                if not self._op(")"):
                    raise ExpressionInvalide("parenthèse fermante manquante")
                self.i += 1
            else:  # « sin x », « sqrt 2 »
                argument = self.puissance()
            return FONCTIONS[minuscule](argument)
        if minuscule in CONSTANTES:
            self.i += 1
            return CONSTANTES[minuscule]
        if mot == "oo" or minuscule == "oo":
            self.i += 1
            return sp.oo
        # Lettres accolées (« xy », « ab ») : produit de variables d'une lettre connues.
        if all(lettre in self.variables for lettre in mot):
            self.i += 1
            produit = sp.Integer(1)
            for lettre in mot:
                produit *= self.variables[lettre]
            return produit
        raise ExpressionInvalide(f"« {mot} » n'est pas une variable ou une fonction acceptée")


def analyser(texte: str, variables: tuple[str, ...] = ("x",)) -> sp.Expr:
    """Texte -> expression SymPy. Les variables sont réelles ; ExpressionInvalide sinon."""
    if not isinstance(texte, str):
        raise ExpressionInvalide("expression absente")
    symboles = {nom: sp.Symbol(nom, real=True) for nom in variables}
    return _Analyseur(_jetons(texte), symboles).analyser()


def symbole(nom: str) -> sp.Symbol:
    if not re.fullmatch(r"[a-zA-Z]", nom or ""):
        raise ExpressionInvalide("la variable doit être une lettre")
    return sp.Symbol(nom, real=True)
