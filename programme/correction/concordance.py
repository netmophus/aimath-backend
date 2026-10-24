"""
Concordance entre la réponse RÉDIGÉE et le résultat CALCULÉ indépendamment (étape 9.1.1).

Deux notions distinctes, jamais confondues :
- « calcul vérifié » : les opérations déclarées dans la correction ont été recalculées par SymPy / Wolfram Alpha
  (contrôles de `verification.py`, inchangés) ;
- « concordance » : la réponse écrite par l'IA pour la question correspond au résultat que le moteur calcule, lui,
  à partir des données de l'énoncé CONFIRMÉ. Une résolution peut avoir des calculs justes et une réponse finale
  recopiée de travers : c'est précisément ce que la concordance détecte.

Statuts : `verifiee` | `non_verifiee` (réponse non interprétable ou non comparable de façon fiable) |
`contradiction` (réponse interprétée mais incompatible avec le résultat calculé).
Une simulation GeoGebra n'intervient jamais ici : elle ne peut pas faire passer une réponse de « non vérifiée » à
« vérifiée ». Cette étape ne gère que les coordonnées d'un vecteur ; d'autres types de réponses s'ajouteront en
enrichissant `concordance_question`, sans toucher au reste.
"""

from __future__ import annotations

from .coordonnees_vecteur import (
    demande_les_coordonnees,
    extraire_points,
    formater_paire,
    lire_coordonnees,
    vecteur_demande,
    vecteur_exact,
)

VERIFIEE = "verifiee"
NON_VERIFIEE = "non_verifiee"
CONTRADICTION = "contradiction"

METHODES = ["SymPy", "Calcul exact"]


def _resultat(statut: str, grandeur: str, detail: str, attendu=None, annonce=None) -> dict:
    return {
        "statut": statut,
        "grandeur": grandeur,
        "attendu": formater_paire(attendu) if attendu is not None else None,
        "annonce": formater_paire(annonce) if annonce is not None else None,
        "detail": detail,
        "methodes": METHODES if attendu is not None else [],
    }


def concordance_question(sources: tuple[str, ...], texte_question: str, resultat: str) -> dict | None:
    """Concordance de la réponse rédigée d'une question, ou None si la question n'est pas du type pris en charge
    (aucun vecteur unique nommé, ou la question ne demande pas des coordonnées)."""
    nommes = vecteur_demande(texte_question)
    if nommes is None or not demande_les_coordonnees(texte_question):
        return None
    na, nb = nommes
    nom = na + nb
    grandeur = f"Coordonnées du vecteur {nom}"

    points, ambigus = extraire_points(sources)
    if na in ambigus or nb in ambigus or na not in points or nb not in points:
        return _resultat(
            NON_VERIFIEE, grandeur,
            f"Les coordonnées des points {na} et {nb} ne sont pas définies sans ambiguïté dans l'énoncé : le résultat "
            "attendu n'a pas pu être calculé de façon fiable.",
        )
    attendu = vecteur_exact(points[na], points[nb])
    if attendu is None:
        return _resultat(NON_VERIFIEE, grandeur, "Les deux calculs indépendants ne concordent pas : rien n'est affirmé.")

    lecture = lire_coordonnees(resultat, nom)
    if lecture.statut != "lue":
        return _resultat(NON_VERIFIEE, grandeur, f"{lecture.raison} La concordance n'a pas pu être vérifiée.", attendu=attendu)

    annonce = lecture.valeur
    if annonce == attendu:
        return _resultat(
            VERIFIEE, grandeur,
            f"La réponse rédigée {formater_paire(annonce)} correspond au résultat calculé indépendamment.",
            attendu=attendu, annonce=annonce,
        )
    detail = f"La réponse rédigée {formater_paire(annonce)} est incompatible avec le résultat calculé {formater_paire(attendu)}."
    if (annonce[1], annonce[0]) == attendu:
        detail += " Les deux composantes semblent inversées."
    elif (-annonce[0], -annonce[1]) == attendu:
        detail += f" Le signe semble opposé (vecteur {nb}{na})."
    return _resultat(CONTRADICTION, grandeur, detail, attendu=attendu, annonce=annonce)
