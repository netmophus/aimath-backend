"""
Recevabilité d'une réponse d'élève (étape 9.2.2) : contrôles DÉTERMINISTES, sans IA, qui décident si un envoi compte
comme une TENTATIVE (donc fait avancer le déblocage de la solution) et mérite un appel au professeur.

Une réponse est irrecevable quand elle est : vide ou inutilisable (aucun caractère exploitable), une simple copie de la
consigne, une répétition d'une réponse déjà donnée, ou un texte manifestement hors sujet (aucune donnée mathématique
et aucun mot en rapport avec l'étape). Une réponse COURTE mais légitime reste recevable : un nombre, un couple, une
notation (« AB »), « oui » / « non », ou tout texte qui reprend un mot de l'énoncé ou du vocabulaire mathématique.

Une réponse irrecevable ne coûte rien à l'élève : pas de tentative comptée, pas d'appel IA, et un message qui l'aide
à repartir (indice, explication, ou reformulation).
"""

from __future__ import annotations

import re
import unicodedata

VIDE, INUTILISABLE, COPIE, REPETITION, HORS_SUJET, NE_SAIT_PAS = (
    "vide", "inutilisable", "copie", "repetition", "hors_sujet", "ne_sait_pas",
)

_OUI_NON = {"oui", "non", "vrai", "faux"}
_SYMBOLES_MATHS = set("=+-−×÷/^()[]{};:<>≤≥√∑∫Δ→∈∪∩∞%π")
_NE_SAIT_PAS = re.compile(
    r"\b(?:je\s+ne\s+sais\s+pas|je\s+sais\s+pas|jsp|aucune\s+idee|je\s+ne\s+comprends?\s+pas|je\s+comprends?\s+pas|"
    r"je\s+n[' ]?y\s+arrive\s+pas|aide(?:z)?[- ]?moi|bloque)\b"
)

# Vocabulaire mathématique courant : un texte qui en contient n'est pas « hors sujet ».
_LEXIQUE = {
    "point", "points", "vecteur", "vecteurs", "abscisse", "ordonnee", "coordonnee", "coordonnees", "repere", "origine",
    "fleche", "segment", "droite", "courbe", "axe", "axes", "plan", "distance", "milieu", "norme", "somme", "difference",
    "produit", "quotient", "calcul", "calculer", "soustrait", "soustraire", "additionne", "ajoute", "formule", "valeur",
    "resultat", "egal", "egale", "fonction", "derivee", "limite", "equation", "solution", "solutions", "racine", "signe",
    "coefficient", "terme", "facteur", "carre", "variable", "variation", "tableau", "graphique", "trace", "tracer",
    "place", "placer", "relie", "relier", "extremite", "composante", "composantes", "horizontal", "vertical",
    "horizontale", "verticale", "gauche", "droite", "haut", "bas", "positif", "negatif", "nul", "entier", "relatif",
    "angle", "triangle", "cercle", "rayon", "aire", "volume", "theoreme", "propriete", "definition", "donc", "car",
    "parce", "alors", "puisque", "x", "y",
}


# Mots-outils : leur présence dans la réponse ne prouve aucun rapport avec l'étape.
_MOTS_OUTILS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "en", "au", "aux", "est", "sont", "que", "qui", "je", "tu", "il",
    "on", "ne", "pas", "ce", "se", "sa", "son", "ses", "ma", "mon", "mes", "par", "pour", "sur", "dans", "avec", "ca", "si", "ni",
    "mais", "donc", "or", "car", "comme", "plus", "moins", "tres", "bien", "oui", "non",
}


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


def cle(texte: str) -> str:
    """Forme normalisée pour comparer deux réponses : sans accents, casse, espaces, ponctuation ni `$`."""
    t = _sans_accents((texte or "").lower()).replace("²", "^2").replace("−", "-").replace("–", "-").replace("×", "*")
    return re.sub(r"[^0-9a-z+\-*/^=.,;()]", "", t)


def _mots(texte: str) -> tuple[set[str], set[str]]:
    """(mots de 2 lettres ou plus en minuscules sans accents, majuscules isolées « A », « B »…)."""
    brut = texte or ""
    majuscules = set(re.findall(r"(?<![A-Za-zÀ-ÿ])[A-Z](?![A-Za-zÀ-ÿ])", brut))
    for groupe in re.findall(r"(?<![A-Za-zÀ-ÿ])[A-Z]{2,3}(?![A-Za-zÀ-ÿ])", brut):  # « AB », « ABC » : noms de points
        majuscules |= set(groupe)
    mots = {_sans_accents(m.lower()) for m in re.findall(r"[A-Za-zÀ-ÿ]{2,}", brut)}
    return mots, majuscules


def _a_du_contenu_math(texte: str) -> bool:
    return any(c.isdigit() or c in _SYMBOLES_MATHS or c == "\\" for c in texte)


def _en_rapport(mots: set[str], majuscules: set[str], contexte: str) -> bool:
    mots_ctx, maj_ctx = _mots(contexte)
    if majuscules & maj_ctx or mots & _LEXIQUE:
        return True
    if (mots & mots_ctx) - _MOTS_OUTILS:  # un mot de l'énoncé, même court (« AB »)
        return True
    racines = {m[:5] for m in mots_ctx if len(m) >= 4}
    return any(len(m) >= 4 and m[:5] in racines for m in mots)


def evaluer(texte: str, consigne: str, contexte: str, deja: list[str]) -> str | None:
    """None si la réponse est recevable ; sinon le motif du refus. `contexte` : textes de la question et de l'étape ;
    `deja` : clés (`cle`) des réponses déjà prises en compte pour cette étape."""
    brut = (texte or "").strip()
    if not brut:
        return VIDE
    if not any(c.isalnum() for c in brut):
        return INUTILISABLE
    k = cle(brut)
    if k and k in deja:
        return REPETITION
    sans_accents = _sans_accents(brut.lower())
    contenu_math = _a_du_contenu_math(brut)
    if not contenu_math and _NE_SAIT_PAS.search(sans_accents):
        return NE_SAIT_PAS
    mots, majuscules = _mots(brut)
    mots_consigne, _ = _mots(consigne)
    # Copie de la consigne : aucun élément nouveau (ni chiffre, ni symbole), presque tous les mots viennent de la consigne.
    if not contenu_math and len(mots) >= 3 and len(mots & mots_consigne) / len(mots) >= 0.8:
        return COPIE
    if k and len(k) >= 12 and k in cle(consigne):
        return COPIE
    if contenu_math or sans_accents.strip(" .!?") in _OUI_NON:
        return None
    return None if _en_rapport(mots, majuscules, contexte) else HORS_SUJET


_MESSAGES = {
    VIDE: "Écris ta réponse avant de l'envoyer.",
    INUTILISABLE: "Je n'arrive pas à lire cette réponse. Écris un nombre, un calcul ou une courte phrase.",
    COPIE: "Tu as recopié la consigne : écris ce que tu proposes comme réponse, même si tu n'es pas sûr(e).",
    REPETITION: "Tu m'as déjà envoyé cette réponse. Change quelque chose dans ton calcul, ou demande un indice si tu es bloqué.",
    HORS_SUJET: "Je ne vois pas le rapport avec la question. Essaie de répondre à la consigne, même par une réponse incomplète.",
    NE_SAIT_PAS: "Pas de souci, c'est normal de bloquer. Demande un indice, ou le bouton « Je n'ai pas compris » pour une autre explication.",
}


def message(motif: str, nb_refus: int) -> str:
    """Message d'aide (sans IA). Après plusieurs refus, on oriente vers les aides qui existent déjà."""
    texte = _MESSAGES[motif]
    if nb_refus >= 3 and motif != NE_SAIT_PAS:
        texte += " Si tu ne sais pas par où commencer, demande un indice ou une explication avec « Je n'ai pas compris »."
    return texte
