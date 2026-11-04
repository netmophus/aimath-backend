from django.conf import settings
from django.db import models


class DemandeAide(models.Model):
    """Une demande d'un élève à l'administration (question, erreur, suggestion). Pas de chat, pas d'IA."""

    class Type(models.TextChoices):
        QUESTION = "question", "Question"
        ERREUR = "erreur", "Erreur"
        SUGGESTION = "suggestion", "Suggestion"

    class Statut(models.TextChoices):
        RECUE = "recue", "Reçue"
        EN_COURS = "en_cours", "En cours"
        TRAITEE = "traitee", "Traitée"

    eleve = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="demandes_aide")
    # Clé générée par le navigateur à l'ouverture du formulaire : un double envoi renvoie la même demande.
    cle = models.CharField(max_length=64)
    type = models.CharField(max_length=12, choices=Type.choices)
    programme = models.ForeignKey("programme.Programme", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    lecon = models.ForeignKey("programme.Lecon", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    message = models.TextField()

    # Pièce jointe PRIVÉE : stockée en base (jamais d'URL publique), servie seulement par une vue authentifiée.
    piece_jointe = models.BinaryField(null=True, blank=True, editable=False)
    piece_jointe_type = models.CharField(max_length=20, blank=True, default="")
    piece_jointe_taille = models.PositiveIntegerField(default=0)

    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.RECUE)
    reponse = models.TextField(blank=True, default="")
    reponse_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reponse_le = models.DateTimeField(null=True, blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)
    traitee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cree_le", "-id"]
        constraints = [models.UniqueConstraint(fields=["eleve", "cle"], name="aide_demande_cle_unique")]
        indexes = [models.Index(fields=["statut", "type"])]

    def __str__(self):
        return f"{self.get_type_display()} #{self.pk}"

    @property
    def a_piece_jointe(self) -> bool:
        return self.piece_jointe_taille > 0
