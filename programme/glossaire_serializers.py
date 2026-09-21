"""
Serializers admin pour le glossaire (TermeGlossaire) : lecture ET écriture.

Le slug est optionnel en écriture — laissé vide, il est dérivé de `terme`
et son unicité garantie automatiquement par TermeGlossaire.save() (voir
models.py). S'il est fourni explicitement, sa unicité est validée ici avec
un message FR (le champ modèle SlugField(unique=True) suffirait à générer
un validateur, mais avec le message par défaut en anglais).
"""

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Lecon, TermeGlossaire


class LeconLieeSerializer(serializers.ModelSerializer):
    """Représentation légère de la leçon liée — pas le détail complet,
    juste de quoi l'identifier et savoir où elle en est."""

    class Meta:
        model = Lecon
        fields = ["id", "titre", "statut"]


class TermeGlossaireSerializer(serializers.ModelSerializer):
    """Lecture (liste ET détail — le glossaire est léger, pas besoin de
    deux serializers séparés comme pour Lecon)."""

    lecon_liee = LeconLieeSerializer(read_only=True)

    class Meta:
        model = TermeGlossaire
        fields = ["id", "terme", "slug", "definition", "exemple", "lecon_liee", "cree_le", "modifie_le"]


class TermeGlossaireEcritureSerializer(serializers.ModelSerializer):
    """Création / modification. `terme` et `definition` sont requis par le
    modèle (ni l'un ni l'autre n'a blank=True) ; `slug` et `exemple` sont
    optionnels."""

    slug = serializers.SlugField(
        required=False,
        allow_blank=True,
        validators=[UniqueValidator(
            queryset=TermeGlossaire.objects.all(),
            message="Ce slug est déjà utilisé par un autre terme.",
        )],
    )
    lecon_liee = serializers.PrimaryKeyRelatedField(
        queryset=Lecon.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = TermeGlossaire
        fields = ["id", "terme", "slug", "definition", "exemple", "lecon_liee"]
        read_only_fields = ["id"]

    def validate_terme(self, valeur: str) -> str:
        if not valeur.strip():
            raise serializers.ValidationError("Le terme ne peut pas être vide.")
        return valeur

    def validate_definition(self, valeur: str) -> str:
        if not valeur.strip():
            raise serializers.ValidationError("La définition ne peut pas être vide.")
        return valeur
