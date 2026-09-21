from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models

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
