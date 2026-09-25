"""
Endpoints admin pour le module vendeur (back-office custom) — réservés
IsAdminRole, même garde que AdminCompteViewSet/CarteFahimtaAdminViewSet.

GET/POST   /api/admin/vendeurs/                        → liste / création
GET/PATCH  /api/admin/vendeurs/{id}/                    → détail / modification
POST       /api/admin/vendeurs/generer-pour-vendeur/    → génère un lot ET l'assigne
POST       /api/admin/vendeurs/assigner-existantes/     → assigne depuis le stock central

Pas d'endpoint dédié pour "les cartes d'un vendeur" : la page de détail
vendeur du back-office réutilise GET /api/admin/cartes/?vendeur=<id>
(CarteFahimtaAdminViewSet, déjà masqué/paginé/trié) — voir son docstring.

Aucune suppression de vendeur (pas de DestroyModelMixin) : hors périmètre de
cette étape, et supprimer un vendeur avec des cartes déjà assignées serait
une opération à part entière (que faire des cartes ? du solde de
commission ?), pas un simple CRUD.
"""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .admin_cartes_serializers import CarteFahimtaAdminSerializer
from .admin_vendeurs_serializers import (
    AssignerExistantesSerializer,
    CreerVendeurSerializer,
    GenererPourVendeurSerializer,
    ModifierVendeurSerializer,
    VendeurAdminSerializer,
)
from .cartes import generer_lot
from .models import CarteFahimta, User
from .permissions import IsAdminRole


class VendeurAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAdminRole]
    serializer_class = VendeurAdminSerializer

    def get_queryset(self):
        # Annotations posées ICI (pas dans le serializer) : elles doivent
        # être présentes aussi bien pour list() que pour retrieve()/create()/
        # update(), qui passent tous par get_queryset() (directement ou via
        # get_object()).
        # Préfixe total_ obligatoire : une annotation ne peut pas porter le
        # même nom que la relation qu'elle agrège ("cartes_assignees" est
        # déjà le related_name de CarteFahimta.vendeur sur User) — Django
        # lève ValueError sinon. Le serializer remappe vers les noms de la
        # consigne via `source=` (voir VendeurAdminSerializer).
        #
        # 4 compteurs qui se décomposent (disponibles + vendues + activées =
        # assignées) — vocabulaire de comptes.cartes, respecté partout :
        # disponibles = encore chez le vendeur (attribuee_a IS NULL) ;
        # vendues = données à un élève, pas encore activées (attribuee_a
        # défini, statut encore active) ; activées = statut utilisee.
        return (
            User.objects.filter(role=User.Role.VENDEUR)
            .annotate(
                total_cartes_assignees=Count("cartes_assignees", distinct=True),
                total_cartes_disponibles=Count(
                    "cartes_assignees",
                    filter=Q(
                        cartes_assignees__statut=CarteFahimta.Statut.ACTIVE,
                        cartes_assignees__attribuee_a__isnull=True,
                    ),
                    distinct=True,
                ),
                total_cartes_vendues=Count(
                    "cartes_assignees",
                    filter=Q(
                        cartes_assignees__statut=CarteFahimta.Statut.ACTIVE,
                        cartes_assignees__attribuee_a__isnull=False,
                    ),
                    distinct=True,
                ),
                total_cartes_activees=Count(
                    "cartes_assignees",
                    filter=Q(cartes_assignees__statut=CarteFahimta.Statut.UTILISEE),
                    distinct=True,
                ),
            )
            .order_by("-date_inscription")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return CreerVendeurSerializer
        if self.action in ("update", "partial_update"):
            return ModifierVendeurSerializer
        return VendeurAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendeur = serializer.save()
        # Re-fetch via get_queryset() : un User fraîchement créé n'a pas les
        # annotations cartes_* posées à l'instant (0 partout, mais il faut
        # les avoir sur l'objet pour que VendeurAdminSerializer les lise).
        vendeur = self.get_queryset().get(pk=vendeur.pk)
        return Response(VendeurAdminSerializer(vendeur).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        vendeur = serializer.save()
        vendeur = self.get_queryset().get(pk=vendeur.pk)
        return Response(VendeurAdminSerializer(vendeur).data)

    @action(detail=False, methods=["post"], url_path="generer-pour-vendeur")
    def generer_pour_vendeur(self, request):
        """generer_lot() (comptes/cartes.py, MÊME fonction que
        /api/admin/cartes/generer/) puis assignation — dans LA MÊME
        transaction : soit les cartes sont créées ET assignées, soit rien du
        tout (pas de lot orphelin au stock central si l'assignation
        échouait, même si en pratique elle ne peut plus échouer une fois le
        vendeur validé par le serializer)."""
        serializer = GenererPourVendeurSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendeur: User = serializer.validated_data["vendeur"]
        quantite = serializer.validated_data["quantite"]
        duree_jours = serializer.validated_data["duree_jours"]

        with transaction.atomic():
            cartes = generer_lot(quantite=quantite, duree_jours=duree_jours)
            ids = [carte.id for carte in cartes]
            CarteFahimta.objects.filter(id__in=ids).update(
                vendeur=vendeur,
                date_assignation=timezone.now(),
                commission_figee=vendeur.commission_fcfa,
            )

        cartes_assignees = CarteFahimta.objects.filter(id__in=ids).select_related("vendeur", "utilisee_par")
        return Response(
            {
                "lot": cartes[0].lot,
                "quantite": quantite,
                "cartes": CarteFahimtaAdminSerializer(cartes_assignees, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="assigner-existantes")
    def assigner_existantes(self, request):
        """Assigne N cartes du STOCK CENTRAL (vendeur=None, statut=active).
        select_for_update() verrouille les lignes candidates jusqu'à la fin
        de la transaction : deux assignations concurrentes ne peuvent
        jamais piocher dans le même sous-ensemble de cartes (l'une attend
        que l'autre relâche son verrou, puis reconstate un stock réduit)."""
        serializer = AssignerExistantesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vendeur: User = serializer.validated_data["vendeur"]
        quantite = serializer.validated_data["quantite"]

        with transaction.atomic():
            cartes_dispo = list(
                CarteFahimta.objects.select_for_update()
                .filter(vendeur__isnull=True, statut=CarteFahimta.Statut.ACTIVE)
                .order_by("id")[:quantite]
            )

            if len(cartes_dispo) < quantite:
                return Response(
                    {"detail": f"Stock central insuffisant ({len(cartes_dispo)} disponible(s))."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ids = [carte.id for carte in cartes_dispo]
            CarteFahimta.objects.filter(id__in=ids).update(
                vendeur=vendeur,
                date_assignation=timezone.now(),
                commission_figee=vendeur.commission_fcfa,
            )

        cartes_assignees = CarteFahimta.objects.filter(id__in=ids).select_related("vendeur", "utilisee_par")
        return Response(
            {"quantite": quantite, "cartes": CarteFahimtaAdminSerializer(cartes_assignees, many=True).data}
        )
