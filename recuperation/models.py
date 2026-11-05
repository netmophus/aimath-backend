from django.conf import settings
from django.db import models
from django.utils import timezone


class DemandeReinitialisation(models.Model):
    """Une demande de récupération de mot de passe pour un compte EXISTANT et actif.

    Le code à 6 chiffres n'est JAMAIS stocké : il se reconstitue à la demande par HMAC-SHA256 d'un secret dédié
    (OTP_CLE_SECRETE) sur l'identifiant de la demande et un sel aléatoire propre à CETTE demande (`sel`). Sans le secret
    (absent de la base), le sel et l'identifiant ne permettent pas de retrouver le code. L'autorisation de
    réinitialisation n'est stockée que sous forme de HMAC.
    Cycle : code envoyé -> vérifié (autorisation émise) -> mot de passe changé (consommée).
    Elle peut aussi être remplacée par une demande plus récente, épuisée (trop d'essais) ou expirée."""

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="demandes_reinitialisation")
    sel = models.CharField(max_length=32)
    cree_le = models.DateTimeField(default=timezone.now, db_index=True)
    expire_le = models.DateTimeField()
    tentatives = models.PositiveSmallIntegerField(default=0)
    verifiee_le = models.DateTimeField(null=True, blank=True)
    autorisation_hmac = models.CharField(max_length=64, blank=True)
    autorisation_expire_le = models.DateTimeField(null=True, blank=True)
    echecs_autorisation = models.PositiveSmallIntegerField(default=0)
    cloturee_le = models.DateTimeField(null=True, blank=True)
    cloture_motif = models.CharField(max_length=12, blank=True)   # consommee / remplacee / epuisee

    class Meta:
        ordering = ["-id"]


class EvenementRecuperation(models.Model):
    """Compteurs de limitation de débit, PARTAGÉS entre dynos et survivant aux redémarrages (PostgreSQL).

    Une ligne est écrite pour CHAQUE demande, que le numéro ait un compte ou non : les limites s'appliquent donc de la
    même façon et ne révèlent pas l'existence d'un compte. Le numéro n'est conservé que sous forme de HMAC."""

    class Type(models.TextChoices):
        DEMANDE = "demande", "Demande de code"
        VERIF_ECHEC = "verif_echec", "Vérification ou réinitialisation échouée"
        CHANGEMENT_ECHEC = "changement_echec", "Mot de passe actuel incorrect"

    type = models.CharField(max_length=20, choices=Type.choices)
    cle = models.CharField(max_length=64, blank=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    cree_le = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["type", "cree_le"]), models.Index(fields=["type", "ip", "cree_le"])]


class EnvoiCodeSms(models.Model):
    """File d'envoi PERSISTANTE (PostgreSQL) des codes par SMS, traitée par le worker `traiter_envoi_codes_otp`.

    Une ligne est créée dans la MÊME transaction que la demande : si la demande existe, l'envoi est programmé, même si
    le dyno web redémarre juste après. La ligne ne contient ni le code ni le texte, seulement le numéro et le nombre de
    segments réservés au budget. États :

      en_attente -> en_cours -> accepte     LAM a accepté le message (pas une confirmation de livraison)
                             -> echec       refus définitif, ou rien n'a pu partir après les essais autorisés
                             -> incertain   le SMS est peut-être parti : JAMAIS renvoyé automatiquement
                             -> en_attente  (seulement si rien n'a pu partir : injoignable, nouvel essai différé)
      en_attente -> expire                  code périmé, remplacé ou clôturé avant l'envoi : aucun SMS
      en_cours trop ancien -> incertain     le worker a été interrompu en plein envoi
    """

    class Etat(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_COURS = "en_cours", "En cours"
        ACCEPTE = "accepte", "Accepté"
        ECHEC = "echec", "Échec"
        INCERTAIN = "incertain", "Incertain"
        EXPIRE = "expire", "Expiré"

    demande = models.OneToOneField(DemandeReinitialisation, on_delete=models.CASCADE, related_name="envoi")
    telephone = models.CharField(max_length=20)
    segments = models.PositiveSmallIntegerField(default=1)
    etat = models.CharField(max_length=12, choices=Etat.choices, default=Etat.EN_ATTENTE)
    tentatives = models.PositiveSmallIntegerField(default=0)
    cree_le = models.DateTimeField(default=timezone.now)
    disponible_le = models.DateTimeField(default=timezone.now)
    expire_le = models.DateTimeField()
    debut_traitement_le = models.DateTimeField(null=True, blank=True)
    termine_le = models.DateTimeField(null=True, blank=True)
    detail = models.CharField(max_length=40, blank=True)   # identifiant technique court, jamais de texte ni de code

    class Meta:
        indexes = [models.Index(fields=["etat", "disponible_le"]), models.Index(fields=["cree_le"])]


class BattementWorkerOtp(models.Model):
    """Ligne unique : dernier signe de vie du worker. Sans worker vivant, la demande de code répond « service
    temporairement indisponible » (à tous les numéros, sans rien révéler) au lieu de promettre un SMS qui ne partira pas."""

    dernier_battement = models.DateTimeField(default=timezone.now)
