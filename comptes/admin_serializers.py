from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User
from .serializers import TELEPHONE_RE


class AdminCompteSerializer(serializers.ModelSerializer):
    """
    Représentation d'un compte pour le dashboard admin. Lecture seule :
    les mutations passent par les actions dédiées (approuver/rejeter/
    suspendre/reactiver) ou par CreerCompteSerializer / ModifierCompteSerializer,
    jamais par une mise à jour générique de ce serializer.
    """

    niveau = serializers.SerializerMethodField()
    serie = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "prenom", "nom", "telephone", "email",
            "role", "statut", "date_inscription",
            "niveau", "serie", "motif_rejet", "doit_changer_mdp",
        ]
        read_only_fields = fields

    def get_niveau(self, obj: User) -> dict | None:
        return {"id": obj.niveau_id, "nom": obj.niveau.nom} if obj.niveau_id else None

    def get_serie(self, obj: User) -> dict | None:
        return {"id": obj.serie_id, "nom": obj.serie.nom} if obj.serie_id else None


class RejeterCompteSerializer(serializers.Serializer):
    """Corps optionnel de POST /api/admin/comptes/{id}/rejeter/."""

    motif = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class CreerCompteSerializer(serializers.ModelSerializer):
    """
    POST /api/admin/comptes/ : création d'un compte ENSEIGNANT ou ADMIN par
    un administrateur. Contrairement à l'inscription publique (élèves), le
    compte créé est directement actif, avec un mot de passe provisoire que
    l'intéressé devra changer (doit_changer_mdp=True).
    """

    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["prenom", "nom", "telephone", "email", "role", "password"]

    def validate_role(self, value: str) -> str:
        if value not in (User.Role.ENSEIGNANT, User.Role.ADMIN):
            raise serializers.ValidationError(
                'Le rôle doit être "enseignant" ou "admin".'
            )
        return value

    def validate_telephone(self, value: str) -> str:
        value = (value or "").strip().replace(" ", "")
        if not TELEPHONE_RE.fullmatch(value):
            raise serializers.ValidationError(
                "Le numéro doit être au format +227 suivi de 8 chiffres "
                "(ex. +22790000000)."
            )
        if User.objects.filter(telephone=value).exists():
            raise serializers.ValidationError("Ce numéro de téléphone est déjà utilisé.")
        return value

    def validate(self, attrs):
        # Utilisateur "factice" pour les validateurs sensibles au contexte
        # (ex. UserAttributeSimilarityValidator comparant au prénom/nom).
        utilisateur_temporaire = User(
            telephone=attrs.get("telephone"),
            prenom=attrs.get("prenom", ""),
            nom=attrs.get("nom", ""),
        )
        try:
            validate_password(attrs["password"], user=utilisateur_temporaire)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password")
        role = validated_data["role"]
        return User.objects.create_user(
            password=password,
            statut=User.Statut.ACTIF,
            doit_changer_mdp=True,
            is_staff=(role == User.Role.ADMIN),
            is_superuser=False,
            **validated_data,
        )


class ModifierCompteSerializer(serializers.ModelSerializer):
    """
    PATCH /api/admin/comptes/{id}/ : mise à jour limitée et volontairement
    étroite — ni le rôle ni le téléphone ne se changent "à la légère" ici
    (le rôle conditionne des permissions, le téléphone est l'identifiant de
    connexion). Le changement de statut passe par approuver/rejeter/
    suspendre/reactiver, pas par ce serializer.
    """

    class Meta:
        model = User
        fields = ["prenom", "nom", "email"]
