"""
Suivi des dépenses Anthropic (budget mensuel GLOBAL + quotas par élève), en PostgreSQL.

Les montants sont des ESTIMATIONS internes en FCFA (tokens facturés x tarif officiel x taux configuré x marge).
Ils ne remplacent pas la facture Anthropic. Aucun contenu d'exercice n'est stocké ici : seulement des compteurs.
"""

import uuid

from django.conf import settings
from django.db import models


class BudgetMensuel(models.Model):
    """Une ligne par mois civil (fuseau Africa/Niamey). Verrouillée (select_for_update) à chaque réservation."""

    mois = models.CharField(max_length=7, unique=True, help_text="AAAA-MM, fuseau Africa/Niamey")
    depense_fcfa = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    reserve_fcfa = models.DecimalField(max_digits=16, decimal_places=4, default=0)
    cree_le = models.DateTimeField(auto_now_add=True)
    maj_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "budget mensuel IA"
        verbose_name_plural = "budgets mensuels IA"
        ordering = ["-mois"]

    def __str__(self):
        return f"Budget IA {self.mois}"


class OperationIA(models.Model):
    class Fonction(models.TextChoices):
        LECTURE = "lecture", "Lecture de l'énoncé"
        CORRECTION = "correction", "Correction"
        PLAN = "professeur_plan", "fahimta ai : plan"
        TOUR = "professeur_tour", "fahimta ai : interaction"
        CONTENU = "contenu_admin", "Génération de contenu (admin)"

    class Statut(models.TextChoices):
        RESERVEE = "reservee", "Réservée (en cours)"
        TERMINEE = "terminee", "Terminée"
        ECHOUEE = "echouee", "Échouée (rien facturé)"
        INCONNUE = "inconnue", "Résultat inconnu (à réconcilier)"

    cle_operation = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    fonctionnalite = models.CharField(max_length=20, choices=Fonction.choices)
    modele = models.CharField(max_length=80)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.RESERVEE, db_index=True)
    mois = models.CharField(max_length=7, db_index=True)
    jour = models.DateField(db_index=True, help_text="Jour civil Africa/Niamey de la réservation")
    exercice_cle = models.CharField(max_length=64, blank=True, db_index=True)
    alias_cle = models.CharField(max_length=64, blank=True, db_index=True, help_text="Empreinte de l'analyse produite")
    cle_requete = models.CharField(max_length=64, blank=True)
    tache_id = models.UUIDField(null=True, blank=True, db_index=True, help_text="Tâche asynchrone d'origine (anti double appel payant)")
    cout_reserve_fcfa = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    cout_fcfa = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    cout_usd = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    tokens_entree = models.IntegerField(null=True, blank=True)
    tokens_sortie = models.IntegerField(null=True, blank=True)
    tokens_cache_ecriture = models.IntegerField(null=True, blank=True)
    tokens_cache_lecture = models.IntegerField(null=True, blank=True)
    consommation_connue = models.BooleanField(default=False)
    code_erreur = models.CharField(max_length=40, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    termine_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "opération IA"
        verbose_name_plural = "opérations IA"
        ordering = ["-cree_le"]
        indexes = [
            models.Index(fields=["utilisateur", "jour"]),
            models.Index(fields=["utilisateur", "exercice_cle", "fonctionnalite"]),
        ]

    def __str__(self):
        return f"{self.fonctionnalite} {self.statut} {self.cle_operation}"


class AlerteBudgetIA(models.Model):
    """Une seule alerte par (mois, seuil) : pas de répétition. Visible dans l'administration."""

    mois = models.CharField(max_length=7)
    seuil = models.PositiveSmallIntegerField(help_text="80, 95 ou 100 (% du plafond opérationnel)")
    message = models.CharField(max_length=200)
    cree_le = models.DateTimeField(auto_now_add=True)
    acquittee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "alerte budget IA"
        verbose_name_plural = "alertes budget IA"
        ordering = ["-cree_le"]
        constraints = [models.UniqueConstraint(fields=["mois", "seuil"], name="alerte_unique_mois_seuil")]

    def __str__(self):
        return f"{self.mois} : {self.seuil} %"
