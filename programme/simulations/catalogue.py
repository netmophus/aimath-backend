"""
Catalogue des simulations interactives (étape 9.1) — GÉNÉRAL et extensible.

Une simulation est un MODÈLE prédéfini (identifiant, version, matières et notions compatibles, paramètres,
règles de validation, conditions de proposition) ; jamais une commande GeoGebra. Le serveur ne publie que
`{modele, version, parametres validés}` : les commandes GeoGebra sont des constantes écrites dans le front, qui
reçoit uniquement des nombres et des noms de points validés. L'IA ne produit aucun paramètre : ils sont extraits
de l'énoncé CONFIRMÉ par des règles déterministes et recalculés indépendamment.

Ajouter un modèle = écrire un module (comme `vecteur_deux_points.py`) et l'enregistrer dans `CATALOGUE`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


class ParametresInvalides(ValueError):
    """Les paramètres d'une simulation sortent du cadre validé du modèle."""


@dataclass(frozen=True)
class ContexteSimulation:
    """Ce que voit un modèle pour décider s'il s'applique : uniquement des données confirmées ou vérifiées."""

    matiere: str  # clé normalisée (« mathematiques »…)
    sources: tuple[str, ...]  # énoncé confirmé, données, textes des questions (jamais la rédaction de l'IA)
    question_texte: str  # texte de la question concernée (énoncé confirmé)
    question_numero: str
    resultat: str  # résultat annoncé par la correction pour cette question (sert au recoupement uniquement)


@dataclass(frozen=True)
class Proposition:
    parametres: dict
    titre: str
    verification: dict  # méthodes de recalcul indépendant et concordance avec la correction


@dataclass(frozen=True)
class ModeleSimulation:
    id: str
    version: int
    titre: str
    matieres: frozenset[str]
    notions: tuple[str, ...]  # notions du programme concernées (documentation du catalogue)
    parametres: dict[str, str]  # nom → description (documentation du catalogue)
    conditions: tuple[str, ...]  # conditions pour proposer le modèle (documentation du catalogue)
    proposer: Callable[[ContexteSimulation], Proposition | None]
    valider: Callable[[object], dict]  # renvoie les paramètres normalisés ou lève ParametresInvalides
    avertissement: str = field(
        default="Illustration visuelle : elle ne démontre rien et ne remplace pas le contrôle SymPy / Wolfram Alpha de la correction."
    )
    # Divulgation progressive (Professeur particulier, étape 9.2) : renvoie une copie des paramètres VALIDÉS dont on a
    # retiré tout ce qui donnerait la réponse d'une question non encore dévoilée. Absent : le modèle n'est jamais
    # proposé dans le Professeur particulier (rien ne part vers le navigateur).
    projeter: Callable[[dict], dict] | None = None
    # Étape 9.2.2 — Divulgation conditionnée à la preuve. `revelatrice(parametres_projetes)` : la simulation montre-t-elle
    # un RÉSULTAT calculé (coordonnées, valeur numérique) ? Absent : le modèle est traité comme révélateur (prudence).
    # Une simulation révélatrice n'est envoyée que si la réponse est vérifiée (SymPy / Wolfram), confirmée par un
    # contrôle déterministe indépendant, ou si la solution a été légitimement débloquée : jamais sur le seul avis de l'IA.
    revelatrice: Callable[[dict], bool] | None = None
    # `controler(parametres_complets, texte_eleve)` : contrôle déterministe INDÉPENDANT de la réponse d'un élève, à partir
    # des paramètres recalculés depuis l'énoncé confirmé (jamais de l'IA). Renvoie « confirme », « contredit » ou None
    # (la réponse ne se prête pas au contrôle). Absent : aucun contrôle.
    controler: Callable[[dict, str], str | None] | None = None


CATALOGUE: dict[str, ModeleSimulation] = {}


def enregistrer(modele: ModeleSimulation) -> ModeleSimulation:
    if modele.id in CATALOGUE:
        raise ValueError(f"Modèle de simulation déjà enregistré : {modele.id}")
    CATALOGUE[modele.id] = modele
    return modele


def valider_simulation(simulation: object) -> dict:
    """Contrôle final d'une simulation avant publication : modèle connu, version courante, paramètres valides."""
    if not isinstance(simulation, dict):
        raise ParametresInvalides("Simulation illisible.")
    modele = CATALOGUE.get(simulation.get("modele"))  # type: ignore[arg-type]
    if modele is None:
        raise ParametresInvalides("Modèle de simulation inconnu.")
    if simulation.get("version") != modele.version:
        raise ParametresInvalides("Version de modèle non prise en charge.")
    return {**simulation, "parametres": modele.valider(simulation.get("parametres"))}
