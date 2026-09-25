from cloudinary.models import CloudinaryField
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

telephone_validator = RegexValidator(
    regex=r"^\+227\d{8}$",
    message="Le numéro doit être au format +227 suivi de 8 chiffres (ex. +22790000000).",
)


class UserManager(BaseUserManager):
    """
    Manager du User custom : pas de champ "username", l'identifiant est
    le téléphone.
    """

    use_in_migrations = True

    @staticmethod
    def normalize_telephone(telephone: str) -> str:
        return (telephone or "").strip().replace(" ", "")

    def _create_user(self, telephone: str, password: str | None, **extra_fields):
        if not telephone:
            raise ValueError("Le numéro de téléphone est obligatoire.")
        telephone = self.normalize_telephone(telephone)
        user = self.model(telephone=telephone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, telephone: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ELEVE)
        extra_fields.setdefault("statut", self.model.Statut.EN_ATTENTE)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(telephone, password, **extra_fields)

    def create_superuser(self, telephone: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        extra_fields.setdefault("statut", self.model.Statut.ACTIF)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Le superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Le superuser doit avoir is_superuser=True.")

        return self._create_user(telephone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Utilisateur FAHIMTA. Connexion par téléphone (pas de username).
    Le champ `statut` porte la logique métier de validation des comptes ;
    `is_active` garde son sens Django habituel (compte utilisable pour
    l'authentification technique, y compris pendant qu'il est en_attente —
    c'est l'API de login qui refuse explicitement les comptes non actifs).
    """

    class Role(models.TextChoices):
        ELEVE = "eleve", "Élève"
        ENSEIGNANT = "enseignant", "Enseignant"
        ADMIN = "admin", "Admin"
        PARTENAIRE = "partenaire", "Partenaire"
        VENDEUR = "vendeur", "Vendeur"

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        ACTIF = "actif", "Actif"
        REJETE = "rejete", "Rejeté"
        SUSPENDU = "suspendu", "Suspendu"

    telephone = models.CharField(
        "téléphone",
        max_length=20,
        unique=True,
        validators=[telephone_validator],
        help_text="Format attendu : +227 suivi de 8 chiffres.",
    )
    email = models.EmailField("email", blank=True, null=True)
    prenom = models.CharField("prénom", max_length=100)
    nom = models.CharField("nom", max_length=100)

    role = models.CharField(
        "rôle", max_length=20, choices=Role.choices, default=Role.ELEVE
    )
    statut = models.CharField(
        "statut", max_length=20, choices=Statut.choices, default=Statut.EN_ATTENTE
    )

    # Rattachement scolaire : uniquement pertinent pour les élèves.
    niveau = models.ForeignKey(
        "programme.Niveau",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eleves",
        verbose_name="niveau",
    )
    serie = models.ForeignKey(
        "programme.Serie",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eleves",
        verbose_name="série",
    )

    is_active = models.BooleanField("actif", default=True)
    is_staff = models.BooleanField("accès admin", default=False)
    date_inscription = models.DateTimeField("date d'inscription", auto_now_add=True)

    # True pour les comptes créés par un admin avec un mot de passe
    # provisoire (enseignant/admin) — non bloquant côté backend pour
    # l'instant, à exploiter côté front pour forcer un changement.
    doit_changer_mdp = models.BooleanField("doit changer son mot de passe", default=False)

    # Renseigné par un admin lors d'un rejet (voir comptes/admin_views.py).
    # Remis à vide si le compte est ensuite approuvé.
    motif_rejet = models.TextField("motif du rejet", blank=True, null=True)

    # --- Abonnement élève ("tout Fahimta", pas d'offre par matière) : une
    # seule date de fin, pas de table séparée — suffisant tant qu'il n'existe
    # qu'une formule unique. null = jamais abonné. Le PAIEMENT (carte NITA)
    # n'est pas géré ici : cette date sera pour l'instant renseignée à la
    # main en base le temps que l'activation par carte existe (voir
    # programme.acces.eleve_peut_acceder pour l'usage de a_un_abonnement_actif).
    abonnement_actif_jusqu_au = models.DateField(
        "abonnement actif jusqu'au", blank=True, null=True,
        help_text="Date de fin de l'abonnement en cours. Vide = jamais abonné.",
    )

    # --- Vendeur : commission FIXE par carte (en FCFA), utilisée seulement
    # pour role=vendeur. Voir CarteFahimta.commission_figee : au moment où
    # une carte est ASSIGNÉE à un vendeur, la valeur courante de ce champ y
    # est recopiée ("figée") — modifier commission_fcfa ensuite ne change
    # donc jamais la commission des cartes déjà assignées, seulement celle
    # des futures assignations (voir comptes/admin_vendeurs_views.py).
    commission_fcfa = models.PositiveIntegerField(
        "commission (FCFA)", default=0,
        help_text="Commission fixe par carte vendue — utilisée uniquement pour les vendeurs.",
    )

    # --- Adresse du vendeur (facultative), pour le suivi/traçabilité admin
    # (voir comptes/admin_vendeurs_serializers.py). `ville` n'est PAS
    # dupliqué ici : le champ existe déjà plus bas (profil élève enrichi) et
    # son sens ("ville", sans plus de précision) est identique pour un
    # vendeur — réutilisé tel quel. `quartier` et `ecole_ou_point_vente`
    # sont propres au vendeur, jamais utilisés pour les autres rôles.
    quartier = models.CharField("quartier", max_length=100, blank=True, null=True)
    ecole_ou_point_vente = models.CharField(
        "école ou point de vente", max_length=150, blank=True, null=True,
        help_text="Repère physique du vendeur (école, boutique, marché…).",
    )

    # --- Profil élève enrichi (tous optionnels : ne casse aucun compte
    # existant) — modifiables par l'élève lui-même via ProfilEleveSerializer
    # (comptes/serializers.py), jamais par un paramètre arbitraire côté
    # admin/autre élève.
    class Genre(models.TextChoices):
        FEMININ = "F", "Féminin"
        MASCULIN = "M", "Masculin"
        AUTRE = "autre", "Autre"

    date_naissance = models.DateField("date de naissance", blank=True, null=True)
    ecole = models.CharField("établissement scolaire", max_length=150, blank=True, null=True)
    ville = models.CharField("ville", max_length=100, blank=True, null=True)
    genre = models.CharField(
        "genre", max_length=10, choices=Genre.choices, blank=True, null=True
    )
    # CloudinaryField (pas ImageField) : évite une dépendance à Pillow, et ne
    # fait AUCUN appel réseau à la définition du modèle ni à `migrate` — le
    # stockage réel sur Cloudinary n'intervient qu'au moment d'un vrai
    # upload (voir ProfilEleveSerializer et settings.CLOUDINARY_CONFIGURE
    # pour le comportement si les identifiants Cloudinary sont absents).
    photo = CloudinaryField(
        "photo de profil", blank=True, null=True, folder="fahimtana/profils"
    )

    objects = UserManager()

    USERNAME_FIELD = "telephone"
    REQUIRED_FIELDS = ["prenom", "nom"]

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["-date_inscription"]

    def __str__(self) -> str:
        return f"{self.prenom} {self.nom} ({self.telephone})"

    def save(self, *args, **kwargs):
        self.telephone = UserManager.normalize_telephone(self.telephone)
        super().save(*args, **kwargs)

    @property
    def a_un_abonnement_actif(self) -> bool:
        """True si `abonnement_actif_jusqu_au` est renseignée et pas encore
        dépassée (inclusive : le dernier jour compte). Utilisée par
        programme.acces.eleve_peut_acceder — jamais recalculée ailleurs."""
        return (
            self.abonnement_actif_jusqu_au is not None
            and self.abonnement_actif_jusqu_au >= timezone.localdate()
        )


# ============================================================
#  CARTES FAHIMTA : codes prépayés que l'élève active pour créditer
#  son abonnement — voir comptes.cartes pour la génération/normalisation
#  des codes et comptes.views.ActiverCarteView pour l'activation.
# ============================================================

class CarteFahimta(models.Model):
    """Un code prépayé, généré par lot, à usage unique. Pas de péremption de
    carte elle-même (valable indéfiniment tant que non activée) — seul
    `duree_jours` détermine la durée d'abonnement CRÉDITÉE une fois activée."""

    class Statut(models.TextChoices):
        ACTIVE = "active", "Active"
        UTILISEE = "utilisee", "Utilisée"

    # Format "FH-XXXX-XXXX-XXXX" (voir comptes.cartes.generer_code_unique) —
    # stocké tel quel, avec les tirets : c'est la forme canonique comparée
    # à l'activation après normalisation de la saisie de l'élève.
    code = models.CharField("code", max_length=17, unique=True, db_index=True)
    duree_jours = models.PositiveIntegerField(
        "durée (jours)", default=30,
        help_text="Nombre de jours d'abonnement crédités à l'activation.",
    )
    statut = models.CharField(
        "statut", max_length=10, choices=Statut.choices, default=Statut.ACTIVE
    )
    utilisee_par = models.ForeignKey(
        "comptes.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cartes_activees", verbose_name="activée par",
    )
    date_activation = models.DateTimeField("date d'activation", null=True, blank=True)
    # Identifiant du lot de génération (ex. "lot-20260925-1030") — pas de FK
    # vers un modèle Lot séparé : un simple texte indexé suffit pour filtrer/
    # exporter un lot depuis l'admin, sans table supplémentaire à gérer.
    lot = models.CharField("lot", max_length=64, db_index=True)
    date_creation = models.DateTimeField("créée le", auto_now_add=True)

    # --- Module vendeur (fondations — voir comptes/admin_vendeurs_views.py) :
    # une carte est soit au STOCK CENTRAL (vendeur=None), soit ASSIGNÉE à un
    # vendeur. `limit_choices_to` ne restreint que les formulaires (admin
    # Django) — l'application réelle du rôle se fait côté vue (le queryset
    # de vendeurs valides y est explicitement filtré sur role=vendeur).
    vendeur = models.ForeignKey(
        "comptes.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cartes_assignees", verbose_name="vendeur",
        limit_choices_to={"role": "vendeur"},
    )
    date_assignation = models.DateTimeField("date d'assignation", null=True, blank=True)
    # Copie de User.commission_fcfa AU MOMENT de l'assignation — jamais
    # recalculée ensuite : modifier la commission d'un vendeur ne doit
    # jamais changer rétroactivement ce que rapportait une carte déjà en
    # circulation (voir comptes/admin_vendeurs_views.py).
    commission_figee = models.PositiveIntegerField(
        "commission figée (FCFA)", null=True, blank=True,
        help_text="Commission du vendeur au moment de l'assignation de cette carte.",
    )

    # --- Vente vendeur → élève (voir comptes/vendeur_views.py) : état
    # intermédiaire entre "assignée à un vendeur" et "activée". Le statut
    # reste ACTIVE tant que l'élève n'a pas lui-même activé le code (voir
    # ActiverCarteView) — attribuee_a ne fait que retirer la carte du stock
    # "disponible" du vendeur et la rendre visible (code en clair) côté
    # élève. limit_choices_to ne restreint que les formulaires admin, comme
    # pour `vendeur` ci-dessus — l'application réelle du rôle se fait dans
    # VendreCarteView.
    attribuee_a = models.ForeignKey(
        "comptes.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cartes_recues", verbose_name="attribuée à",
        limit_choices_to={"role": "eleve"},
    )
    date_attribution = models.DateTimeField("date d'attribution", null=True, blank=True)

    class Meta:
        verbose_name = "carte Fahimta"
        verbose_name_plural = "cartes Fahimta"
        ordering = ["-date_creation"]

    def __str__(self) -> str:
        return self.code


# ============================================================
#  PAIEMENT NITA : second moyen (avec les cartes Fahimta) de créditer
#  abonnement_actif_jusqu_au — voir comptes.nita pour le client HTTP NITA
#  (auth/achat/vérification, mode simulé NITA_MOCK) et comptes.nita_views
#  pour le flux complet (initier / callback / vérifier), avec sa
#  ré-vérification serveur systématique et son idempotence stricte.
# ============================================================

class PaiementNita(models.Model):
    """Une tentative de paiement NITA, du clic "Payer" jusqu'à confirmation
    (ou échec). `request_id` est LA clé de suivi côté Fahimta (généré ici,
    envoyé à NITA, renvoyé tel quel par son callback) ; `reference_nita` est
    LA référence que l'élève doit indiquer dans MYNITA — connue seulement
    une fois l'achat créé côté NITA (nullable jusque-là, voir
    comptes.nita_views.InitierPaiementNitaView)."""

    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        CONFIRME = "confirme", "Confirmé"
        ECHOUE = "echoue", "Échoué"

    user = models.ForeignKey(
        "comptes.User", on_delete=models.CASCADE, related_name="paiements_nita",
        limit_choices_to={"role": "eleve"},
    )
    # Copié depuis user.telephone au moment de l'initiation (pas juste une
    # FK) : garde une trace même si le téléphone du compte change ensuite,
    # et évite un aller-retour supplémentaire vers `user` pour la
    # normalisation NITA (voir comptes.nita.normaliser_telephone_nita).
    telephone = models.CharField("téléphone", max_length=20)
    montant = models.PositiveIntegerField("montant (FCFA)")
    duree_jours = models.PositiveIntegerField("durée (jours)")
    request_id = models.CharField("request ID", max_length=64, unique=True, db_index=True)
    reference_nita = models.CharField(
        "référence NITA", max_length=64, null=True, blank=True,
        help_text="Connue seulement après la création de l'achat côté NITA.",
    )
    statut = models.CharField(
        "statut", max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE,
    )
    date_creation = models.DateTimeField("créé le", auto_now_add=True)
    date_confirmation = models.DateTimeField("confirmé le", null=True, blank=True)

    class Meta:
        verbose_name = "paiement NITA"
        verbose_name_plural = "paiements NITA"
        ordering = ["-date_creation"]

    def __str__(self) -> str:
        return f"{self.request_id} ({self.statut})"


# ============================================================
#  ANTI-DOUBLON DES RAPPELS D'EXPIRATION (voir comptes/management/commands/
#  envoyer_rappels_abonnement.py) : une ligne = un rappel RÉELLEMENT envoyé
#  (créée seulement APRÈS un envoi réussi, jamais avant — voir la commande)
#  pour un (élève, seuil, échéance visée) donné. La contrainte d'unicité en
#  base est un garde-fou supplémentaire, pas le seul mécanisme anti-doublon.
# ============================================================

class RappelAbonnementEnvoye(models.Model):
    user = models.ForeignKey(
        "comptes.User", on_delete=models.CASCADE, related_name="rappels_abonnement_envoyes",
    )
    # Nombre de jours avant l'échéance au moment de l'envoi (10/5/3/1).
    seuil_jours = models.PositiveIntegerField("seuil (jours)")
    # Date d'échéance VISÉE par ce rappel — pas juste "aujourd'hui" : si
    # l'élève prolonge son abonnement entre deux rappels, une NOUVELLE
    # échéance donne droit à de nouveaux rappels (ce n'est plus la même
    # "campagne" d'expiration), sans quoi il ne recevrait plus jamais de
    # rappel après en avoir reçu un pour une échéance déjà dépassée depuis.
    date_expiration_visee = models.DateField("échéance visée")
    date_envoi = models.DateTimeField("envoyé le", auto_now_add=True)

    class Meta:
        verbose_name = "rappel d'abonnement envoyé"
        verbose_name_plural = "rappels d'abonnement envoyés"
        ordering = ["-date_envoi"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "seuil_jours", "date_expiration_visee"],
                name="unique_rappel_abonnement_par_seuil_et_echeance",
            )
        ]

    def __str__(self) -> str:
        return f"J-{self.seuil_jours} pour {self.user_id} (échéance {self.date_expiration_visee})"
