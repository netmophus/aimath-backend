"""
Sélection DÉTERMINISTE des simulations d'une correction (étape 9.1).

Entrées : l'énoncé confirmé (normalisé) et la correction vérifiée. Aucun appel IA, aucune écriture dans la
correction mise en cache : les simulations sont ajoutées à une COPIE au moment de la réponse, après contrôle du
réglage (développement local seulement tant que la licence GeoGebra n'est pas finalisée).
Toute erreur interne laisse la correction intacte : une simulation est un bonus, jamais une condition.
"""

from __future__ import annotations

import copy
import logging

from django.conf import settings

from ..lecture_exercice import cle_matiere
from . import geometrie_triangle, plan_complexe, suite_recurrente, vecteur_deux_points  # noqa: F401  (enregistrent les modèles dans le catalogue)
from .catalogue import CATALOGUE, ContexteSimulation, ParametresInvalides, valider_simulation

logger = logging.getLogger(__name__)

MAX_SIMULATIONS_PAR_QUESTION = 2


def simulations_activees() -> bool:
    """Désactivées par défaut ; tant que SIMULATIONS_DEV_SEULEMENT est vrai (défaut), exigent DEBUG=True."""
    if not settings.SIMULATIONS_ACTIVES:
        return False
    return settings.DEBUG or not settings.SIMULATIONS_DEV_SEULEMENT


def question_confirmee(analyse: dict, index: int, numero: str, nb_questions: int) -> str:
    """Texte CONFIRMÉ de la question (jamais la reformulation de l'IA) : par numéro, sinon par rang."""
    questions = analyse["questions"]
    if numero:
        for q in questions:
            if q["numero"] == numero:
                return q["texte"]
    if len(questions) == nb_questions and index < len(questions):
        return questions[index]["texte"]
    return ""


def sources_enonce(analyse: dict) -> tuple[str, ...]:
    """Textes CONFIRMÉS dont on peut tirer des données : énoncé, données, questions (jamais la rédaction de l'IA)."""
    return (
        analyse["enonce"],
        *(f"{d['libelle']} {d['valeur']}" for d in analyse["donnees"]),
        *(q["texte"] for q in analyse["questions"]),
    )


def simulations_pour_question(analyse: dict, matiere: str, texte: str, numero: str, resultat: str) -> list[dict]:
    sources = sources_enonce(analyse)
    contexte = ContexteSimulation(matiere=matiere, sources=sources, question_texte=texte, question_numero=numero, resultat=resultat)
    sorties: list[dict] = []
    for modele in CATALOGUE.values():
        if matiere not in modele.matieres or len(sorties) >= MAX_SIMULATIONS_PAR_QUESTION:
            continue
        proposition = modele.proposer(contexte)
        if proposition is None:
            continue
        try:
            sorties.append(valider_simulation({
                "modele": modele.id,
                "version": modele.version,
                "titre": proposition.titre,
                "parametres": proposition.parametres,
                "verification": proposition.verification,
                "avertissement": modele.avertissement,
            }))
        except ParametresInvalides:
            logger.error("simulation %s rejetée à la validation finale", modele.id)
    return sorties


AVERTISSEMENT_PROFESSEUR = "Illustration pour t'aider à visualiser : elle ne valide pas ta réponse, c'est le professeur qui la contrôle."


def projeter_pour_professeur(simulation: dict) -> dict | None:
    """Version d'une simulation destinée au Professeur particulier : paramètres RÉDUITS selon le modèle (sans la réponse
    d'une question non dévoilée), aucune mention de contrôle ni de concordance, avertissement adapté. Revalidée avant
    de partir. None si le modèle ne prévoit pas de projection ou si quoi que ce soit est invalide : rien n'est envoyé."""
    try:
        valide = valider_simulation(simulation)
        modele = CATALOGUE[valide["modele"]]
        if modele.projeter is None:
            return None
        projetee = {
            "modele": valide["modele"],
            "version": valide["version"],
            "titre": valide["titre"],
            "parametres": modele.projeter(valide["parametres"]),
            "verification": {"methodes": [], "concordance_correction": "non_applicable"},
            "avertissement": AVERTISSEMENT_PROFESSEUR,
        }
        return valider_simulation(projetee)
    except (ParametresInvalides, KeyError):
        logger.error("projection pédagogique d'une simulation rejetée")
        return None


def avec_simulations(correction: dict, analyse: dict, matiere_programme: str) -> dict:
    """Copie de la correction dont chaque question reçoit `simulations` (liste, souvent vide) ; sinon inchangée."""
    if not simulations_activees():
        return correction
    try:
        matiere = cle_matiere(matiere_programme) or ""
        sortie = copy.deepcopy(correction)
        nb = len(sortie["questions"])
        for index, question in enumerate(sortie["questions"]):
            texte = question_confirmee(analyse, index, question.get("numero", ""), nb)
            question["simulations"] = simulations_pour_question(
                analyse, matiere, texte, question.get("numero", ""), question.get("resultat", "")
            )
        return sortie
    except Exception:  # noqa: BLE001 — la correction doit toujours être livrée
        logger.exception("sélection des simulations abandonnée")
        return correction
