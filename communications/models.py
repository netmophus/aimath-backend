from django.conf import settings
from django.db import models


class ParametresCommunication(models.Model):
    """Réglages modifiables par un administrateur (une seule ligne, pk=1). Jamais de secret ici."""

    lien_whatsapp = models.URLField("lien du groupe WhatsApp", max_length=200, blank=True)
    plafond_mensuel_fcfa = models.PositiveIntegerField(
        "plafond mensuel (FCFA)", default=0,
        help_text="0 = aucun envoi autorisé tant qu'un plafond n'est pas défini.")
    cout_segment_fcfa = models.DecimalField(
        "coût d'un segment SMS (FCFA)", max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Tarif du fournisseur. Vide = coût inconnu : aucun envoi autorisé.")
    mis_a_jour_le = models.DateTimeField(auto_now=True)
    mis_a_jour_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "paramètres de communication"

    @classmethod
    def charger(cls) -> "ParametresCommunication":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PreferenceCommunication(models.Model):
    """Préférences et consentements, à part du modèle User (aucune donnée d'authentification touchée).

    - opposition_facultatif : opt-out des SMS facultatifs (défaut False = pas d'opposition).
    - invitations_whatsapp : opt-in EXPLICITE. None = jamais répondu, ce qui n'est PAS un consentement.
    - parental_* : recueil vérifiable pour un mineur (ou âge inconnu) : l'élève indique un contact parent,
      un administrateur valide après vérification et le consigne. Jamais créé automatiquement.
    """

    class Parental(models.TextChoices):
        AUCUN = "aucun", "Aucune demande"
        DEMANDE = "demande", "Demande en attente de vérification"
        VALIDE = "valide", "Validé"
        REFUSE = "refuse", "Refusé"

    class Methode(models.TextChoices):
        APPEL = "appel", "Appel téléphonique au parent"
        FORMULAIRE = "formulaire", "Formulaire signé"
        PRESENCE = "presence", "En présence du parent"

    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                       related_name="preference_communication")
    opposition_facultatif = models.BooleanField(
        "s'oppose aux communications facultatives", default=False)
    invitations_whatsapp = models.BooleanField(
        "accepte les invitations aux groupes WhatsApp", null=True, blank=True, default=None)
    invitations_whatsapp_le = models.DateTimeField(null=True, blank=True)
    parental_statut = models.CharField(max_length=10, choices=Parental.choices, default=Parental.AUCUN)
    parental_telephone = models.CharField("téléphone du parent ou tuteur", max_length=20, blank=True)
    parental_demande_le = models.DateTimeField(null=True, blank=True)
    parental_methode = models.CharField(max_length=12, choices=Methode.choices, blank=True)
    parental_note = models.CharField(max_length=200, blank=True)
    parental_decide_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                            on_delete=models.SET_NULL, related_name="+")
    parental_decide_le = models.DateTimeField(null=True, blank=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)


class Campagne(models.Model):
    class Type(models.TextChoices):
        SMS = "sms", "SMS"
        INVITATION = "invitation_whatsapp", "Invitation WhatsApp"
        ACTIVATION = "activation", "Activation de compte"

    class Categorie(models.TextChoices):
        SERVICE = "service", "Notification de service"
        FACULTATIF = "facultatif", "Communication facultative"

    class Statut(models.TextChoices):
        APERCU = "apercu", "Aperçu (rien n'est parti)"
        EN_COURS = "en_cours", "En cours"
        TERMINEE = "terminee", "Terminée"
        ARRETEE = "arretee", "Arrêtée"

    class Mode(models.TextChoices):
        IDS = "ids", "Comptes choisis"
        FILTRES = "filtres", "Résultats filtrés"
        TOUS = "tous", "Tous les éligibles"

    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name="campagnes_communication")
    cle = models.CharField("clé d'idempotence", max_length=64)
    type = models.CharField(max_length=24, choices=Type.choices)
    categorie = models.CharField(max_length=12, choices=Categorie.choices)
    texte = models.TextField()
    mode = models.CharField(max_length=8, choices=Mode.choices)
    filtres = models.JSONField(default=dict, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.APERCU)

    nb_comptes = models.PositiveIntegerField(default=0)
    exclusions = models.JSONField(default=dict, blank=True)   # {"numero_invalide": n, "doublon": n, ...}
    nb_destinataires = models.PositiveIntegerField(default=0)
    segments_total = models.PositiveIntegerField(default=0)
    cout_segment = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # tarif figé à l'aperçu
    cout_estime = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    cree_le = models.DateTimeField(auto_now_add=True)
    confirmee_le = models.DateTimeField(null=True, blank=True)
    terminee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["auteur", "cle"], name="campagne_cle_unique_par_auteur")]


class MessageSms(models.Model):
    """Un destinataire d'une campagne. Aucun numéro complet ni texte n'est copié ici : le numéro est relu
    sur le compte au moment de l'envoi, seule une version masquée est conservée pour l'historique."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_COURS = "en_cours", "Envoi en cours"
        ACCEPTE = "accepte", "Accepté par le fournisseur"
        ECHEC = "echec", "Échec"
        INCERTAIN = "incertain", "Résultat incertain"
        IGNORE = "ignore", "Ignoré"
        ANNULE = "annule", "Annulé"

    campagne = models.ForeignKey(Campagne, on_delete=models.CASCADE, related_name="messages")
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                    related_name="messages_communication")
    telephone_masque = models.CharField(max_length=20)
    segments = models.PositiveSmallIntegerField(default=1)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_ATTENTE)
    tentatives = models.PositiveSmallIntegerField(default=0)
    dernier_code = models.CharField(max_length=40, blank=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["campagne", "statut"])]


class TentativeSms(models.Model):
    message = models.ForeignKey(MessageSms, on_delete=models.CASCADE, related_name="historique")
    resultat = models.CharField(max_length=12)
    code = models.CharField(max_length=40, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
