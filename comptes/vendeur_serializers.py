"""
Serializers pour l'espace VENDEUR lui-même (/api/vendeur/...) — distinct du
back-office admin (comptes/admin_vendeurs_serializers.py, qui gère les
vendeurs DEPUIS l'admin). Un vendeur connecté ici n'agit que sur SES
propres cartes (voir vendeur_views.py, toujours filtré sur request.user).

RÈGLE ABSOLUE : aucun serializer de ce module n'expose jamais `code` — le
vendeur ne voit jamais un code de carte, à aucun moment (voir
CarteVendeurSerializer, qui liste volontairement `code` hors de Meta.fields).
"""

from rest_framework import serializers

from .models import CarteFahimta


class EleveInfoSerializer(serializers.Serializer):
    """Sous-objet minimal pour l'élève destinataire d'une carte — même
    esprit que UtiliseeParSerializer/VendeurInfoSerializer côté admin."""

    prenom = serializers.CharField()
    nom = serializers.CharField()
    telephone = serializers.CharField()


class MoiVendeurSerializer(serializers.Serializer):
    """GET /api/vendeur/moi/ — profil + compteurs du vendeur connecté. Les
    compteurs sont calculés dans la vue (pas ici) car ils dépendent d'une
    requête sur CarteFahimta, pas d'un champ direct de User."""

    id = serializers.IntegerField()
    prenom = serializers.CharField()
    nom = serializers.CharField()
    telephone = serializers.CharField()
    commission_fcfa = serializers.IntegerField()
    cartes_disponibles = serializers.IntegerField()
    cartes_distribuees = serializers.IntegerField()
    cartes_activees = serializers.IntegerField()


class CarteVendeurSerializer(serializers.Serializer):
    """
    GET /api/vendeur/cartes/ — une carte assignée au vendeur connecté, SANS
    le champ `code` (volontairement absent, voir docstring de module).

    `etat` résume la règle métier des 3 états (voir comptes.models.
    CarteFahimta) pour éviter au frontend de la recalculer depuis
    statut/attribuee_a.
    """

    id = serializers.IntegerField()
    duree_jours = serializers.IntegerField()
    date_assignation = serializers.DateTimeField()
    attribuee_a = serializers.SerializerMethodField()
    date_attribution = serializers.DateTimeField()
    date_activation = serializers.DateTimeField()
    etat = serializers.SerializerMethodField()

    def get_attribuee_a(self, obj) -> dict | None:
        if not obj.attribuee_a_id:
            return None
        return EleveInfoSerializer(obj.attribuee_a).data

    def get_etat(self, obj) -> str:
        if obj.statut == CarteFahimta.Statut.UTILISEE:
            return "activee"
        if obj.attribuee_a_id:
            return "distribuee"
        return "disponible"


# --- POST /api/vendeur/vendre-carte/ ---

class VendreCarteSerializer(serializers.Serializer):
    """Juste la validation de forme — la logique métier (élève introuvable,
    cartes indisponibles, verrouillage) vit dans la vue, qui a besoin d'un
    verrou transactionnel (select_for_update). `carte_ids` : le vendeur
    choisit lui-même une ou plusieurs cartes via des cases à cocher
    (voir VendreCarteModal.tsx côté frontend) — jamais une simple quantité,
    pour que la sélection soit explicite et vérifiable une à une côté vue."""

    telephone_eleve = serializers.CharField(max_length=20, allow_blank=False)
    carte_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=1000
    )

    def validate_telephone_eleve(self, value: str) -> str:
        return (value or "").strip().replace(" ", "")

    def validate_carte_ids(self, value: list[int]) -> list[int]:
        # dédoublonne (en gardant l'ordre) : cocher deux fois la même carte
        # ne doit jamais compter double dans le total/la commission affichés
        # au vendeur, ni être traité comme deux ventes distinctes.
        vus: set[int] = set()
        dedupliques = []
        for id_ in value:
            if id_ not in vus:
                vus.add(id_)
                dedupliques.append(id_)
        return dedupliques
