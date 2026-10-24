"""
Séance de Professeur particulier : état TEMPORAIRE côté serveur.

L'état complet (plan avec les réponses attendues, indices donnés, tentatives,
erreurs, historique) vit dans le cache Django sous un identifiant aléatoire,
lié à l'élève, avec expiration (IA_PROF_SEANCE_SECONDES, glissante). Le
navigateur n'envoie JAMAIS d'historique ni de plan : seulement l'identifiant,
la dernière `version` qu'il a vue et le texte de sa réponse. Le plan (les
réponses) n'est jamais renvoyé : on ne révèle que l'étape atteinte, quand
l'élève la débloque.

Chaque action (répondre, indice, explication, solution, suivante) :
 1. recharge la séance, la vérifie (propriétaire, version, quotas) ;
 2. prend un verrou par séance → un double clic ou deux onglets ne déclenchent
    jamais deux appels IA : le second reçoit 409 ;
 3. n'écrit l'état qu'APRÈS le succès de l'action : une demande d'explication qui
    échoue côté IA ne consomme rien ; pour une réponse de l'élève, le verdict
    (SymPy) est acquis même si la rédaction du retour échoue — un texte neutre
    est alors donné et la tentative compte.

Limite connue : le cache par défaut de Django est local à chaque processus ;
avec plusieurs workers il faut un cache partagé (Redis…).
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
import secrets
import time

from django.conf import settings
from django.core.cache import cache

from ..ia.exceptions import IAErreur, IAReponseVide
from ..lecture_exercice import ContexteProgramme, normaliser_analyse
from ..correction.service import verifier_admissibilite
from ..correction.etude_fonction import etude_pour_affirmations
from . import plan as plan_module
from . import recevabilite, tour, visualisation
from .reponses import CORRECT, INCORRECT, NON_VERIFIABLE, LONGUEUR_MAX_REPONSE, Verdict, verifier_reponse

logger = logging.getLogger(__name__)

NB_INDICES = 3
# Déblocage de la solution : au moins deux tentatives RECEVABLES et distinctes (voir recevabilite.py) ET deux indices.
# Plus de raccourci « quatre réponses sans indice » : des envois arbitraires ne suffisent pas (étape 9.2.2).
TENTATIVES_SOLUTION, INDICES_SOLUTION = 2, 2
NOTE_NON_VERIFIE = "Je n'ai pas pu vérifier ce résultat automatiquement : je continue avec toi, mais je ne le valide pas."
NOTE_FIGURE_RETENUE = "La figure qui montre le résultat ne s'ouvrira que lorsque ce résultat aura été vérifié, ou après avoir vu la solution."
MESSAGE_CONTREDIT = ("Une valeur que tu as écrite ne correspond pas à ce qui est donné ou calculé à partir de l'énoncé. "
                     "Relis les données de l'énoncé, puis reprends ton calcul.")
MAX_MESSAGES = 160


class ProfesseurErreur(Exception):
    code = "erreur"
    statut_http = 400


class SeanceIntrouvable(ProfesseurErreur):
    code, statut_http = "seance_introuvable", 404


class SeanceOccupee(ProfesseurErreur):
    code, statut_http = "occupee", 409


class EtatObsolete(ProfesseurErreur):
    code, statut_http = "etat_obsolete", 409


class ActionRefusee(ProfesseurErreur):
    code, statut_http = "action_refusee", 400


class LimiteAtteinte(ProfesseurErreur):
    code, statut_http = "limite_atteinte", 429


class Desactive(ProfesseurErreur):
    code, statut_http = "professeur_desactive", 503


def professeur_actif() -> bool:
    if not settings.IA_PROF_ACTIVE:
        return False
    if settings.IA_PROF_DEV_SEULEMENT and not settings.DEBUG:
        return False
    return True


# --------------------------------------------------------------------------
#  Stockage
# --------------------------------------------------------------------------

def _cle(id_seance: str) -> str:
    return f"prof:seance:{id_seance}"


def _sauver(etat: dict) -> None:
    etat["expire_a"] = int(time.time()) + int(settings.IA_PROF_SEANCE_SECONDES)
    cache.set(_cle(etat["id"]), etat, timeout=int(settings.IA_PROF_SEANCE_SECONDES))


def charger(id_seance: str, utilisateur_id: int) -> dict:
    etat = cache.get(_cle(id_seance)) if isinstance(id_seance, str) and 10 <= len(id_seance) <= 80 else None
    # Même réponse « introuvable » pour une séance inexistante, expirée ou d'un autre élève.
    if etat is None or etat["user_id"] != utilisateur_id:
        raise SeanceIntrouvable("Cette séance n'existe plus ou a expiré. Recommence depuis ton exercice.")
    return copy.deepcopy(etat)


# --------------------------------------------------------------------------
#  Vue publique (aucun secret : ni plan, ni réponses attendues, ni solutions)
# --------------------------------------------------------------------------

def _etape(etat: dict, q: int | None = None, e: int | None = None) -> dict:
    return etat["plan"][etat["q"] if q is None else q]["etapes"][etat["e"] if e is None else e]


def _suivi(etat: dict, q: int | None = None, e: int | None = None) -> dict:
    return etat["etapes"][f"{etat['q'] if q is None else q}-{etat['e'] if e is None else e}"]


def solution_debloquee(suivi: dict) -> bool:
    return suivi["tentatives"] >= TENTATIVES_SOLUTION and suivi["indices"] >= INDICES_SOLUTION


def _conditions_solution(suivi: dict) -> str:
    if solution_debloquee(suivi):
        return ""
    manque_t = max(0, TENTATIVES_SOLUTION - suivi["tentatives"])
    manque_i = max(0, INDICES_SOLUTION - suivi["indices"])
    morceaux = []
    if manque_t:
        morceaux.append(f"{manque_t} tentative{'s' if manque_t > 1 else ''} de plus")
    if manque_i:
        morceaux.append(f"{manque_i} indice{'s' if manque_i > 1 else ''} de plus")
    return "Pour débloquer la solution de cette étape : " + " et ".join(morceaux) + " (une tentative = une réponse sérieuse, différente des précédentes)."


def _total_etapes(etat: dict) -> int:
    return sum(len(q["etapes"]) for q in etat["plan"])


def _terminees(etat: dict) -> int:
    return sum(1 for s in etat["etapes"].values() if s["statut"] != "en_cours")


def vue_publique(etat: dict) -> dict:
    q, e = etat["q"], etat["e"]
    question, etape, suivi = etat["plan"][q], _etape(etat), _suivi(etat)
    fini = etat["etape_terminee"] or etat["termine"]
    total = _total_etapes(etat)
    return {
        "seance": etat["id"],
        "version": etat["version"],
        "expire_a": etat.get("expire_a"),
        "termine": etat["termine"],
        "etape_terminee": etat["etape_terminee"] and not etat["termine"],
        "progression": {
            "question": q + 1, "nb_questions": len(etat["plan"]),
            "etape": e + 1, "nb_etapes_question": len(question["etapes"]),
            "etapes_terminees": _terminees(etat), "nb_etapes_total": total,
            "pourcentage": round(100 * _terminees(etat) / total) if total else 0,
        },
        "question": {"numero": question["numero"], "enonce": question["enonce"], "objectif": question["objectif"]},
        "etape": {
            "consigne": etape["consigne"],
            "indices_donnes": suivi["indices"], "indices_max": NB_INDICES,
            "tentatives": suivi["tentatives"],
            "solution_disponible": solution_debloquee(suivi) and not fini,
            "conditions_solution": "" if fini else _conditions_solution(suivi),
            "verifiable": etape["reference"] == "verifiee" and etape["attendu"] is not None,
        },
        "actions": {
            "repondre": not fini,
            "indice": not fini and suivi["indices"] < NB_INDICES,
            "explication": not etat["termine"],
            "solution": not fini and solution_debloquee(suivi),
            "suivante": etat["etape_terminee"] and not etat["termine"],
        },
        "messages": etat["messages"],
        # Pas de courbe ni de tableau avant la fin : ils donneraient les réponses des questions à venir.
        "etudes": etat.get("etudes", []) if etat["termine"] else [],
        # Simulations GeoGebra : seulement celles des questions terminées, en version réduite (voir visualisation.py).
        "simulations": visualisation.publiques(etat),
        "echanges_restants": max(0, int(settings.IA_PROF_MAX_ECHANGES) - etat["nb_actions"]),
    }


# --------------------------------------------------------------------------
#  Messages
# --------------------------------------------------------------------------

def _ajouter(etat: dict, role: str, texte: str, type_: str, **extra) -> dict:
    message = {"id": len(etat["messages"]) + 1, "role": role, "texte": texte, "type": type_,
               "q": etat["q"], "e": etat["e"], "verification": extra.pop("verification", None), "niveau": extra.pop("niveau", None)}
    message.update(extra)
    etat["messages"].append(message)
    if len(etat["messages"]) > MAX_MESSAGES:
        del etat["messages"][: len(etat["messages"]) - MAX_MESSAGES]
    return message


def _intro_etape(etat: dict) -> str:
    question, etape = etat["plan"][etat["q"]], _etape(etat)
    if etat["e"] == 0:
        entete = f"**Question {question['numero']}** — {question['enonce']}\n\n"
        if question["objectif"]:
            entete += f"*Ce qu'on cherche :* {question['objectif']}\n\n"
        return entete + etape["consigne"]
    return etape["consigne"]


def _suivi_neuf() -> dict:
    # `tentatives` ne compte que les réponses RECEVABLES et distinctes ; `cles` : leurs formes normalisées ; `preuve` :
    # ce qui a clos l'étape (« calcul » SymPy, « controle » indépendant, « solution », « avis_ia » = non vérifiée).
    return {"tentatives": 0, "irrecevables": 0, "cles": [], "indices": 0, "reponses": [], "erreurs": [], "statut": "en_cours", "preuve": ""}


# --------------------------------------------------------------------------
#  Démarrage
# --------------------------------------------------------------------------

def _empreinte(analyse: dict) -> str:
    utile = {k: analyse[k] for k in ("enonce", "donnees", "formules", "questions", "tableaux", "figures")}
    return hashlib.sha256(json.dumps(utile, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _quota_creation(utilisateur_id: int) -> None:
    cle = f"prof:quota:{utilisateur_id}"
    cache.add(cle, 0, timeout=3600)
    try:
        n = cache.incr(cle)
    except ValueError:  # expirée entre-temps
        cache.set(cle, 1, timeout=3600)
        n = 1
    if n > int(settings.IA_PROF_MAX_SEANCES_PAR_HEURE):
        raise LimiteAtteinte("Tu as lancé beaucoup de séances en peu de temps. Réessaie dans une heure ou reprends ta séance en cours.")


def _etudes_du_plan(questions: list[dict]) -> list[dict]:
    """Courbe et tableau de variations des questions d'extrema/variations, calculés par SymPy. SECRET de
    séance : ils révèlent les réponses (extrema, sens de variation), donc `vue_publique` ne les montre
    qu'une fois l'exercice entièrement terminé."""
    etudes = []
    for q in questions:
        etude = etude_pour_affirmations([e["affirmation"] for e in q["etapes"] if e.get("affirmation")])
        if etude is not None:
            etudes.append({"question": q["numero"], "etude": etude})
    return etudes


def demarrer(*, utilisateur_id: int, programme_id: int, contexte: ContexteProgramme, analyse_brute: dict) -> dict:
    """Crée (ou reprend) la séance de cet énoncé confirmé. Renvoie l'état interne (pas la vue publique)."""
    analyse = normaliser_analyse(analyse_brute, contexte)
    verifier_admissibilite(analyse, contexte.matiere)  # mêmes refus que la correction complète
    empreinte = _empreinte(analyse)

    # Séance déjà ouverte pour ce même énoncé : on la reprend, sans nouvel appel payant.
    cle_courante = f"prof:courante:{utilisateur_id}:{programme_id}:{empreinte}"
    existante = cache.get(cle_courante)
    if existante:
        try:
            etat = charger(existante, utilisateur_id)
            if not etat["termine"]:
                etat["reprise"] = True
                return etat
        except SeanceIntrouvable:
            pass

    cle_verrou = f"prof:verrou_plan:{utilisateur_id}:{empreinte}"
    if not cache.add(cle_verrou, 1, timeout=int(settings.IA_PROF_TIMEOUT_SECONDES) + int(settings.WOLFRAM_TIMEOUT_SECONDES) * 4 + 30):
        raise SeanceOccupee("Ta séance est déjà en cours de préparation. Patiente quelques secondes, sans renvoyer.")
    try:
        _quota_creation(utilisateur_id)
        cle_plan = f"prof:plan:{empreinte}"
        en_cache = cache.get(cle_plan)
        jetons = {"tokens_entree": 0, "tokens_sortie": 0}
        appels = 0
        if en_cache is not None:
            questions = copy.deepcopy(en_cache)
        else:
            brut, usage = plan_module.generer_plan_brut(analyse, f"{contexte.matiere}, {contexte.classe}")
            appels = 1
            jetons = {"tokens_entree": usage.get("tokens_entree") or 0, "tokens_sortie": usage.get("tokens_sortie") or 0}
            questions, resume = plan_module.preparer_plan(brut)
            if not questions:
                raise IAReponseVide("Le plan de la séance est vide.")
            logger.info("professeur plan questions=%s resume=%s", len(questions), resume)
            cache.set(cle_plan, copy.deepcopy(questions), timeout=int(settings.IA_PROF_PLAN_CACHE_SECONDES))

        etat = {
            "id": secrets.token_urlsafe(24), "user_id": utilisateur_id, "programme_id": programme_id, "version": 1,
            "contexte": {"matiere": contexte.matiere, "classe": contexte.classe, "enonce": analyse["enonce"] or "\n".join(q["texte"] for q in analyse["questions"])},
            "plan": questions, "q": 0, "e": 0,
            "etapes": {f"{qi}-{ei}": _suivi_neuf() for qi, q in enumerate(questions) for ei in range(len(q["etapes"]))},
            "messages": [], "termine": False, "etape_terminee": False,
            "etudes": _etudes_du_plan(questions),
            "simulations": visualisation.preparer(analyse, contexte.matiere, questions),  # SECRET de séance, comme le plan
            "nb_appels_ia": appels, "nb_actions": 0, "jetons": jetons, "reprise": False,
        }
        _ajouter(etat, "prof", "Bonjour ! Je vais t'accompagner pas à pas. Je ne te donnerai pas les réponses : "
                             "tu cherches, tu te trompes si besoin, et on comprend ensemble. Allons-y !", "intro")
        _ajouter(etat, "prof", _intro_etape(etat), "consigne")
        _sauver(etat)
        cache.set(cle_courante, etat["id"], timeout=int(settings.IA_PROF_SEANCE_SECONDES))
        return etat
    finally:
        cache.delete(cle_verrou)


# --------------------------------------------------------------------------
#  Actions
# --------------------------------------------------------------------------

class _Action:
    """Contexte d'une action : charge, verrouille, contrôle la version et les quotas ; écrit à la sortie si tout s'est bien passé."""

    def __init__(self, id_seance: str, utilisateur_id: int, version: int):
        self.id, self.utilisateur_id, self.version = id_seance, utilisateur_id, version
        self.etat: dict = {}
        self._verrou = f"prof:verrou:{id_seance}"
        self._pris = False

    def __enter__(self) -> "_Action":
        self.etat = charger(self.id, self.utilisateur_id)
        if not cache.add(self._verrou, 1, timeout=int(settings.IA_PROF_TIMEOUT_SECONDES) + 30):
            raise SeanceOccupee("Une action est déjà en cours pour cette séance. Patiente un instant.")
        self._pris = True
        try:
            self.etat = charger(self.id, self.utilisateur_id)  # relu sous verrou
            if self.etat["version"] != self.version:
                raise EtatObsolete("Ta séance a avancé entre-temps : l'écran est mis à jour.")
            if self.etat["nb_actions"] >= int(settings.IA_PROF_MAX_ECHANGES):
                raise LimiteAtteinte("Cette séance est arrivée à sa limite d'échanges. Relance une séance depuis ton exercice.")
        except BaseException:
            # Une exception dans __enter__ ne passe pas par __exit__ : sans cela, une requête périmée
            # (double clic, deux onglets) laisserait la séance verrouillée plusieurs minutes.
            cache.delete(self._verrou)
            self._pris = False
            raise
        return self

    def valider(self) -> dict:
        self.etat["version"] += 1
        self.etat["nb_actions"] += 1
        _sauver(self.etat)
        return self.etat

    def __exit__(self, *_exc) -> None:
        if self._pris:
            cache.delete(self._verrou)


def _verifier_ouverte(etat: dict) -> None:
    if etat["termine"]:
        raise ActionRefusee("Cet exercice est terminé.")
    if etat["etape_terminee"]:
        raise ActionRefusee("Cette étape est terminée : passe à l'étape suivante.")


def _contexte_etape(etat: dict) -> str:
    """Textes de la question et de l'étape en cours (serveur seulement) : sert à reconnaître une réponse hors sujet."""
    question, etape = etat["plan"][etat["q"]], _etape(etat)
    return " ".join([question["enonce"], question["objectif"], etape["consigne"], etape["solution"], *etape["indices"]])


def _appeler_tour(etat: dict, **kwargs) -> tuple[dict | None, dict]:
    """Un appel court au professeur ; (None, {}) si le budget d'appels de la séance est épuisé."""
    if etat["nb_appels_ia"] >= int(settings.IA_PROF_MAX_APPELS_IA):
        return None, {}
    etape, suivi = _etape(etat), _suivi(etat)
    message = tour.construire_message(
        contexte=etat["contexte"], etape=etape, question=etat["plan"][etat["q"]], etat_etape=suivi,
        messages=etat["messages"], **kwargs,
    )
    brut, usage = tour.appeler_tour(message)
    etat["nb_appels_ia"] += 1
    etat["jetons"]["tokens_entree"] += usage.get("tokens_entree") or 0
    etat["jetons"]["tokens_sortie"] += usage.get("tokens_sortie") or 0
    return tour.normaliser_tour(brut), usage


def repondre(id_seance: str, utilisateur_id: int, version: int, texte: str) -> dict:
    texte = (texte or "").strip()
    if not texte:
        raise ActionRefusee("Écris ta réponse avant de l'envoyer.")
    if len(texte) > LONGUEUR_MAX_REPONSE:
        raise ActionRefusee(f"Ta réponse est trop longue ({LONGUEUR_MAX_REPONSE} caractères maximum).")
    with _Action(id_seance, utilisateur_id, version) as action:
        etat = action.etat
        _verifier_ouverte(etat)
        etape, suivi = _etape(etat), _suivi(etat)
        attendu = etape["attendu"] if etape["reference"] == "verifiee" else None
        verdict = verifier_reponse(attendu, texte)

        _ajouter(etat, "eleve", texte, "reponse")
        if verdict.statut != CORRECT:
            # Recevabilité déterministe (sans IA) : un envoi vide, répété, copié de la consigne ou hors sujet n'est pas une
            # tentative (il ne fait pas avancer le déblocage de la solution) et ne déclenche aucun appel IA.
            motif = recevabilite.evaluer(texte, etape["consigne"], _contexte_etape(etat), suivi.setdefault("cles", []))
            if motif:
                suivi["irrecevables"] = suivi.get("irrecevables", 0) + 1
                if attendu is not None and motif in (recevabilite.HORS_SUJET, recevabilite.INUTILISABLE):
                    # Étape vérifiable et texte illisible : on rappelle le format attendu (retour gratuit habituel).
                    _ajouter(etat, "prof", tour.message_reponse_illisible(verdict.detail), "retour", verification="illisible")
                else:
                    _ajouter(etat, "prof", recevabilite.message(motif, suivi["irrecevables"]), "retour")
                return action.valider() and etat
        suivi["tentatives"] += 1
        suivi["cles"] = (suivi.get("cles", []) + [recevabilite.cle(texte)])[-30:]
        suivi["reponses"] = (suivi["reponses"] + [texte[:300]])[-5:]

        # Contrôle déterministe INDÉPENDANT (étape 9.2.2), hors étapes déjà vérifiées par SymPy : les coordonnées écrites
        # sont comparées à celles recalculées depuis l'énoncé confirmé. Il confirme ou contredit ; jamais l'avis de l'IA.
        controle = visualisation.controler_reponse(etat, texte) if verdict.statut != CORRECT and etape["reference"] != "verifiee" else None
        if controle == "confirme":
            suivi["statut"], suivi["preuve"] = "reussie", "controle"
            etat["etape_terminee"] = True
            _ajouter(etat, "prof", etape["message_reussite"], "reussite", verification="verifiee")
            return action.valider() and etat
        if controle == "contredit":
            suivi["erreurs"] = (suivi["erreurs"] + [{"type": "calcul", "resume": "Réponse contredite par le contrôle indépendant."}])[-6:]
            _ajouter(etat, "prof", MESSAGE_CONTREDIT, "retour", verification="verifiee", type_erreur="calcul")
            return action.valider() and etat

        if etape["reference"] == "contredite":
            verification = "incertaine"
        elif verdict.statut == NON_VERIFIABLE and attendu is None:
            verification = "non_verifiable"
        elif verdict.statut == NON_VERIFIABLE:
            verification = "illisible"
        else:
            verification = "verifiee"

        if verdict.statut == CORRECT:
            suivi["statut"], suivi["preuve"] = "reussie", "calcul"
            etat["etape_terminee"] = True
            _ajouter(etat, "prof", etape["message_reussite"], "reussite", verification="verifiee")
            return action.valider() and etat

        if verification == "illisible":  # réponse non lisible : retour gratuit, sans appel IA
            _ajouter(etat, "prof", tour.message_reponse_illisible(verdict.detail), "retour", verification="illisible")
            return action.valider() and etat

        resultat, _ = None, None
        try:
            resultat, _ = _appeler_tour(etat, texte_eleve=texte, verdict=verdict, demande=None)
        except IAErreur as exc:
            logger.warning("professeur : retour IA indisponible (%s)", type(exc).__name__)
        if resultat is None:
            message, type_erreur, resume, evaluation = tour.message_de_secours(verdict, None), verdict.erreur_probable or "non_precise", "", "non_applicable"
        else:
            message, type_erreur, resume, evaluation = resultat["message"] or tour.message_de_secours(verdict, None), resultat["type_erreur"], resultat["resume_erreur"], resultat["evaluation"]
        message, fuite = tour.filtrer_fuite(message, attendu, verdict, ignorer=[texte])
        if fuite:
            logger.warning("professeur : fuite de la réponse attendue détectée, message remplacé")

        if verdict.statut == INCORRECT:
            if type_erreur == "aucune":
                type_erreur = verdict.erreur_probable or "non_precise"
            suivi["erreurs"] = (suivi["erreurs"] + [{"type": type_erreur, "resume": resume or verdict.diagnostic or "Réponse différente de celle attendue."}])[-6:]
            _ajouter(etat, "prof", message, "retour", verification="verifiee", type_erreur=type_erreur)
        else:  # étape sans calcul vérifiable (ou référence incertaine) : aucun « juste » affirmé par le seul avis de l'IA
            if evaluation == "plausible" and not fuite and etape["reference"] != "contredite":
                # On laisse l'élève PROGRESSER, sans prétendre que c'est vérifié : statut « non vérifiée », signalé clairement.
                # Ce statut ne suffit jamais à dévoiler un résultat (voir visualisation.publiques).
                suivi["statut"], suivi["preuve"] = "reussie_non_verifiee", "avis_ia"
                etat["etape_terminee"] = True
                if etape["reference"] == "non_verifiee":  # un calcul était attendu mais n'a pas pu être confirmé
                    message += "\n\n" + NOTE_NON_VERIFIE
                if visualisation.a_une_simulation_revelatrice(etat, etat["q"]):
                    message += "\n\n" + NOTE_FIGURE_RETENUE
            _ajouter(etat, "prof", message, "retour", verification=verification)
        action.valider()
        return etat


def indice(id_seance: str, utilisateur_id: int, version: int) -> dict:
    with _Action(id_seance, utilisateur_id, version) as action:
        etat = action.etat
        _verifier_ouverte(etat)
        etape, suivi = _etape(etat), _suivi(etat)
        if suivi["indices"] >= NB_INDICES:
            raise ActionRefusee("Tu as déjà reçu les trois indices de cette étape. " + (
                "Tu peux maintenant voir la solution de cette étape." if solution_debloquee(suivi) else _conditions_solution(suivi) or "Essaie de répondre."))
        niveau = suivi["indices"] + 1
        suivi["indices"] = niveau
        _ajouter(etat, "eleve", "Besoin d'un indice", "demande_indice")
        _ajouter(etat, "prof", etape["indices"][niveau - 1], "indice", niveau=niveau)
        return action.valider() and etat


def explication(id_seance: str, utilisateur_id: int, version: int, type_demande: str, texte: str = "") -> dict:
    if type_demande not in tour.TYPES_DEMANDE:
        raise ActionRefusee("Type de demande inconnu.")
    texte = (texte or "").strip()
    if type_demande == "question" and not texte:
        raise ActionRefusee("Écris ta question avant de l'envoyer.")
    if len(texte) > LONGUEUR_MAX_REPONSE:
        raise ActionRefusee(f"Ta question est trop longue ({LONGUEUR_MAX_REPONSE} caractères maximum).")
    libelles = {"incomprehension": "Je n'ai pas compris.", "autre_explication": "Peux-tu expliquer autrement ?",
                "exemple": "Donne-moi un exemple plus simple.", "pourquoi": "Pourquoi utilise-t-on cette formule ?", "question": texte}
    with _Action(id_seance, utilisateur_id, version) as action:
        etat = action.etat
        if etat["termine"]:
            raise ActionRefusee("Cet exercice est terminé.")
        if etat["nb_appels_ia"] >= int(settings.IA_PROF_MAX_APPELS_IA):
            raise LimiteAtteinte("Cette séance a atteint sa limite d'explications. Relance une séance depuis ton exercice.")
        etape = _etape(etat)
        attendu = etape["attendu"] if etape["reference"] == "verifiee" and not etat["etape_terminee"] else None
        resultat, _ = _appeler_tour(etat, texte_eleve=texte if type_demande == "question" else libelles[type_demande] + (f" {texte}" if texte else ""),
                                    verdict=None, demande=type_demande)  # une erreur IA remonte : rien n'est consommé
        message = resultat["message"] or tour.message_de_secours(None, type_demande)
        message, fuite = tour.filtrer_fuite(message, attendu, ignorer=[texte], explication=True)
        if fuite:
            logger.warning("professeur : fuite de la réponse attendue détectée (explication), message remplacé")
        _ajouter(etat, "eleve", libelles[type_demande], "demande_explication")
        _ajouter(etat, "prof", message, "explication")
        return action.valider() and etat


def solution(id_seance: str, utilisateur_id: int, version: int) -> dict:
    with _Action(id_seance, utilisateur_id, version) as action:
        etat = action.etat
        _verifier_ouverte(etat)
        etape, suivi = _etape(etat), _suivi(etat)
        if not solution_debloquee(suivi):
            raise ActionRefusee(_conditions_solution(suivi))
        suivi["statut"], suivi["preuve"] = "solution_vue", "solution"
        etat["etape_terminee"] = True
        texte = etape["solution"] or "La solution détaillée de cette étape n'est pas disponible."
        if etape["note_reference"]:
            texte += f"\n\n*{etape['note_reference']}*"
        _ajouter(etat, "eleve", "Voir la solution de cette étape", "demande_solution")
        _ajouter(etat, "prof", "Voici la solution de **cette étape** (pas de l'exercice entier) :\n\n" + texte, "solution",
                 verification="verifiee" if etape["reference"] == "verifiee" else "non_verifiable")
        return action.valider() and etat


def _recapitulatif(etat: dict) -> str:
    stats = {"seul": 0, "aide": 0, "solution": 0, "non_verifiee": 0}
    erreurs: dict[str, int] = {}
    for suivi in etat["etapes"].values():
        if suivi["statut"] == "solution_vue":
            stats["solution"] += 1
        elif suivi["statut"] == "reussie_non_verifiee":
            stats["non_verifiee"] += 1
        elif suivi["indices"] or suivi["tentatives"] > 1:
            stats["aide"] += 1
        else:
            stats["seul"] += 1
        for err in suivi["erreurs"]:
            erreurs[err["type"]] = erreurs.get(err["type"], 0) + 1
    lignes = ["**Exercice terminé, bravo pour ton travail !**", ""]
    lignes.append(f"- Étapes réussies du premier coup : {stats['seul']}")
    lignes.append(f"- Étapes réussies avec indices ou après une erreur : {stats['aide']}")
    if stats["solution"]:
        lignes.append(f"- Étapes dont tu as vu la solution : {stats['solution']} (revois-les à tête reposée)")
    if stats["non_verifiee"]:
        lignes.append(f"- Étapes dont la réponse n'a pas pu être vérifiée automatiquement : {stats['non_verifiee']}")
    if erreurs:
        noms = {"calcul": "erreurs de calcul", "raisonnement": "erreurs de raisonnement", "notation": "erreurs de notation", "incomplet": "réponses incomplètes", "non_precise": "autres erreurs"}
        lignes.append("- À retravailler : " + ", ".join(f"{n} {noms.get(t, t)}" for t, n in sorted(erreurs.items())))
    return "\n".join(lignes)


def suivante(id_seance: str, utilisateur_id: int, version: int) -> dict:
    with _Action(id_seance, utilisateur_id, version) as action:
        etat = action.etat
        if etat["termine"]:
            raise ActionRefusee("Cet exercice est terminé.")
        if not etat["etape_terminee"]:
            raise ActionRefusee("Termine d'abord cette étape (ou vois sa solution) avant de passer à la suivante.")
        question = etat["plan"][etat["q"]]
        if etat["e"] + 1 < len(question["etapes"]):
            etat["e"] += 1
        elif etat["q"] + 1 < len(etat["plan"]):
            etat["q"], etat["e"] = etat["q"] + 1, 0
        else:
            etat["termine"] = True
            _ajouter(etat, "prof", _recapitulatif(etat), "fin")
            return action.valider() and etat
        etat["etape_terminee"] = False
        _ajouter(etat, "prof", _intro_etape(etat), "consigne")
        return action.valider() and etat
