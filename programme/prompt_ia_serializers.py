"""Serializer pour le CRUD des prompts personnalisés par section (voir
prompt_ia_views.py). Volontairement séparé de lecon_serializers.py : un
prompt personnalisé est rattaché à la Notion, pas à la Lecon.
"""

from rest_framework import serializers

from .ia.prompts import SECTIONS

# Doit rester synchronisé avec programme.ia.prompts.SECTIONS — même
# précédent que programme.ia_serializers.SECTIONS_CHOICES.
SECTIONS_CLES = list(SECTIONS.keys())


class PromptsNotionSerializer(serializers.Serializer):
    """Un champ texte par section générable. Chaîne vide = pas de prompt
    personnalisé pour cette section (comportement de génération par défaut).
    """

    histoire = serializers.CharField(allow_blank=True, required=False, default="")
    objectifs = serializers.CharField(allow_blank=True, required=False, default="")
    prerequis = serializers.CharField(allow_blank=True, required=False, default="")
    cours = serializers.CharField(allow_blank=True, required=False, default="")
    demonstrations = serializers.CharField(allow_blank=True, required=False, default="")
    a_retenir = serializers.CharField(allow_blank=True, required=False, default="")
    exercices = serializers.CharField(allow_blank=True, required=False, default="")
    sujet_examen = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, attrs: dict) -> dict:
        inconnues = set(self.initial_data.keys()) - set(SECTIONS_CLES)
        if inconnues:
            raise serializers.ValidationError(
                f"Section(s) inconnue(s) : {', '.join(sorted(inconnues))}."
            )
        return attrs
