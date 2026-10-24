"""
Correction complète d'un exercice de mathématiques (étape 6, pilote).

Chaîne : énoncé CONFIRMÉ (texte) → Anthropic rédige la résolution et déclare
ses calculs vérifiables → SymPy puis Wolfram Alpha les recalculent
indépendamment → on compare, on détecte les contradictions, on structure.

Honnêteté de la vérification (règle centrale) :
- seuls les calculs DÉCLARÉS et pris en charge sont contrôlés ; la rédaction,
  le choix de la méthode et les théorèmes invoqués ne le sont pas. Le statut
  global ne dit donc JAMAIS « démonstration vérifiée » : au mieux
  « calculs_verifies », avec la mention explicite de ce qui reste à relire ;
- une contradiction (IA ≠ SymPy, IA ≠ Wolfram) prime sur tout le reste ;
- ce qui n'a pas pu être contrôlé est marqué « non_verifie », jamais « ok ».

Coûts : désactivé par défaut (IA_CORRECTION_ACTIVE), réservé à DEBUG tant que
IA_CORRECTION_DEV_SEULEMENT est vrai ; un seul appel Anthropic sans retry ;
même énoncé redemandé → cache (aucun nouvel appel payant) ; même énoncé en
cours → refusé (verrou). Les photos ne sont pas concernées : l'énoncé confirmé
est du texte, la lecture des documents n'est pas rappelée.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from ..ia.exceptions import IAErreur
from ..lecture_exercice import ContexteProgramme, cle_matiere, normaliser_analyse
from ..simulations.selection import question_confirmee, sources_enonce
from . import concordance, resolution
from .etude_fonction import etude_pour_affirmations
from .verification import CONTRADICTION, INDISPONIBLE, OK, verifier_avec_sympy
from .wolfram import verifier_avec_wolfram

logger = logging.getLogger(__name__)

MAX_REQUETES_WOLFRAM = 15

AVERTISSEMENT_PORTEE = (
    "Seuls les calculs listés dans « Contrôles automatiques » ont été recalculés par SymPy et/ou Wolfram Alpha. "
    "Le raisonnement, le choix des méthodes et la rédaction n'ont pas été vérifiés automatiquement : relis-les."
)

LIBELLE_STATUT = {
    "contradiction": "Contradiction détectée : ne te fie pas à cette correction sans la vérifier.",
    "calculs_verifies": "Les calculs déclarés ont été contrôlés automatiquement (le raisonnement reste à relire).",
    "partiellement_verifiee": "Vérification partielle : certains calculs n'ont pas pu être contrôlés.",
    "non_verifiee": "Aucun calcul n'a pu être contrôlé automatiquement : correction non vérifiée.",
}


class CorrectionRefusee(IAErreur):
    """L'énoncé ne peut pas être corrigé automatiquement (illisible, figure non interprétée, hors maths…)."""


class CorrectionDejaEnCours(IAErreur):
    """La même correction est déjà en cours de production."""


@dataclass
class ResultatCorrection:
    correction: dict
    depuis_cache: bool
    modele: str | None = None
    tokens_entree: int | None = None
    tokens_sortie: int | None = None


def correction_activee() -> bool:
    if not settings.IA_CORRECTION_ACTIVE:
        return False
    if settings.IA_CORRECTION_DEV_SEULEMENT and not settings.DEBUG:
        return False
    return True


# --- Admissibilité ----------------------------------------------------------

def verifier_admissibilite(analyse: dict, matiere_programme: str) -> None:
    """Lève CorrectionRefusee (message français) si l'exercice ne doit PAS être résolu automatiquement."""
    if cle_matiere(matiere_programme) != "mathematiques":
        raise CorrectionRefusee("La correction complète n'est disponible que pour les mathématiques.")
    if not analyse["lisible"]:
        raise CorrectionRefusee("Cet exercice n'a pas été lu correctement : reprends une photo plus nette avant de demander la correction.")
    if analyse["concordance_programme"] == "differente":
        raise CorrectionRefusee("Cet exercice ne semble pas être un exercice de mathématiques : la correction n'est pas lancée.")
    if analyse["parties_incertaines"] or any(q["incertain"] for q in analyse["questions"]):
        raise CorrectionRefusee(
            "Des passages de l'énoncé sont signalés comme incertains : corrige la lecture (« Signaler une erreur de lecture ») "
            "avant de demander la correction."
        )
    if any(not f["exploitable"] for f in analyse["figures"]):
        raise CorrectionRefusee(
            "Une figure indispensable n'a pas pu être interprétée : la correction automatique n'est pas lancée "
            "pour éviter une réponse inventée."
        )
    if not analyse["questions"] and not analyse["enonce"]:
        raise CorrectionRefusee("L'énoncé est vide : il n'y a rien à corriger.")


# --- Vérification -----------------------------------------------------------

def _combiner(verdict_sympy, verdict_wolfram, wolfram_interroge: bool) -> dict:
    methodes = [{"nom": "SymPy", "statut": verdict_sympy.statut, "detail": verdict_sympy.detail}]
    if wolfram_interroge or verdict_wolfram.statut != INDISPONIBLE:
        methodes.append({"nom": "Wolfram Alpha", "statut": verdict_wolfram.statut, "detail": verdict_wolfram.detail})
    statuts = {verdict_sympy.statut, verdict_wolfram.statut}
    if CONTRADICTION in statuts:
        statut = "contradiction"
    elif OK in statuts:
        statut = "verifie"
    else:
        statut = "non_verifie"
    return {
        "statut": statut,
        "methodes": methodes,
        "desaccord_methodes": CONTRADICTION in statuts and OK in statuts,
    }


def verifier_correction(brute: dict) -> dict:
    """Contrôle chaque affirmation et assemble la correction finale (structure renvoyée à l'élève)."""
    requetes_wolfram = 0
    questions = []
    total = {"verifie": 0, "contradiction": 0, "non_verifie": 0}

    for q in brute["questions"]:
        controles = []
        for numero, affirmation in enumerate(q["affirmations"], start=1):
            sympy_v = verifier_avec_sympy(affirmation)
            if requetes_wolfram < MAX_REQUETES_WOLFRAM:
                wolfram_v, interroge = verifier_avec_wolfram(affirmation)
                requetes_wolfram += 1 if interroge else 0
            else:
                from .verification import VerdictMethode
                wolfram_v, interroge = VerdictMethode(INDISPONIBLE, "Limite de requêtes Wolfram Alpha atteinte pour cette correction."), False
            controle = _combiner(sympy_v, wolfram_v, interroge)
            controle.update({"id": f"{q['numero'] or len(questions) + 1}-{numero}", "type": affirmation["type"], "description": affirmation["description"]})
            total[controle["statut"]] += 1
            controles.append(controle)

        statuts = [c["statut"] for c in controles]
        if "contradiction" in statuts:
            statut_q = "contradiction"
        elif controles and all(s == "verifie" for s in statuts) and q["resultat"] and not q["incertitudes"]:
            statut_q = "verifiee"
        elif "verifie" in statuts:
            statut_q = "partiellement_verifiee"
        else:
            statut_q = "non_verifiee"
        etude = etude_pour_affirmations(q["affirmations"])  # tableau/courbe : calculés par SymPy, jamais repris de l'IA
        if etude is not None and etude["statut"] == "verifie":
            etude["contredit_par_la_correction"] = any(
                c["statut"] == "contradiction" and c["type"] in ("extrema", "variations") for c in controles
            )
        questions.append({
            "numero": q["numero"], "enonce": q["enonce"], "etapes": q["etapes"], "resultat": q["resultat"],
            "incertitudes": q["incertitudes"], "statut": statut_q, "controles": controles, "etude_fonction": etude,
        })

    avertissements = [AVERTISSEMENT_PORTEE] + list(brute["incertitudes_generales"])
    statuts_q = [q["statut"] for q in questions]
    if not questions:
        statut = "non_verifiee"
        avertissements.append("Aucune question n'a été traitée dans la correction.")
    elif "contradiction" in statuts_q:
        statut = "contradiction"
    elif all(s == "verifiee" for s in statuts_q) and not brute["incertitudes_generales"]:
        statut = "calculs_verifies"
    elif any(s in ("verifiee", "partiellement_verifiee") for s in statuts_q):
        statut = "partiellement_verifiee"
    else:
        statut = "non_verifiee"

    for q in questions:
        if q["statut"] == "contradiction":
            avertissements.append(f"Question {q['numero']} : le contrôle automatique contredit la correction proposée.")
        elif q["statut"] == "non_verifiee":
            avertissements.append(f"Question {q['numero']} : aucun calcul n'a pu être contrôlé automatiquement.")

    return {
        "statut": statut,
        "libelle_statut": LIBELLE_STATUT[statut],
        "resume_verification": {
            "controles": sum(total.values()),
            "verifies": total["verifie"],
            "contradictions": total["contradiction"],
            "non_verifies": total["non_verifie"],
            "requetes_wolfram": requetes_wolfram,
        },
        "donnees": brute["donnees"],
        "formules": brute["formules"],
        "questions": questions,
        "conclusion": brute["conclusion"],
        "avertissements": avertissements,
    }


def _marquer_questions_manquantes(correction: dict, analyse: dict) -> None:
    traitees = {q["numero"].strip().rstrip(".)") for q in correction["questions"]}
    attendues = [q["numero"].strip().rstrip(".)") for q in analyse["questions"] if q["numero"].strip()]
    manquantes = [n for n in attendues if n not in traitees]
    if manquantes:
        correction["avertissements"].append(
            "Questions de l'énoncé non traitées par la correction : " + ", ".join(manquantes) + "."
        )
        if correction["statut"] == "calculs_verifies":
            correction["statut"] = "partiellement_verifiee"
            correction["libelle_statut"] = LIBELLE_STATUT["partiellement_verifiee"]


# --- Concordance réponse rédigée / résultat calculé --------------------------

def _appliquer_concordances(correction: dict, analyse: dict) -> None:
    """Ajoute `concordance` aux questions prises en charge (réponse rédigée comparée au résultat CALCULÉ à partir
    de l'énoncé confirmé) et répercute le verdict : une contradiction prime sur tout ; une concordance non vérifiée
    empêche une question de passer « vérifiée ». Une simulation n'y change rien. Une erreur interne laisse la
    correction intacte : la concordance est un contrôle supplémentaire, jamais une condition de livraison."""
    try:
        sources = sources_enonce(analyse)
        questions = correction["questions"]
        degradee = False
        for index, q in enumerate(questions):
            texte = question_confirmee(analyse, index, q["numero"], len(questions))
            verdict = concordance.concordance_question(sources, texte, q["resultat"])
            if verdict is None:
                continue
            q["concordance"] = verdict
            if verdict["statut"] == concordance.CONTRADICTION:
                q["statut"] = "contradiction"
                correction["avertissements"].append(
                    f"Question {q['numero']} : la réponse rédigée ne concorde pas avec le résultat calculé. {verdict['detail']}"
                )
            elif verdict["statut"] == concordance.NON_VERIFIEE:
                correction["avertissements"].append(
                    f"Question {q['numero']} : concordance non vérifiée entre la réponse rédigée et le résultat calculé."
                )
                if q["statut"] == "verifiee":
                    q["statut"] = "partiellement_verifiee"
                    degradee = True
        if any(q["statut"] == "contradiction" for q in questions):
            correction["statut"] = "contradiction"
        elif degradee and correction["statut"] == "calculs_verifies":
            correction["statut"] = "partiellement_verifiee"
        correction["libelle_statut"] = LIBELLE_STATUT[correction["statut"]]
    except Exception:  # noqa: BLE001 — la correction doit toujours être livrée
        logger.exception("concordance abandonnée")


# --- Orchestration ----------------------------------------------------------

def _empreinte(utilisateur_id: int, programme_id: int, analyse: dict) -> str:
    utile = {k: analyse[k] for k in ("enonce", "donnees", "formules", "questions", "tableaux", "figures")}
    canonique = json.dumps(utile, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(f"u{utilisateur_id}|p{programme_id}|{canonique}".encode()).hexdigest()


def corriger_exercice(
    *, utilisateur_id: int, programme_id: int, contexte: ContexteProgramme, analyse_brute: dict
) -> ResultatCorrection:
    analyse = normaliser_analyse(analyse_brute, contexte)
    verifier_admissibilite(analyse, contexte.matiere)

    empreinte = _empreinte(utilisateur_id, programme_id, analyse)
    cle_cache, cle_verrou = f"correction:resultat:{empreinte}", f"correction:verrou:{empreinte}"

    en_cache = cache.get(cle_cache)
    if en_cache is not None:
        return ResultatCorrection(correction=en_cache, depuis_cache=True)

    verrou = int(settings.IA_CORRECTION_TIMEOUT_SECONDES) + int(settings.WOLFRAM_TIMEOUT_SECONDES) * 4 + 30
    if not cache.add(cle_verrou, 1, timeout=verrou):
        raise CorrectionDejaEnCours("Cette correction est déjà en cours de préparation. Patiente quelques secondes, sans renvoyer.")

    try:
        modele = settings.IA_CORRECTION_MODELE or settings.IA_MODELE
        message = resolution.construire_message(analyse, f"{contexte.matiere}, {contexte.classe}")
        brut, usage = resolution._appeler_anthropic(modele=modele, message=message)
        correction = verifier_correction(resolution.normaliser_correction(brut))
        _marquer_questions_manquantes(correction, analyse)
        _appliquer_concordances(correction, analyse)
        logger.info(
            "correction exercice statut=%s controles=%s requetes_wolfram=%s tokens_entree=%s tokens_sortie=%s",
            correction["statut"], correction["resume_verification"]["controles"],
            correction["resume_verification"]["requetes_wolfram"], usage.get("tokens_entree"), usage.get("tokens_sortie"),
        )
        cache.set(cle_cache, correction, timeout=int(settings.IA_CORRECTION_CACHE_SECONDES))
        return ResultatCorrection(
            correction=correction, depuis_cache=False, modele=modele,
            tokens_entree=usage.get("tokens_entree"), tokens_sortie=usage.get("tokens_sortie"),
        )
    finally:
        cache.delete(cle_verrou)
