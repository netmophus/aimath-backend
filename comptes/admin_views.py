from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from programme.models import Lecon

from .admin_serializers import (
    AdminCompteSerializer,
    CreerCompteSerializer,
    ModifierCompteSerializer,
    RejeterCompteSerializer,
)
from .models import User
from .mot_de_passe import generer_mot_de_passe
from .permissions import IsAdminRole
from .sms import envoyer_sms


class AdminCompteViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """
    Gestion des comptes utilisateurs pour le dashboard admin.

    GET  /api/admin/comptes/                → liste paginée, filtrable
    GET  /api/admin/comptes/{id}/           → détail d'un compte
    POST /api/admin/comptes/                → créer un compte enseignant/admin
    PATCH/PUT /api/admin/comptes/{id}/      → modifier prenom/nom/email
    POST /api/admin/comptes/{id}/approuver/ → en_attente → actif
    POST /api/admin/comptes/{id}/rejeter/   → en_attente → rejete
    POST /api/admin/comptes/{id}/suspendre/ → actif → suspendu
    POST /api/admin/comptes/{id}/reactiver/ → suspendu/rejete → actif

    Filtres de la liste (query params) : ?statut=, ?role=, ?search=
    (nom, prénom, téléphone). Pas d'endpoint /en-attente/ dédié : le même
    résultat s'obtient avec ?statut=en_attente (voir résumé de livraison).
    """

    permission_classes = [IsAdminRole]
    serializer_class = AdminCompteSerializer
    queryset = User.objects.select_related("niveau", "serie").order_by("-date_inscription")

    def get_serializer_class(self):
        if self.action == "create":
            return CreerCompteSerializer
        if self.action in ("update", "partial_update"):
            return ModifierCompteSerializer
        return AdminCompteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte = serializer.save()
        return Response(AdminCompteSerializer(compte).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        compte = serializer.save()
        return Response(AdminCompteSerializer(compte).data)

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        statut = params.get("statut")
        if statut:
            queryset = queryset.filter(statut=statut)

        role = params.get("role")
        if role:
            queryset = queryset.filter(role=role)

        search = params.get("search")
        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search)
                | Q(prenom__icontains=search)
                | Q(telephone__icontains=search)
            )

        return queryset

    @action(detail=True, methods=["post"], url_path="reinitialiser-mot-de-passe")
    def reinitialiser_mot_de_passe(self, request, pk=None):
        """
        Génère un mot de passe aléatoire, l'applique, force son changement à
        la prochaine connexion et l'envoie PAR SMS uniquement — il n'apparaît
        jamais dans la réponse. Le SMS ne bloque jamais l'action (envoyer_sms
        ne lève pas) : `sms_envoye` indique si LAM l'a accepté ; sinon l'admin
        peut simplement relancer la réinitialisation.
        """
        compte = self.get_object()

        if compte.pk == request.user.pk:
            return Response(
                {"detail": "Tu ne peux pas réinitialiser ton propre mot de passe depuis ici."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        nouveau = generer_mot_de_passe()
        compte.set_password(nouveau)
        compte.doit_changer_mdp = True
        compte.save(update_fields=["password", "doit_changer_mdp"])

        sms_envoye = envoyer_sms(
            compte.telephone,
            "FAHIMTA : votre mot de passe a ete reinitialise. "
            f"Nouveau mot de passe : {nouveau}. "
            "Vous devrez le changer a la prochaine connexion.",
        )

        return Response({"detail": "Mot de passe réinitialisé.", "sms_envoye": sms_envoye})

    @action(detail=True, methods=["post"])
    def approuver(self, request, pk=None):
        """Passe le compte en_attente → actif. Idempotence : refusé (400) si le compte n'est pas en_attente."""
        compte = self.get_object()

        if compte.statut != User.Statut.EN_ATTENTE:
            return Response(
                {"detail": "Ce compte n'est pas en attente de validation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        compte.statut = User.Statut.ACTIF
        compte.motif_rejet = None
        compte.save(update_fields=["statut", "motif_rejet"])

        return Response(AdminCompteSerializer(compte).data)

    @action(detail=True, methods=["post"])
    def rejeter(self, request, pk=None):
        """Passe le compte en_attente → rejete, avec motif optionnel."""
        compte = self.get_object()

        if compte.statut != User.Statut.EN_ATTENTE:
            return Response(
                {"detail": "Ce compte n'est pas en attente de validation."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        body = RejeterCompteSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        compte.statut = User.Statut.REJETE
        compte.motif_rejet = body.validated_data.get("motif", "")
        compte.save(update_fields=["statut", "motif_rejet"])

        return Response(AdminCompteSerializer(compte).data)

    @action(detail=True, methods=["post"])
    def suspendre(self, request, pk=None):
        """Passe le compte actif → suspendu."""
        compte = self.get_object()

        if compte.statut != User.Statut.ACTIF:
            return Response(
                {"detail": "Seul un compte actif peut être suspendu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        compte.statut = User.Statut.SUSPENDU
        compte.save(update_fields=["statut"])

        return Response(AdminCompteSerializer(compte).data)

    @action(detail=True, methods=["post"])
    def reactiver(self, request, pk=None):
        """Passe le compte suspendu ou rejeté → actif."""
        compte = self.get_object()

        if compte.statut not in (User.Statut.SUSPENDU, User.Statut.REJETE):
            return Response(
                {"detail": "Seul un compte suspendu ou rejeté peut être réactivé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        compte.statut = User.Statut.ACTIF
        compte.motif_rejet = None
        compte.save(update_fields=["statut", "motif_rejet"])

        return Response(AdminCompteSerializer(compte).data)


class AdminStatsView(APIView):
    """GET /api/admin/stats/ — compteurs simples pour la vue d'ensemble du dashboard."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(
            {
                "nb_eleves": User.objects.filter(role=User.Role.ELEVE).count(),
                "nb_enseignants": User.objects.filter(role=User.Role.ENSEIGNANT).count(),
                "nb_en_attente": User.objects.filter(statut=User.Statut.EN_ATTENTE).count(),
                "total_lecons": Lecon.objects.count(),
                "lecons_publiees": Lecon.objects.filter(statut=Lecon.Statut.PUBLIE).count(),
            }
        )
