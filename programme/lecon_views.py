"""
ViewSet admin pour la Lecon (le contenu produit), avec ses exercices/vidéos/
ressources gérés en imbriqué (voir lecon_serializers.py pour la convention
de synchronisation en écriture).

GET    /api/admin/lecons/               → liste paginée, filtrable
POST   /api/admin/lecons/               → créer (avec exercices/vidéos/ressources imbriqués)
GET    /api/admin/lecons/{id}/          → détail complet
PUT/PATCH /api/admin/lecons/{id}/       → modifier (idem, synchronise l'imbriqué)
DELETE /api/admin/lecons/{id}/          → supprimer (cascade — libère la notion)
POST   /api/admin/lecons/{id}/publier/  → statut → publié
POST   /api/admin/lecons/{id}/depublier/→ statut → brouillon

Filtres de la liste : ?statut=, ?notion=, ?chapitre=, ?programme=, ?search=
"""

from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from comptes.permissions import IsAdminRole

from .lecon_serializers import LeconDetailSerializer, LeconEcritureSerializer, LeconListeSerializer
from .models import Lecon


class LeconViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminRole]
    queryset = (
        Lecon.objects.select_related(
            "notion",
            "notion__chapitre",
            "notion__chapitre__theme",
            "notion__chapitre__theme__programme",
            "notion__chapitre__theme__programme__matiere",
            "notion__chapitre__theme__programme__niveau",
            "notion__chapitre__theme__programme__serie",
        )
        .annotate(
            nb_exercices=Count("exercices", distinct=True),
            nb_videos=Count("videos", distinct=True),
        )
        .order_by("-modifie_le")
    )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LeconEcritureSerializer
        if self.action == "retrieve":
            return LeconDetailSerializer
        return LeconListeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        statut = params.get("statut")
        if statut:
            queryset = queryset.filter(statut=statut)

        notion_id = params.get("notion")
        if notion_id:
            queryset = queryset.filter(notion_id=notion_id)

        chapitre_id = params.get("chapitre")
        if chapitre_id:
            queryset = queryset.filter(notion__chapitre_id=chapitre_id)

        programme_id = params.get("programme")
        if programme_id:
            queryset = queryset.filter(notion__chapitre__theme__programme_id=programme_id)

        search = params.get("search")
        if search:
            queryset = queryset.filter(titre__icontains=search)

        if self.action == "retrieve":
            queryset = queryset.prefetch_related("exercices", "videos", "ressources", "prerequis_lecons")

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lecon = serializer.save()
        data = LeconDetailSerializer(lecon, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        lecon = serializer.save()
        data = LeconDetailSerializer(lecon, context=self.get_serializer_context()).data
        return Response(data)

    def _reponse_statut(self, lecon: Lecon) -> Response:
        data = LeconDetailSerializer(lecon, context=self.get_serializer_context()).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def publier(self, request, pk=None):
        lecon = self.get_object()
        lecon.statut = Lecon.Statut.PUBLIE
        lecon.save(update_fields=["statut", "modifie_le"])
        return self._reponse_statut(lecon)

    @action(detail=True, methods=["post"])
    def depublier(self, request, pk=None):
        lecon = self.get_object()
        lecon.statut = Lecon.Statut.BROUILLON
        lecon.save(update_fields=["statut", "modifie_le"])
        return self._reponse_statut(lecon)
