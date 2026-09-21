"""
ViewSet admin pour le glossaire (TermeGlossaire).

GET    /api/admin/glossaire/          → liste paginée, ?search= sur le terme
POST   /api/admin/glossaire/          → créer
GET    /api/admin/glossaire/{id}/     → détail
PUT/PATCH /api/admin/glossaire/{id}/  → modifier
DELETE /api/admin/glossaire/{id}/     → supprimer (libre : un [[slug]] orphelin
                                         dans un cours est géré côté front,
                                         pas une raison d'interdire la suppression)
"""

from rest_framework import status, viewsets
from rest_framework.response import Response

from comptes.permissions import IsAdminRole

from .glossaire_serializers import TermeGlossaireEcritureSerializer, TermeGlossaireSerializer
from .models import TermeGlossaire


class TermeGlossaireViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminRole]
    queryset = TermeGlossaire.objects.select_related("lecon_liee").all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TermeGlossaireEcritureSerializer
        return TermeGlossaireSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(terme__icontains=search)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        terme = serializer.save()
        data = TermeGlossaireSerializer(terme, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        terme = serializer.save()
        data = TermeGlossaireSerializer(terme, context=self.get_serializer_context()).data
        return Response(data)
