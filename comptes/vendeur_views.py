"""
Endpoints de l'espace VENDEUR lui-même (/api/vendeur/...) — réservés
IsVendeurActif, un vendeur n'agit JAMAIS que sur SES propres cartes
(request.user, jamais un id passé par le client).

GET  /api/vendeur/moi/             → profil + compteurs (disponibles/distribuées/activées)
GET  /api/vendeur/cartes/          → liste paginée des cartes du vendeur, SANS code (?etat=)
GET  /api/vendeur/verifier-eleve/  → prénom/nom d'un élève par téléphone, avant confirmation de vente
POST /api/vendeur/vendre-carte/    → transfère une ou plusieurs cartes disponibles (carte_ids) à un élève existant

Distinct de comptes/admin_vendeurs_views.py (back-office admin qui GÈRE les
vendeurs) — ici c'est le vendeur qui agit pour lui-même.
"""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CarteFahimta, User
from .permissions import IsVendeurActif
from .vendeur_serializers import (
    CarteVendeurSerializer,
    MoiVendeurSerializer,
    VendreCarteSerializer,
)

MESSAGE_ELEVE_INTROUVABLE = (
    "Aucun élève trouvé avec ce numéro. L'élève doit d'abord créer un compte."
)


class MoiVendeurView(APIView):
    """GET /api/vendeur/moi/ — profil du vendeur connecté + ses 3 compteurs
    (voir CarteFahimta : disponible = active ET attribuee_a IS NULL ;
    distribuée = active ET attribuee_a NOT NULL ; activée = statut utilisee)."""

    permission_classes = [IsVendeurActif]

    def get(self, request):
        vendeur = request.user
        agregats = CarteFahimta.objects.filter(vendeur=vendeur).aggregate(
            disponibles=Count(
                "id",
                filter=Q(statut=CarteFahimta.Statut.ACTIVE, attribuee_a__isnull=True),
            ),
            distribuees=Count(
                "id",
                filter=Q(statut=CarteFahimta.Statut.ACTIVE, attribuee_a__isnull=False),
            ),
            activees=Count("id", filter=Q(statut=CarteFahimta.Statut.UTILISEE)),
        )
        data = {
            "id": vendeur.id,
            "prenom": vendeur.prenom,
            "nom": vendeur.nom,
            "telephone": vendeur.telephone,
            "commission_fcfa": vendeur.commission_fcfa,
            "cartes_disponibles": agregats["disponibles"],
            "cartes_distribuees": agregats["distribuees"],
            "cartes_activees": agregats["activees"],
        }
        return Response(MoiVendeurSerializer(data).data)


class MesCartesVendeurView(generics.ListAPIView):
    """GET /api/vendeur/cartes/?etat=disponible|distribuee|activee — cartes
    DU vendeur connecté uniquement. Sert à la fois de "stock" (etat=disponible)
    et d'historique des ventes (etat=distribuee/activee) — voir CarteVendeurSerializer
    pour la règle des 3 états. Jamais de champ `code`."""

    serializer_class = CarteVendeurSerializer
    permission_classes = [IsVendeurActif]

    def get_queryset(self):
        queryset = (
            CarteFahimta.objects.filter(vendeur=self.request.user)
            .select_related("attribuee_a")
            .order_by("-date_attribution", "-date_assignation")
        )

        etat = self.request.query_params.get("etat")
        if etat == "disponible":
            queryset = queryset.filter(statut=CarteFahimta.Statut.ACTIVE, attribuee_a__isnull=True)
        elif etat == "distribuee":
            queryset = queryset.filter(statut=CarteFahimta.Statut.ACTIVE, attribuee_a__isnull=False)
        elif etat == "activee":
            queryset = queryset.filter(statut=CarteFahimta.Statut.UTILISEE)

        return queryset


class VerifierEleveView(APIView):
    """GET /api/vendeur/verifier-eleve/?telephone=+227XXXXXXXX — vérifie
    l'existence d'un compte élève AVANT la vente, pour que le frontend
    affiche son nom en confirmation (voir VendreCarteModal.tsx). Ne modifie
    rien : la vraie vérification (et le verrou) est refaite dans
    VendreCarteView, cet endpoint n'est qu'un confort d'UI."""

    permission_classes = [IsVendeurActif]

    def get(self, request):
        telephone = (request.query_params.get("telephone") or "").strip().replace(" ", "")
        eleve = User.objects.filter(telephone=telephone, role=User.Role.ELEVE).first()
        if eleve is None:
            return Response({"detail": MESSAGE_ELEVE_INTROUVABLE}, status=status.HTTP_404_NOT_FOUND)
        return Response({"prenom": eleve.prenom, "nom": eleve.nom})


class VendreCarteView(APIView):
    """
    POST /api/vendeur/vendre-carte/ — { "telephone_eleve": "...", "carte_ids": [N, ...] }

    Le vendeur sélectionne lui-même une ou plusieurs cartes (cases à cocher
    côté frontend, voir VendreCarteModal.tsx) — jamais une simple quantité.

    Transaction atomique + select_for_update() sur les cartes candidates :
    TOUT ou RIEN. Si une seule des cartes demandées ne correspond plus au
    vendeur connecté, n'est plus "active", ou a déjà été attribuée entre
    l'affichage de la liste et la confirmation (vente concurrente), la
    requête ENTIÈRE est rejetée — aucune des cartes demandées n'est vendue
    partiellement. Deux ventes concurrentes visant la ou les mêmes cartes ne
    peuvent donc jamais toutes les deux réussir.

    Le vendeur ne voit JAMAIS le code — la réponse de succès ne renvoie que
    le nom de l'élève et le nombre de cartes, jamais les cartes elles-mêmes.
    """

    permission_classes = [IsVendeurActif]

    def post(self, request):
        vendeur = request.user
        serializer = VendreCarteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        telephone_eleve = serializer.validated_data["telephone_eleve"]
        carte_ids = serializer.validated_data["carte_ids"]

        eleve = User.objects.filter(telephone=telephone_eleve, role=User.Role.ELEVE).first()
        if eleve is None:
            return Response({"detail": MESSAGE_ELEVE_INTROUVABLE}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # select_for_update() verrouille les lignes AVANT de vérifier leur
            # éligibilité : une vente concurrente sur l'une de ces cartes
            # attend ce verrou, puis reconstate (une fois relâché) que la
            # carte n'est plus disponible — elle échoue alors proprement,
            # jamais un double-transfert.
            cartes = list(
                CarteFahimta.objects.select_for_update().filter(
                    id__in=carte_ids,
                    vendeur=vendeur,
                    statut=CarteFahimta.Statut.ACTIVE,
                    attribuee_a__isnull=True,
                )
            )

            if len(cartes) != len(carte_ids):
                return Response(
                    {
                        "detail": (
                            "Une ou plusieurs cartes sélectionnées ne sont plus "
                            "disponibles. Rafraîchis la liste et réessaie."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ids_verrouilles = [carte.id for carte in cartes]
            maintenant = timezone.now()
            CarteFahimta.objects.filter(id__in=ids_verrouilles).update(
                attribuee_a=eleve, date_attribution=maintenant
            )

        quantite = len(ids_verrouilles)
        if quantite > 1:
            message = (
                f"{quantite} cartes envoyées à {eleve.prenom} {eleve.nom}. "
                "Il peut maintenant les activer depuis son espace."
            )
        else:
            message = (
                f"1 carte envoyée à {eleve.prenom} {eleve.nom}. "
                "Il peut maintenant l'activer depuis son espace."
            )

        return Response(
            {
                "message": message,
                "quantite": quantite,
                "eleve": {"prenom": eleve.prenom, "nom": eleve.nom},
            }
        )
