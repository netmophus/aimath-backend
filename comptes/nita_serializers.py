"""Serializers pour le paiement NITA (comptes/nita_views.py) — validation de
forme uniquement, la logique métier (appel NITA, crédit, idempotence) vit
dans les vues (voir comptes/nita.py)."""

from rest_framework import serializers

from .nita import PLANS_NITA


class InitierPaiementNitaSerializer(serializers.Serializer):
    """POST /api/eleve/nita/initier/ — { "plan": "mensuel" }."""

    plan = serializers.ChoiceField(choices=list(PLANS_NITA.keys()))


class VerifierPaiementNitaSerializer(serializers.Serializer):
    """POST /api/eleve/nita/verifier/ — { "requestId": "FAH-..." }."""

    requestId = serializers.CharField(max_length=64, allow_blank=False)


class MockConfirmerSerializer(serializers.Serializer):
    """POST /api/nita/mock/confirmer/ — { "requestId": "FAH-..." } (actif
    UNIQUEMENT si settings.NITA_MOCK, voir NitaMockConfirmerView)."""

    requestId = serializers.CharField(max_length=64, allow_blank=False)
