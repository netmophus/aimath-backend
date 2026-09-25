"""
Serializers admin pour le module vendeur (back-office custom).

Réutilise ce qui existe déjà : TELEPHONE_RE et le schéma de validation mot
de passe/téléphone de comptes/serializers.py (même logique que
CreerCompteSerializer, jamais dupliquée — seule la FORME du payload diffère,
imposée par la consigne : `mot_de_passe` au lieu de `password`, rôle
toujours vendeur).
"""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User
from .serializers import TELEPHONE_RE


class VendeurAdminSerializer(serializers.ModelSerializer):
    """GET (liste/détail) — les compteurs viennent des annotations posées
    par VendeurAdminViewSet.get_queryset(), jamais recalculés ici avec une
    requête supplémentaire par vendeur (éviterait un N+1).

    Vocabulaire des 4 compteurs (voir comptes.cartes, respecté partout) :
    `cartes_assignees` = TOTAL de cartes jamais assignées à ce vendeur (peu
    importe leur devenir ensuite) ; les trois suivants s'additionnent pour
    retrouver ce total : `cartes_disponibles` (encore chez lui, pas données à
    un élève), `cartes_vendues` (données à un élève, pas encore activées),
    `cartes_activees` (l'élève a activé son abonnement)."""

    # source= : voir VendeurAdminViewSet.get_queryset(), les annotations
    # portent le préfixe total_ pour ne pas entrer en conflit avec le
    # related_name "cartes_assignees" de CarteFahimta.vendeur.
    cartes_assignees = serializers.IntegerField(source="total_cartes_assignees", read_only=True)
    cartes_disponibles = serializers.IntegerField(source="total_cartes_disponibles", read_only=True)
    cartes_vendues = serializers.IntegerField(source="total_cartes_vendues", read_only=True)
    cartes_activees = serializers.IntegerField(source="total_cartes_activees", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "prenom", "nom", "telephone", "commission_fcfa",
            "ville", "quartier", "ecole_ou_point_vente",
            "date_inscription",
            "cartes_assignees", "cartes_disponibles", "cartes_vendues", "cartes_activees",
        ]
        read_only_fields = fields


class CreerVendeurSerializer(serializers.ModelSerializer):
    """POST /api/admin/vendeurs/ — { nom, prenom, telephone, mot_de_passe,
    commission_fcfa }. Le compte créé est directement actif (comme un
    enseignant/admin créé par un admin, voir CreerCompteSerializer), avec un
    mot de passe provisoire (doit_changer_mdp=True)."""

    mot_de_passe = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "prenom", "nom", "telephone", "mot_de_passe", "commission_fcfa",
            "ville", "quartier", "ecole_ou_point_vente",
        ]

    def validate_telephone(self, value: str) -> str:
        value = (value or "").strip().replace(" ", "")
        if not TELEPHONE_RE.fullmatch(value):
            raise serializers.ValidationError(
                "Le numéro doit être au format +227 suivi de 8 chiffres (ex. +22790000000)."
            )
        if User.objects.filter(telephone=value).exists():
            raise serializers.ValidationError("Ce numéro de téléphone est déjà utilisé.")
        return value

    def validate(self, attrs):
        utilisateur_temporaire = User(
            telephone=attrs.get("telephone"),
            prenom=attrs.get("prenom", ""),
            nom=attrs.get("nom", ""),
        )
        try:
            validate_password(attrs["mot_de_passe"], user=utilisateur_temporaire)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"mot_de_passe": list(exc.messages)})
        return attrs

    def create(self, validated_data: dict) -> User:
        mot_de_passe = validated_data.pop("mot_de_passe")
        return User.objects.create_user(
            password=mot_de_passe,
            role=User.Role.VENDEUR,
            statut=User.Statut.ACTIF,
            doit_changer_mdp=True,
            is_staff=False,
            is_superuser=False,
            **validated_data,
        )


class ModifierVendeurSerializer(serializers.ModelSerializer):
    """PATCH /api/admin/vendeurs/{id}/ — prenom/nom/commission_fcfa
    uniquement (téléphone = identifiant de connexion, non modifiable ici,
    même convention que ModifierCompteSerializer). IMPORTANT : changer
    commission_fcfa ne touche JAMAIS commission_figee des cartes déjà
    assignées — voir CarteFahimta.commission_figee et les deux actions
    d'assignation dans admin_vendeurs_views.py."""

    class Meta:
        model = User
        fields = ["prenom", "nom", "commission_fcfa", "ville", "quartier", "ecole_ou_point_vente"]


# --- Assignation de cartes ---

class GenererPourVendeurSerializer(serializers.Serializer):
    """POST /api/admin/vendeurs/generer-pour-vendeur/."""

    vendeur_id = serializers.PrimaryKeyRelatedField(
        source="vendeur", queryset=User.objects.filter(role=User.Role.VENDEUR)
    )
    quantite = serializers.IntegerField(min_value=1, max_value=1000)
    duree_jours = serializers.IntegerField(min_value=1, default=30)


class AssignerExistantesSerializer(serializers.Serializer):
    """POST /api/admin/vendeurs/assigner-existantes/."""

    vendeur_id = serializers.PrimaryKeyRelatedField(
        source="vendeur", queryset=User.objects.filter(role=User.Role.VENDEUR)
    )
    quantite = serializers.IntegerField(min_value=1, max_value=1000)
