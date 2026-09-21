"""
ViewSets admin pour la structure scolaire (Cycle, Niveau, Serie, Matiere).

Point critique : la suppression (destroy) ne s'appuie JAMAIS uniquement sur
on_delete des FK. Chaque ViewSet vérifie explicitement les dépendances
métier et refuse (409) avec un message français si l'élément est utilisé
ailleurs — indépendamment de ce que ferait un DELETE SQL brut.
"""

from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.response import Response

from comptes.permissions import IsAdminRole

from .admin_serializers import (
    CycleReadSerializer,
    CycleWriteSerializer,
    MatiereReadSerializer,
    MatiereWriteSerializer,
    NiveauReadSerializer,
    NiveauWriteSerializer,
    SerieReadSerializer,
    SerieWriteSerializer,
)
from .models import Cycle, Matiere, Niveau, Serie


def formater_compte(n: int, mot: str, suffixe: str = "s") -> str:
    """Ex: formater_compte(3, "programme") -> "3 programme(s)"."""
    return f"{n} {mot}({suffixe})"


class StructureViewSet(viewsets.ModelViewSet):
    """
    Base commune : serializer de lecture/écriture séparé (la réponse de
    create/update reste toujours au format "lecture", riche), et
    suppression protégée via get_dependances().
    """

    permission_classes = [IsAdminRole]
    read_serializer_class: type
    write_serializer_class: type

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return self.write_serializer_class
        return self.read_serializer_class

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        data = self.read_serializer_class(instance, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        data = self.read_serializer_class(instance, context=self.get_serializer_context()).data
        return Response(data)

    def get_dependances(self, instance) -> list[str]:
        """À redéfinir : liste de dépendances déjà formatées ("3 programme(s)"). Vide = suppression permise."""
        return []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        raise NotImplementedError

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        dependances = self.get_dependances(instance)
        if dependances:
            return Response(
                {"detail": self.message_suppression_impossible(instance, dependances)},
                status=status.HTTP_409_CONFLICT,
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CycleViewSet(StructureViewSet):
    read_serializer_class = CycleReadSerializer
    write_serializer_class = CycleWriteSerializer
    queryset = Cycle.objects.annotate(nb_niveaux=Count("niveaux", distinct=True)).order_by("ordre")

    def get_dependances(self, instance: Cycle) -> list[str]:
        nb = instance.niveaux.count()
        return [formater_compte(nb, "niveau", "x")] if nb else []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer ce cycle : il contient {dependances[0]}."


class NiveauViewSet(StructureViewSet):
    read_serializer_class = NiveauReadSerializer
    write_serializer_class = NiveauWriteSerializer
    queryset = (
        Niveau.objects.select_related("cycle")
        .annotate(
            nb_series=Count("series", distinct=True),
            nb_programmes=Count("programmes", distinct=True),
            nb_eleves=Count("eleves", distinct=True),
        )
        .order_by("ordre")
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        cycle_id = self.request.query_params.get("cycle")
        if cycle_id:
            queryset = queryset.filter(cycle_id=cycle_id)
        return queryset

    def get_dependances(self, instance: Niveau) -> list[str]:
        dependances = []
        nb_series = instance.series.count()
        nb_programmes = instance.programmes.count()
        nb_eleves = instance.eleves.count()
        if nb_series:
            dependances.append(formater_compte(nb_series, "série"))
        if nb_programmes:
            dependances.append(formater_compte(nb_programmes, "programme"))
        if nb_eleves:
            dependances.append(formater_compte(nb_eleves, "élève"))
        return dependances

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer ce niveau : {', '.join(dependances)} y sont rattaché(s)."


class SerieViewSet(StructureViewSet):
    read_serializer_class = SerieReadSerializer
    write_serializer_class = SerieWriteSerializer
    queryset = (
        Serie.objects.select_related("niveau")
        .annotate(
            nb_programmes=Count("programmes", distinct=True),
            nb_eleves=Count("eleves", distinct=True),
        )
        .order_by("niveau__ordre", "nom")
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        niveau_id = self.request.query_params.get("niveau")
        if niveau_id:
            queryset = queryset.filter(niveau_id=niveau_id)
        return queryset

    def get_dependances(self, instance: Serie) -> list[str]:
        dependances = []
        nb_programmes = instance.programmes.count()
        nb_eleves = instance.eleves.count()
        if nb_programmes:
            dependances.append(formater_compte(nb_programmes, "programme"))
        if nb_eleves:
            dependances.append(formater_compte(nb_eleves, "élève"))
        return dependances

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer cette série : {', '.join(dependances)} y sont rattaché(s)."


class MatiereViewSet(StructureViewSet):
    read_serializer_class = MatiereReadSerializer
    write_serializer_class = MatiereWriteSerializer
    queryset = Matiere.objects.annotate(nb_programmes=Count("programmes", distinct=True)).order_by("nom")

    def get_dependances(self, instance: Matiere) -> list[str]:
        nb = instance.programmes.count()
        return [formater_compte(nb, "programme")] if nb else []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer cette matière : elle est utilisée par {dependances[0]}."
