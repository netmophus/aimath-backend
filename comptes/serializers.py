import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from programme.models import Niveau, Serie

from .models import User

TELEPHONE_RE = re.compile(r"^\+227\d{8}$")


class InscriptionEleveSerializer(serializers.ModelSerializer):
    """Inscription d'un élève : crée le compte en_attente (pas de jeton)."""

    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label="Confirmation du mot de passe")
    niveau = serializers.PrimaryKeyRelatedField(queryset=Niveau.objects.all())
    serie = serializers.PrimaryKeyRelatedField(
        queryset=Serie.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = [
            "prenom", "nom", "telephone", "email",
            "password", "password2", "niveau", "serie",
        ]

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
        password2 = attrs.pop("password2")
        if attrs["password"] != password2:
            raise serializers.ValidationError(
                {"password2": "Les mots de passe ne correspondent pas."}
            )

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

        niveau = attrs["niveau"]
        serie = attrs.get("serie")
        niveau_a_des_series = niveau.series.exists()

        if niveau_a_des_series and serie is None:
            raise serializers.ValidationError(
                {"serie": "Une série est requise pour ce niveau."}
            )
        if not niveau_a_des_series and serie is not None:
            raise serializers.ValidationError(
                {"serie": "Ce niveau ne comporte pas de série."}
            )
        if serie is not None and serie.niveau_id != niveau.id:
            raise serializers.ValidationError(
                {"serie": "Cette série n'appartient pas au niveau choisi."}
            )

        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password")
        return User.objects.create_user(
            role=User.Role.ELEVE,
            statut=User.Statut.EN_ATTENTE,
            password=password,
            **validated_data,
        )


class TelephoneTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Connexion par téléphone + mot de passe. N'émet des jetons que si le
    compte est "actif" ; sinon lève une erreur 403 avec un message adapté
    au statut du compte.
    """

    MESSAGES_STATUT = {
        User.Statut.EN_ATTENTE: "Ce compte est en attente de validation par un administrateur.",
        User.Statut.REJETE: "Cette demande d'inscription a été rejetée.",
        User.Statut.SUSPENDU: "Ce compte a été suspendu.",
    }

    def validate(self, attrs):
        # Normalise le téléphone (espaces éventuels) avant authentification.
        attrs[self.username_field] = (attrs.get(self.username_field) or "").strip().replace(" ", "")

        data = super().validate(attrs)
        user: User = self.user

        if user.statut != User.Statut.ACTIF:
            message = self.MESSAGES_STATUT.get(user.statut, "Ce compte n'est pas actif.")
            raise PermissionDenied(message)

        data["role"] = user.role
        data["prenom"] = user.prenom
        data["nom"] = user.nom
        data["statut"] = user.statut
        data["niveau"] = {"id": user.niveau_id, "nom": user.niveau.nom} if user.niveau_id else None
        data["serie"] = {"id": user.serie_id, "nom": user.serie.nom} if user.serie_id else None

        return data


class MeSerializer(serializers.ModelSerializer):
    """Profil de l'utilisateur connecté."""

    niveau = serializers.CharField(source="niveau.nom", default=None, read_only=True)
    serie = serializers.CharField(source="serie.nom", default=None, read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "telephone", "email", "prenom", "nom",
            "role", "statut", "niveau", "serie", "date_inscription",
        ]
        read_only_fields = fields
