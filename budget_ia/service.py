"""
Contrôle des dépenses Anthropic : réservation atomique AVANT l'appel, décompte réel APRÈS.

Principe (tout en PostgreSQL, rien dans le cache ni dans React) :

  1. `ouvrir()` : dans UNE transaction, verrouille la ligne de l'élève puis la ligne du budget du mois
     (`select_for_update`), applique les quotas, vérifie que « dépensé + réservé + coût maximal de CETTE opération »
     reste sous le seuil opérationnel, puis RÉSERVE ce coût maximal et crée l'opération. Deux requêtes simultanées
     passent l'une après l'autre : le plafond ne peut pas être dépassé par concurrence.
  2. L'appel Anthropic a lieu (voir `appeler_sdk`).
  3. `terminer()` remplace la réservation par le coût RÉEL (tokens facturés). `echouer()` libère la réservation si
     le fournisseur a répondu par une erreur (rien de facturé) ; si le résultat est INCONNU (timeout, coupure,
     arrêt du processus) la réservation est conservée comme dépense, marquée « à réconcilier ».

Un appel dont le contrôle échoue n'atteint JAMAIS le fournisseur : `ouvrir()` lève avant tout appel réseau.
Les montants sont des ESTIMATIONS internes (tarif officiel x taux configuré x marge), pas la facture Anthropic.
"""

from __future__ import annotations

import base64
import contextvars
import hashlib
import json
import logging
import math
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from programme.ia.exceptions import (
    BudgetEpuise,
    IAConfigurationInvalide,
    IADesactivee,
    IANonAutorisee,
    LimiteExerciceAtteinte,
    LimiteInteractionsAtteinte,
    LimiteJourAtteinte,
    ResultatPrecedentInconnu,
    OperationDejaEnCours,
)

from . import acces, tarifs
from .models import AlerteBudgetIA, BudgetMensuel, OperationIA

logger = logging.getLogger(__name__)
F = OperationIA.Fonction
S = OperationIA.Statut
ACTIFS = (S.RESERVEE, S.TERMINEE, S.INCONNUE)
SEUILS_ALERTE = (80, 95)


# --------------------------------------------------------------------------
#  Temps, identifiants
# --------------------------------------------------------------------------

def mois_et_jour(maintenant=None):
    """(« AAAA-MM », date) dans le fuseau Africa/Niamey (settings.TIME_ZONE), jamais en UTC."""
    local = timezone.localtime(maintenant or timezone.now())
    return local.strftime("%Y-%m"), local.date()


def empreinte_analyse(analyse: dict) -> str:
    """Identité d'un exercice APRÈS lecture : mêmes champs que programme.professeur.seance._empreinte."""
    utile = {k: analyse.get(k) for k in ("enonce", "donnees", "formules", "questions", "tableaux", "figures")}
    return hashlib.sha256(json.dumps(utile, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def empreinte_depot(utilisateur_id: int, programme_id: int, octets_fichiers: list[bytes], enonce: str) -> str:
    """Identité d'un exercice AVANT lecture (fichiers + texte saisi). La remarque de relecture n'en fait pas partie :
    une relecture reste le MÊME exercice."""
    h = hashlib.sha256(f"u{utilisateur_id}|p{programme_id}|".encode())
    for octets in octets_fichiers:
        h.update(hashlib.sha256(octets).digest())
    h.update((enonce or "").strip().encode())
    return h.hexdigest()


def resoudre_exercice(utilisateur_id: int, empreinte_analyse_: str) -> str:
    """Rattache une analyse à l'exercice dont elle provient (lecture), sinon elle forme un nouvel exercice."""
    op = (
        OperationIA.objects.filter(utilisateur_id=utilisateur_id, alias_cle=empreinte_analyse_, statut__in=ACTIFS)
        .exclude(exercice_cle="").order_by("-cree_le").first()
    )
    return op.exercice_cle if op else empreinte_analyse_


# --------------------------------------------------------------------------
#  Contexte (qui, quel exercice) : porté par une ContextVar, posé par les services métier
# --------------------------------------------------------------------------

@dataclass
class ContexteIA:
    utilisateur_id: int | None
    exercice_cle: str = ""
    cle_requete: str = ""
    operations: list = field(default_factory=list)

    def associer_analyse(self, analyse: dict) -> str:
        """Après une lecture réussie : l'analyse produite devient un alias de l'exercice (correction et fahimta ai
        la retrouveront sans consommer un nouvel exercice)."""
        alias = empreinte_analyse(analyse)
        if self.operations:
            OperationIA.objects.filter(pk=self.operations[-1]).update(alias_cle=alias)
        return alias


_contexte: contextvars.ContextVar[ContexteIA | None] = contextvars.ContextVar("budget_ia_contexte", default=None)
# (identifiant de tâche, est une reprise) : posé par le worker autour de l'exécution d'une tâche asynchrone.
_tache: contextvars.ContextVar[tuple | None] = contextvars.ContextVar("budget_ia_tache", default=None)


@contextmanager
def tache(tache_id, reprise: bool):
    jeton = _tache.set((tache_id, reprise))
    try:
        yield
    finally:
        _tache.reset(jeton)


@contextmanager
def contexte(*, utilisateur_id: int | None, exercice_cle: str = "", cle_requete: str = ""):
    ctx = ContexteIA(utilisateur_id=utilisateur_id, exercice_cle=exercice_cle, cle_requete=cle_requete)
    jeton = _contexte.set(ctx)
    try:
        yield ctx
    finally:
        _contexte.reset(jeton)


# --------------------------------------------------------------------------
#  Estimation PRUDENTE des tokens d'entrée (avant l'appel)
# --------------------------------------------------------------------------

_PAGE_PDF = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def tokens_texte(texte: str) -> int:
    return math.ceil(len(texte or "") / float(settings.IA_EST_CARACTERES_PAR_TOKEN))


def _pages_pdf(octets: bytes) -> int:
    n = len(_PAGE_PDF.findall(octets))
    return n if n else max(1, math.ceil(len(octets) / 150_000))


def estimer_entree(*, message: str | None = None, blocs: list[dict] | None = None, systeme: str = "", outil: dict | None = None) -> int:
    total = int(settings.IA_EST_TOKENS_FIXES) + tokens_texte(systeme)
    if outil:
        total += tokens_texte(json.dumps(outil, ensure_ascii=False))
    if message:
        total += tokens_texte(message)
    for bloc in blocs or []:
        genre = bloc.get("type")
        if genre == "text":
            total += tokens_texte(bloc.get("text", ""))
        elif genre == "image":
            total += int(settings.IA_EST_TOKENS_PAR_IMAGE)
        elif genre == "document":
            try:
                octets = base64.b64decode(bloc["source"]["data"])
            except Exception:  # noqa: BLE001 : illisible, on suppose le pire (10 pages)
                octets = b""
            pages = _pages_pdf(octets) if octets else 10
            total += pages * int(settings.IA_EST_TOKENS_PAR_PAGE_PDF)
    return total


# --------------------------------------------------------------------------
#  Réservation
# --------------------------------------------------------------------------

def _limite_par_exercice(fonction: str) -> int | None:
    return {
        F.LECTURE: int(settings.IA_LECTURES_MAX_PAR_EXERCICE),
        F.CORRECTION: int(settings.IA_CORRECTIONS_MAX_PAR_EXERCICE),
        F.PLAN: int(settings.IA_PLANS_MAX_PAR_EXERCICE),
        F.TOUR: int(settings.IA_INTERACTIONS_PROF_PAR_EXERCICE),
    }.get(fonction)


def _peremption() -> timedelta:
    return timedelta(seconds=int(getattr(settings, "IA_RESERVATION_PEREMPTION_SECONDS", 600)))


def _verrouiller_budget(mois: str) -> BudgetMensuel:
    BudgetMensuel.objects.get_or_create(mois=mois)  # création concurrente : l'unicité tranche, le verrou suit
    return BudgetMensuel.objects.select_for_update().get(mois=mois)


def _abandonner_perimees(budget: BudgetMensuel) -> None:
    """Réservations restées ouvertes (processus tué, coupure) : résultat inconnu, coût conservé par prudence."""
    limite = timezone.now() - _peremption()
    for op in OperationIA.objects.select_for_update().filter(statut=S.RESERVEE, mois=budget.mois, cree_le__lt=limite):
        budget.reserve_fcfa -= op.cout_reserve_fcfa
        budget.depense_fcfa += op.cout_reserve_fcfa
        op.statut, op.cout_fcfa, op.code_erreur, op.termine_le = S.INCONNUE, op.cout_reserve_fcfa, "abandonnee", timezone.now()
        op.save(update_fields=["statut", "cout_fcfa", "code_erreur", "termine_le"])
    if budget.reserve_fcfa < 0:
        budget.reserve_fcfa = Decimal(0)


def _verifier_quotas(utilisateur_id: int, fonction: str, ctx: ContexteIA, jour) -> None:
    """Appelé avec la ligne de l'élève verrouillée : les décomptes ne peuvent pas être dépassés en parallèle."""
    if ctx.cle_requete and OperationIA.objects.filter(
        utilisateur_id=utilisateur_id, fonctionnalite=fonction, cle_requete=ctx.cle_requete,
        statut=S.RESERVEE, cree_le__gte=timezone.now() - _peremption(),
    ).exists():
        raise OperationDejaEnCours()

    cles_du_jour = set(
        OperationIA.objects.filter(utilisateur_id=utilisateur_id, jour=jour, statut__in=ACTIFS)
        .exclude(exercice_cle="").values_list("exercice_cle", flat=True).distinct()
    )
    if ctx.exercice_cle not in cles_du_jour and len(cles_du_jour) >= int(settings.IA_EXERCICES_PAR_JOUR):
        raise LimiteJourAtteinte()

    maximum = _limite_par_exercice(fonction)
    if maximum is not None:
        deja = OperationIA.objects.filter(
            utilisateur_id=utilisateur_id, exercice_cle=ctx.exercice_cle, fonctionnalite=fonction, statut__in=ACTIFS
        ).count()
        if deja >= maximum:
            raise (LimiteInteractionsAtteinte if fonction == F.TOUR else LimiteExerciceAtteinte)()


def ouvrir(*, fonctionnalite: str, modele: str, tokens_entree: int, tokens_sortie_max: int) -> OperationIA:
    """Contrôles + réservation. Lève AVANT tout appel au fournisseur ; l'opération renvoyée doit être soldée par
    `terminer()` ou `echouer()` (c'est le rôle de `appeler_sdk`)."""
    if not settings.IA_INTERRUPTEUR_GLOBAL:
        raise IADesactivee()
    tarifs.tarif(modele)  # lève ModeleNonTarife : jamais d'appel sans tarif vérifié
    cout_max = tarifs.usd_vers_fcfa(tarifs.cout_usd(modele, entree=tokens_entree, sortie=tokens_sortie_max))

    ctx = _contexte.get()
    pour_un_eleve = fonctionnalite != F.CONTENU
    if pour_un_eleve and (ctx is None or not ctx.utilisateur_id or not ctx.exercice_cle):
        # Fermé par défaut : aucun appel élève sans identité ni exercice (ne doit jamais échapper au contrôle).
        raise IAConfigurationInvalide("Contexte budgétaire absent : appel refusé.")
    if pour_un_eleve and acces.mode_pilote() and not acces.compte_autorise(ctx.utilisateur_id):
        # Mode pilote : dernier verrou, valable aussi pour une tâche différée exécutée par le worker.
        raise IANonAutorisee()

    mois, jour = mois_et_jour()
    plein = False
    op = None
    with transaction.atomic():
        if pour_un_eleve:
            from comptes.models import User
            User.objects.select_for_update().get(pk=ctx.utilisateur_id)  # sérialise les requêtes d'un même élève
            _verifier_quotas(ctx.utilisateur_id, fonctionnalite, ctx, jour)
        courante = _tache.get()
        if courante and courante[1] and OperationIA.objects.filter(
            tache_id=courante[0], statut__in=[OperationIA.Statut.RESERVEE, OperationIA.Statut.INCONNUE, OperationIA.Statut.TERMINEE]
        ).exists():
            # Reprise d'une tâche dont un appel payant a déjà été ouvert (issue inconnue ou réponse non conservée).
            raise ResultatPrecedentInconnu()
        budget = _verrouiller_budget(mois)
        _abandonner_perimees(budget)
        plafond = Decimal(settings.BUDGET_IA_SEUIL_OPERATIONNEL_FCFA)
        if budget.depense_fcfa + budget.reserve_fcfa + cout_max > plafond:
            plein = True
            budget.save()
        else:
            budget.reserve_fcfa += cout_max
            budget.save()
            op = OperationIA.objects.create(
                utilisateur_id=ctx.utilisateur_id if ctx else None, fonctionnalite=fonctionnalite, modele=modele,
                mois=mois, jour=jour, exercice_cle=(ctx.exercice_cle if ctx else ""),
                cle_requete=(ctx.cle_requete if ctx else ""), cout_reserve_fcfa=cout_max,
                tache_id=(_tache.get()[0] if _tache.get() else None),
            )
            part = (budget.depense_fcfa + budget.reserve_fcfa) * 100 / plafond if plafond > 0 else Decimal(100)
    if plein:
        _alerter(mois, 100)  # hors de la transaction : le refus n'efface pas l'alerte
        raise BudgetEpuise()
    for seuil in SEUILS_ALERTE:
        if part >= seuil:
            _alerter(mois, seuil)
    if ctx is not None:
        ctx.operations.append(op.pk)
    return op


def _alerter(mois: str, seuil: int) -> None:
    textes = {
        80: "Budget IA à 80 % du plafond opérationnel : surveiller la consommation.",
        95: "ALERTE CRITIQUE : budget IA à 95 % du plafond opérationnel.",
        100: "Budget IA épuisé : plus aucun appel IA n'est autorisé ce mois-ci.",
    }
    alerte, cree = AlerteBudgetIA.objects.get_or_create(mois=mois, seuil=seuil, defaults={"message": textes[seuil]})
    if cree:  # une seule fois par seuil et par mois
        (logger.error if seuil >= 95 else logger.warning)("BUDGET_IA %s : %s", mois, alerte.message)


# --------------------------------------------------------------------------
#  Décompte
# --------------------------------------------------------------------------

def usage_de_reponse(reponse) -> dict:
    u = getattr(reponse, "usage", None)

    def lire(nom):
        v = getattr(u, nom, None)
        return v if isinstance(v, int) else None

    return {
        "tokens_entree": lire("input_tokens"), "tokens_sortie": lire("output_tokens"),
        "tokens_cache_ecriture": lire("cache_creation_input_tokens"), "tokens_cache_lecture": lire("cache_read_input_tokens"),
    }


def terminer(op: OperationIA, usage: dict | None) -> OperationIA:
    """Remplace la réservation par le coût réel. Idempotent (une opération déjà soldée n'est jamais recomptée)."""
    with transaction.atomic():
        op = OperationIA.objects.select_for_update().get(pk=op.pk)
        if op.statut != S.RESERVEE:
            return op
        budget = _verrouiller_budget(op.mois)
        usage = usage or {}
        connue = usage.get("tokens_entree") is not None and usage.get("tokens_sortie") is not None
        if connue:
            usd = tarifs.cout_usd(
                op.modele, entree=usage["tokens_entree"], sortie=usage["tokens_sortie"],
                cache_ecriture=usage.get("tokens_cache_ecriture"), cache_lecture=usage.get("tokens_cache_lecture"),
            )
            cout = tarifs.usd_vers_fcfa(usd)
            if cout > op.cout_reserve_fcfa:
                logger.warning("BUDGET_IA estimation sous-évaluée : réel %s FCFA > réservé %s FCFA (%s)", cout, op.cout_reserve_fcfa, op.fonctionnalite)
            op.cout_usd = usd
        else:
            cout = op.cout_reserve_fcfa  # consommation inconnue : on compte la réservation entière (prudence)
        budget.reserve_fcfa = max(Decimal(0), budget.reserve_fcfa - op.cout_reserve_fcfa)
        budget.depense_fcfa += cout
        budget.save()
        op.statut, op.cout_fcfa, op.consommation_connue, op.termine_le = S.TERMINEE, cout, connue, timezone.now()
        op.tokens_entree, op.tokens_sortie = usage.get("tokens_entree"), usage.get("tokens_sortie")
        op.tokens_cache_ecriture, op.tokens_cache_lecture = usage.get("tokens_cache_ecriture"), usage.get("tokens_cache_lecture")
        op.save()
    return op


def echouer(op: OperationIA, code: str, *, resultat_inconnu: bool) -> OperationIA:
    with transaction.atomic():
        op = OperationIA.objects.select_for_update().get(pk=op.pk)
        if op.statut != S.RESERVEE:
            return op
        budget = _verrouiller_budget(op.mois)
        budget.reserve_fcfa = max(Decimal(0), budget.reserve_fcfa - op.cout_reserve_fcfa)
        if resultat_inconnu:  # le fournisseur a peut-être facturé : on garde le coût réservé
            budget.depense_fcfa += op.cout_reserve_fcfa
            op.statut, op.cout_fcfa = S.INCONNUE, op.cout_reserve_fcfa
        else:
            op.statut, op.cout_fcfa = S.ECHOUEE, Decimal(0)
        budget.save()
        op.code_erreur, op.termine_le = code[:40], timezone.now()
        op.save()
    return op


def appeler_sdk(op: OperationIA, creer):
    """Exécute `creer()` (l'appel `client.messages.create`) et solde l'opération. Les exceptions repartent
    inchangées : l'appelant garde son propre mapping d'erreurs."""
    try:
        reponse = creer()
    except BaseException as exc:  # noqa: BLE001 : y compris arrêt du worker (SystemExit) : résultat inconnu
        echouer(op, type(exc).__name__, resultat_inconnu=_resultat_inconnu(exc))
        raise
    terminer(op, usage_de_reponse(reponse))
    return reponse


def _resultat_inconnu(exc: BaseException) -> bool:
    """Erreur HTTP renvoyée par le fournisseur (401, 400, 429, 5xx) : rien de facturé. Timeout, coupure de
    connexion ou toute autre interruption : le fournisseur a pu traiter la requête, résultat INCONNU."""
    try:
        import anthropic
    except ImportError:
        return True
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return False
    return True


def reconcilier_abandonnees() -> int:
    """Pour la commande de maintenance : solde les réservations périmées de TOUS les mois."""
    n = 0
    for mois in OperationIA.objects.filter(statut=S.RESERVEE).values_list("mois", flat=True).distinct():
        with transaction.atomic():
            budget = _verrouiller_budget(mois)
            avant = OperationIA.objects.filter(statut=S.RESERVEE, mois=mois).count()
            _abandonner_perimees(budget)
            budget.save()
            n += avant - OperationIA.objects.filter(statut=S.RESERVEE, mois=mois).count()
    return n
