from rest_framework import serializers

from .ia.prompts import SECTIONS

SECTIONS_CHOICES = list(SECTIONS.keys())


class GenererSectionSerializer(serializers.Serializer):
    notion_id = serializers.IntegerField()
    section = serializers.ChoiceField(choices=SECTIONS_CHOICES)
    # Opt-in : True -> réponse en flux SSE (génération longue, évite le H12 Heroku).
    # Absent ou False -> comportement historique (réponse JSON d'un bloc).
    stream = serializers.BooleanField(required=False, default=False)


class VerifierContenuSerializer(serializers.Serializer):
    section = serializers.ChoiceField(choices=SECTIONS_CHOICES)
    contenu = serializers.CharField(trim_whitespace=False, allow_blank=False)
    notion_id = serializers.IntegerField(required=False, allow_null=True)
