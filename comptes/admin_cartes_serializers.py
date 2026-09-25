"""
Serializers admin pour les cartes Fahimta (back-office custom, PAS l'admin
Django — voir comptes/admin.py pour celui-ci, qui réutilise les mêmes
fonctions de comptes/cartes.py sans dupliquer la logique).
"""

from rest_framework import serializers

from .cartes import code_masque, etat_carte
from .models import CarteFahimta


class UtiliseeParSerializer(serializers.Serializer):
    """Sous-objet minimal — jamais le serializer complet d'un compte (qui
    exposerait bien plus qu'un nom/téléphone à afficher dans une liste).
    Réutilisé tel quel pour `attribuee_a` (même forme id/nom/prenom/
    téléphone) : voir CarteFahimtaAdminSerializer.get_attribuee_a."""

    id = serializers.IntegerField()
    nom = serializers.CharField()
    prenom = serializers.CharField()
    telephone = serializers.CharField()


class VendeurInfoSerializer(serializers.Serializer):
    """Sous-objet minimal pour `vendeur` sur une carte — même esprit que
    UtiliseeParSerializer ci-dessus (jamais le serializer complet)."""

    id = serializers.IntegerField()
    nom = serializers.CharField()
    prenom = serializers.CharField()


class CarteFahimtaAdminSerializer(serializers.ModelSerializer):
    """GET /api/admin/cartes/ (et /api/admin/vendeurs/{id}/, filtré via
    ?vendeur=, voir CarteFahimtaAdminViewSet.get_queryset) — code MASQUÉ tant
    que la carte est active (voir code_masque, partagée avec l'admin
    Django). Réutilisé tel quel pour la liste des cartes d'UN vendeur :
    aucun serializer séparé pour cette vue, seul le queryset filtre.

    `etat` : voir comptes.cartes.etat_carte, LE calcul de référence du
    vocabulaire de suivi (stock_central/assignee/vendue/utilisee), le même
    que le filtre ?etat= (comptes.cartes.filtre_etat) et l'action `stats` —
    jamais recalculé différemment ici."""

    code = serializers.SerializerMethodField()
    etat = serializers.SerializerMethodField()
    utilisee_par = serializers.SerializerMethodField()
    vendeur = serializers.SerializerMethodField()
    attribuee_a = serializers.SerializerMethodField()

    class Meta:
        model = CarteFahimta
        fields = [
            "id", "code", "statut", "etat", "duree_jours", "lot",
            "vendeur", "commission_figee", "date_assignation",
            "attribuee_a", "date_attribution",
            "utilisee_par", "date_activation",
            "date_creation",
        ]
        read_only_fields = fields

    def get_code(self, obj: CarteFahimta) -> str:
        return code_masque(obj)

    def get_etat(self, obj: CarteFahimta) -> str:
        return etat_carte(obj)

    def get_utilisee_par(self, obj: CarteFahimta) -> dict | None:
        if not obj.utilisee_par_id:
            return None
        return UtiliseeParSerializer(obj.utilisee_par).data

    def get_vendeur(self, obj: CarteFahimta) -> dict | None:
        if not obj.vendeur_id:
            return None
        return VendeurInfoSerializer(obj.vendeur).data

    def get_attribuee_a(self, obj: CarteFahimta) -> dict | None:
        if not obj.attribuee_a_id:
            return None
        return UtiliseeParSerializer(obj.attribuee_a).data


class CarteFahimtaGenereeSerializer(serializers.ModelSerializer):
    """Réponse de POST /api/admin/cartes/generer/ : code EN CLAIR — c'est le
    seul moment (avec l'export CSV) où les codes non masqués sont exposés,
    volontairement, pour affichage/impression immédiate du lot fraîchement
    créé."""

    class Meta:
        model = CarteFahimta
        fields = ["id", "code", "duree_jours", "lot", "date_creation"]
        read_only_fields = fields


class GenererLotSerializer(serializers.Serializer):
    """Corps de POST /api/admin/cartes/generer/."""

    quantite = serializers.IntegerField(min_value=1, max_value=1000)
    duree_jours = serializers.IntegerField(min_value=1, default=30)
    # Optionnel et volontairement absent du formulaire frontend (voir la
    # page /admin/cartes) : un identifiant de lot auto-généré depuis
    # l'horodatage suffit pour l'usage courant, mais l'API reste utilisable
    # avec un lot nommé (tests, scripts) sans changer ce serializer.
    lot = serializers.CharField(required=False, allow_blank=True, max_length=64)
