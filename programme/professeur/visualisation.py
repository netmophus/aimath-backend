"""
Simulations GeoGebra dans le Professeur particulier (étape 9.2) : DIVULGATION PROGRESSIVE contrôlée par le serveur.

Principe de sécurité : le navigateur ne reçoit que les simulations des questions TERMINÉES (étapes réussies ou dont la
solution a été légitimement débloquée selon les règles de la séance), et seulement leur version RÉDUITE (voir
`ModeleSimulation.projeter`) : jamais la réponse d'une question non dévoilée. Rien n'est masqué en CSS ou en React :
ce qui ne doit pas être vu n'est tout simplement pas transmis.

- aucune route ne permet de DEMANDER une simulation : elles ne voyagent que dans l'état public de la séance, calculé à
  chaque réponse à partir de la progression enregistrée côté serveur (un client ne peut donc ni en réclamer une, ni
  en forcer une par un paramètre) ;
- les simulations complètes (avec leurs réponses) sont préparées au démarrage à partir de l'énoncé CONFIRMÉ et vivent
  dans l'état serveur, comme le plan et les réponses attendues ;
- elles dépendent du même réglage que la correction (développement local uniquement) et sont revérifiées à chaque envoi ;
- GeoGebra ne valide jamais une réponse : la vérification de l'élève reste celle de la séance (SymPy / Wolfram Alpha).
"""

from __future__ import annotations

import logging

from ..lecture_exercice import cle_matiere
from ..simulations.catalogue import CATALOGUE, ParametresInvalides, valider_simulation
from ..simulations.selection import (
    projeter_pour_professeur,
    question_confirmee,
    simulations_activees,
    simulations_pour_question,
)

logger = logging.getLogger(__name__)


def preparer(analyse: dict, matiere_programme: str, plan: list[dict]) -> dict[str, list[dict]]:
    """Simulations COMPLÈTES de chaque question du plan (clé = rang de la question), d'après l'énoncé confirmé. Vide si
    les simulations ne sont pas autorisées ou en cas d'erreur : une simulation est un bonus, jamais une condition."""
    if not simulations_activees():
        return {}
    try:
        matiere = cle_matiere(matiere_programme) or ""
        sortie: dict[str, list[dict]] = {}
        for rang, question in enumerate(plan):
            texte = question_confirmee(analyse, rang, question.get("numero", ""), len(plan))
            # Le Professeur n'a aucun « résultat rédigé » à recouper : la concordance n'existe pas ici.
            sims = simulations_pour_question(analyse, matiere, texte, question.get("numero", ""), "") if texte else []
            # Seuls les modèles qui prévoient une projection de divulgation (`projeter`) sont proposables au Professeur
            # particulier : vecteurs (9.2), nombres complexes, suites et géométrie du triangle (9.4).
            sims = [s for s in sims if CATALOGUE[s["modele"]].projeter is not None]
            if sims:
                sortie[str(rang)] = sims
        return sortie
    except Exception:  # noqa: BLE001 — la séance doit toujours démarrer
        logger.exception("professeur : préparation des simulations abandonnée")
        return {}


def question_terminee(etat: dict, rang: int) -> bool:
    """Toutes les étapes de la question sont closes : réussies, ou solution vue (déblocage conditionné côté serveur)."""
    etapes = [s for cle, s in etat["etapes"].items() if cle.startswith(f"{rang}-")]
    return bool(etapes) and all(s["statut"] != "en_cours" for s in etapes)


def _sans_preuve(etat: dict, rang: int) -> bool:
    """Une étape de la question a été acceptée SANS preuve (avis de l'IA seul, `reussie_non_verifiee`)."""
    return any(s["statut"] == "reussie_non_verifiee" for cle, s in etat["etapes"].items() if cle.startswith(f"{rang}-"))


def _revelatrice(simulation: dict) -> bool:
    """La simulation montre-t-elle un résultat calculé ? Modèle inconnu ou sans indication : oui (prudence)."""
    try:
        valide = valider_simulation(simulation)
        modele = CATALOGUE[valide["modele"]]
        return True if modele.revelatrice is None else bool(modele.revelatrice(valide["parametres"]))
    except (ParametresInvalides, KeyError):
        return True


def a_une_simulation_revelatrice(etat: dict, rang: int) -> bool:
    return any(_revelatrice(sim) for sim in etat.get("simulations", {}).get(str(rang), []))


def controler_reponse(etat: dict, texte: str) -> str | None:
    """Contrôle déterministe indépendant de la réponse de l'élève à la question en cours (« confirme », « contredit » ou
    None), à partir des paramètres recalculés depuis l'énoncé confirmé. Jamais l'avis de l'IA ; None si les simulations
    ne sont pas autorisées ou si la réponse ne se prête pas au contrôle."""
    if not simulations_activees():
        return None
    verdicts = set()
    for sim in etat.get("simulations", {}).get(str(etat["q"]), []):
        try:
            valide = valider_simulation(sim)
            modele = CATALOGUE[valide["modele"]]
            if modele.controler is not None:
                verdicts.add(modele.controler(valide["parametres"], texte))
        except (ParametresInvalides, KeyError):
            continue
    verdicts.discard(None)
    if "contredit" in verdicts:
        return "contredit"
    return "confirme" if verdicts == {"confirme"} else None


def publiques(etat: dict) -> list[dict]:
    """Simulations transmissibles MAINTENANT : celles des questions terminées, en version réduite, dans l'ordre des
    questions. Vide si les simulations ne sont pas autorisées (production) ou si rien n'est encore débloqué.

    Divulgation conditionnée à la PREUVE (étape 9.2.2) : une simulation RÉVÉLATRICE (qui montre un résultat calculé) n'est
    envoyée que si aucune étape de la question n'a été acceptée sans preuve ; c'est-à-dire seulement si les réponses ont
    été vérifiées (SymPy / Wolfram), confirmées par le contrôle déterministe indépendant, ou si la solution a été
    légitimement débloquée. Une simulation non révélatrice (points de l'énoncé, tracé demandé) part dès la fin."""
    if not simulations_activees():
        return []
    liste: list[dict] = []
    for rang, question in enumerate(etat["plan"]):
        if not question_terminee(etat, rang):
            continue
        sans_preuve = _sans_preuve(etat, rang)
        for simulation in etat.get("simulations", {}).get(str(rang), []):
            if sans_preuve and _revelatrice(simulation):
                continue
            projetee = projeter_pour_professeur(simulation)
            if projetee is not None:
                liste.append({"question": question["numero"] or str(rang + 1), "simulation": projetee})
    return liste
