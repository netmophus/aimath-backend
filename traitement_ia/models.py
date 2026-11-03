"""
File de tâches IA PERSISTANTE (PostgreSQL) : une requête longue (lecture, correction, plan fahimta ai...) est enregistrée,
puis exécutée par un processus `worker` distinct du web. Le navigateur consulte l'état de la tâche et récupère le résultat.

Rien ne vit dans la mémoire d'un processus web : un redémarrage, un second dyno ou un second worker ne perdent rien.
Les fichiers d'un exercice sont supprimés dès que la tâche est terminée ; le résultat est purgé après `expire_le`.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class TacheIA(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"   # le résultat peut être une erreur (429, 503...) : voir resultat_http
        ECHOUEE = "echouee", "Abandonnée"   # trop de tentatives (worker interrompu à répétition)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    type = models.CharField(max_length=30)
    vue = models.CharField(max_length=120, help_text="Chemin Python de la vue qui exécute la tâche")
    kwargs = models.JSONField(default=dict)
    donnees = models.JSONField(default=dict, help_text="Champs de la requête d'origine (sans fichiers)")
    cle_requete = models.CharField(max_length=64, help_text="Anti double envoi : une seule tâche active par clé")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE, db_index=True)
    tentatives = models.PositiveSmallIntegerField(default=0)
    disponible_le = models.DateTimeField(help_text="Pas avant cette date (nouvel essai différé)")
    verrou_jusqua = models.DateTimeField(null=True, blank=True, help_text="Bail du worker : après cette date, un autre worker peut reprendre")
    travailleur = models.CharField(max_length=60, blank=True)
    resultat_http = models.PositiveSmallIntegerField(null=True, blank=True)
    resultat = models.JSONField(null=True, blank=True)
    code_erreur = models.CharField(max_length=40, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    demarre_le = models.DateTimeField(null=True, blank=True)
    termine_le = models.DateTimeField(null=True, blank=True)
    expire_le = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "tâche IA"
        verbose_name_plural = "tâches IA"
        ordering = ["cree_le"]
        constraints = [
            models.UniqueConstraint(
                fields=["utilisateur", "type", "cle_requete"],
                condition=Q(statut__in=["en_attente", "en_cours"]),
                name="tache_active_unique",
            )
        ]

    def __str__(self):
        return f"{self.type} {self.statut} {self.id}"


class FichierTacheIA(models.Model):
    """Octets d'un fichier d'exercice, conservés SEULEMENT le temps du traitement (supprimés à la fin de la tâche)."""

    tache = models.ForeignKey(TacheIA, on_delete=models.CASCADE, related_name="fichiers")
    ordre = models.PositiveSmallIntegerField()
    champ = models.CharField(max_length=30, default="fichiers")
    nom = models.CharField(max_length=255)
    type_mime = models.CharField(max_length=100)
    octets = models.BinaryField()

    class Meta:
        ordering = ["ordre"]
