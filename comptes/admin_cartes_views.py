"""
Endpoints admin pour les cartes Fahimta (back-office custom) — réservés
IsAdminRole, cohérent avec AdminCompteViewSet/AdminStatsView. AUCUNE logique
de génération/masquage/export n'est réécrite ici : tout vient de
comptes/cartes.py, déjà utilisée par la commande `generer_cartes` et l'admin
Django (voir comptes/admin.py).

GET  /api/admin/cartes/           → liste paginée, filtrable (dont ?vendeur=<id>), recherche par code
POST /api/admin/cartes/generer/   → génère un nouveau lot (codes EN CLAIR en réponse)
GET  /api/admin/cartes/lots/      → vue synthétique par lot
GET  /api/admin/cartes/export/    → export CSV (?lot=... pour restreindre, sinon tout)

Le module vendeur (comptes/admin_vendeurs_views.py) RÉUTILISE ce endpoint via
?vendeur=<id> pour la liste des cartes d'un vendeur, plutôt que d'exposer un
endpoint dédié — la page de détail vendeur du back-office appelle donc la
MÊME fonction lib/carteApi.ts::listerCartes que la page /admin/cartes.
"""

from django.db.models import Count, Max, Min, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .admin_cartes_serializers import (
    CarteFahimtaAdminSerializer,
    CarteFahimtaGenereeSerializer,
    GenererLotSerializer,
)
from .cartes import ETAT_ASSIGNEE, ETAT_STOCK_CENTRAL, ETAT_UTILISEE, ETAT_VENDUE, filtre_etat, generer_lot, reponse_csv_cartes
from .models import CarteFahimta
from .permissions import IsAdminRole


class CarteFahimtaAdminViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = CarteFahimtaAdminSerializer
    queryset = (
        CarteFahimta.objects.select_related("utilisee_par", "vendeur", "attribuee_a")
        .order_by("-date_creation")
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        statut = params.get("statut")
        if statut:
            queryset = queryset.filter(statut=statut)

        # État de suivi admin (voir comptes.cartes.filtre_etat, vocabulaire
        # stock_central/assignee/vendue/utilisee) — plus précis que `statut`
        # ci-dessus (qui ne distingue pas stock central/assignée/vendue,
        # toutes trois "active") : les deux filtres coexistent, `statut`
        # reste utilisé tel quel par les autres appelants existants
        # (ex. AssignerCartesModal.tsx, ?statut=active&vendeur=none).
        etat = params.get("etat")
        if etat:
            queryset = queryset.filter(filtre_etat(etat))

        lot = params.get("lot")
        if lot:
            queryset = queryset.filter(lot=lot)

        duree_jours = params.get("duree_jours")
        if duree_jours:
            queryset = queryset.filter(duree_jours=duree_jours)

        # Cartes d'UN vendeur (voir la page de détail vendeur du
        # back-office, qui réutilise CET endpoint plutôt qu'un endpoint
        # dédié) — ?vendeur=<id>. ?vendeur=none => stock central (non
        # assigné) — utilisé par la page vendeur pour afficher le stock
        # disponible avant d'assigner (juste le `count` de la réponse
        # paginée, ?page_size réel importe peu ici). Volontairement pas de
        # recherche libre par nom de vendeur, comme pour `lot` : le front
        # connaît déjà l'id.
        vendeur_id = params.get("vendeur")
        if vendeur_id == "none":
            queryset = queryset.filter(vendeur__isnull=True)
        elif vendeur_id:
            queryset = queryset.filter(vendeur_id=vendeur_id)

        # Traçabilité PAR ÉLÈVE (voir la consigne "vue par élève") — toutes
        # les cartes qui LE concernent, qu'elles lui aient été vendues
        # (attribuee_a) et/ou qu'il les ait lui-même activées (utilisee_par) :
        # les deux peuvent différer d'une carte à l'autre (une carte achetée
        # directement, sans passer par un vendeur, n'a pas d'attribuee_a mais
        # a un utilisee_par une fois activée).
        eleve_id = params.get("eleve")
        if eleve_id:
            queryset = queryset.filter(Q(attribuee_a_id=eleve_id) | Q(utilisee_par_id=eleve_id))

        # Recherche brute sur le champ `code` : un admin colle en général le
        # code EXACT (vu sur une carte imprimée ou dans un export), pas un
        # fragment — icontains reste tolérant à la casse/aux tirets partiels
        # sans avoir besoin de ré-implémenter normaliser_code ici.
        search = params.get("search")
        if search:
            queryset = queryset.filter(code__icontains=search.strip())

        return queryset

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """GET /api/admin/cartes/stats/ — compteurs GLOBAUX par état (voir
        comptes.cartes, vocabulaire stock_central/assignee/vendue/utilisee),
        pour l'en-tête de la page /admin/cartes. Toujours sur l'ensemble des
        cartes (pas filtré par les autres query params de la liste) : c'est
        une vue d'ensemble, pas un total de la page courante."""
        agregats = CarteFahimta.objects.aggregate(
            total=Count("id"),
            stock_central=Count("id", filter=filtre_etat(ETAT_STOCK_CENTRAL)),
            assignee=Count("id", filter=filtre_etat(ETAT_ASSIGNEE)),
            vendue=Count("id", filter=filtre_etat(ETAT_VENDUE)),
            utilisee=Count("id", filter=filtre_etat(ETAT_UTILISEE)),
        )
        return Response(agregats)

    @action(detail=False, methods=["post"])
    def generer(self, request):
        """Codes renvoyés EN CLAIR (CarteFahimtaGenereeSerializer, pas le
        serializer de liste) : c'est le seul moment où le back-office
        affiche les codes non masqués en masse, pour impression/export
        immédiat — voir GenererLotSerializer pour pourquoi `lot` n'est pas
        exposé dans le formulaire frontend."""
        serializer = GenererLotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cartes = generer_lot(
            quantite=serializer.validated_data["quantite"],
            duree_jours=serializer.validated_data["duree_jours"],
            lot=serializer.validated_data.get("lot") or None,
        )

        return Response(
            {
                "lot": cartes[0].lot,
                "duree_jours": cartes[0].duree_jours,
                "cartes": CarteFahimtaGenereeSerializer(cartes, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def lots(self, request):
        """Regroupement par lot — total/actives/utilisées, pour une vue
        synthétique. `duree_jours` via Max() : toutes les cartes d'un même
        lot partagent en pratique la même durée (générées ensemble par
        generer_lot), Max() est juste la façon la plus simple d'en tirer
        UNE valeur depuis l'agrégation sans supposer d'ordre."""
        agregats = (
            CarteFahimta.objects.values("lot")
            .annotate(
                total=Count("id"),
                actives=Count("id", filter=Q(statut=CarteFahimta.Statut.ACTIVE)),
                utilisees=Count("id", filter=Q(statut=CarteFahimta.Statut.UTILISEE)),
                duree_jours=Max("duree_jours"),
                date_creation=Min("date_creation"),
            )
            .order_by("-date_creation")
        )
        return Response(list(agregats))

    @action(detail=False, methods=["get"])
    def export(self, request):
        """CSV — codes TOUJOURS en clair (voir comptes.cartes.lignes_csv_cartes) :
        c'est le moyen prévu de sortir des codes en masse pour impression/
        distribution, au même titre que la réponse de `generer`. Respecte
        les mêmes filtres que la liste (ex. ?lot=xxx pour restreindre à un
        seul lot, comme demandé pour l'impression d'un lot précis)."""
        queryset = self.get_queryset().order_by("code")
        lot = request.query_params.get("lot")
        nom_fichier = f"cartes_fahimta_{lot}.csv" if lot else "cartes_fahimta.csv"
        return reponse_csv_cartes(queryset, nom_fichier=nom_fichier)
