"""Tableau de bord du budget IA : chiffres ESTIMÉS par FAHIMTA (pas la facture Anthropic). Aucun secret, aucun contenu."""

from decimal import Decimal

from django.conf import settings
from django.db.models import Count, F, Sum, Value
from django.db.models.functions import Greatest

from .models import AlerteBudgetIA, BudgetMensuel, OperationIA
from .service import mois_et_jour

S = OperationIA.Statut


def _f(v) -> float:
    return float(v or 0)


def rapport_mensuel(mois: str | None = None) -> dict:
    mois = mois or mois_et_jour()[0]
    budget = BudgetMensuel.objects.filter(mois=mois).first()
    depense, reserve = (budget.depense_fcfa, budget.reserve_fcfa) if budget else (Decimal(0), Decimal(0))
    plafond = Decimal(settings.BUDGET_IA_MENSUEL_FCFA)
    seuil = Decimal(settings.BUDGET_IA_SEUIL_OPERATIONNEL_FCFA)
    ops = OperationIA.objects.filter(mois=mois)
    appels = ops.exclude(statut=S.ECHOUEE)

    def groupe(champ):
        return [
            {"cle": ligne[champ] if ligne[champ] is not None else "(admin)", "operations": ligne["n"], "cout_fcfa": _f(ligne["cout"])}
            for ligne in appels.values(champ).annotate(n=Count("id"), cout=Sum("cout_fcfa")).order_by("-cout")[:50]
        ]

    from traitement_ia.models import TacheIA

    depassement = appels.filter(consommation_connue=True).aggregate(
        x=Sum(Greatest(F("cout_fcfa") - F("cout_reserve_fcfa"), Value(Decimal(0))))
    )["x"]
    return {
        "mois": mois,
        "avertissement": "Montants estimés par FAHIMTA (tarif officiel x taux configuré x marge). Ne remplace pas la facture Anthropic.",
        "budget_reference_fcfa": _f(plafond),
        "seuil_operationnel_fcfa": _f(seuil),
        "consomme_estime_fcfa": _f(depense),
        "reserve_en_cours_fcfa": _f(reserve),
        "restant_fcfa": _f(max(Decimal(0), seuil - depense - reserve)),
        "pourcentage_seuil": _f((depense + reserve) * 100 / seuil) if seuil else 100.0,
        "taux_usd_fcfa": str(settings.IA_TAUX_USD_FCFA),
        "taux_date_reference": settings.IA_TAUX_USD_FCFA_DATE,
        "taux_bceao_reference": str(settings.IA_TAUX_BCEAO_REFERENCE),
        "taux_bceao_date": settings.IA_TAUX_BCEAO_DATE,
        # Somme des dépassements du coût réel sur le coût réservé : doit rester ~0 ; sinon relever IA_EST_*.
        "depassement_estimation_fcfa": _f(depassement),
        "taches": {s: TacheIA.objects.filter(statut=s).count() for s in ("en_attente", "en_cours", "echouee")},
        "marge_securite": str(settings.IA_MARGE_SECURITE),
        "interrupteur_global": bool(settings.IA_INTERRUPTEUR_GLOBAL),
        "exercices_traites": ops.exclude(exercice_cle="").filter(statut__in=(S.TERMINEE, S.INCONNUE)).values("exercice_cle").distinct().count(),
        "appels_anthropic": appels.count(),
        "echecs": ops.filter(statut=S.ECHOUEE).count(),
        "en_cours": ops.filter(statut=S.RESERVEE).count(),
        "a_reconcilier": ops.filter(statut=S.INCONNUE).count(),
        "par_fonctionnalite": groupe("fonctionnalite"),
        "par_modele": groupe("modele"),
        "par_eleve": groupe("utilisateur_id"),
        "alertes": list(AlerteBudgetIA.objects.filter(mois=mois).values("seuil", "message", "cree_le", "acquittee")),
    }
