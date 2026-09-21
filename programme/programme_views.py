"""
ViewSets admin pour la hiérarchie du programme officiel :
Programme → Theme → Chapitre → Notion. Montés sous /api/admin/ (distinct de
/api/admin/structure/, réservé à Cycle/Niveau/Serie/Matiere) — voir
programme_urls.py.

Garde-fou de suppression commun : Theme/Chapitre/Notion (et Programme, par
cohérence avec le même principe) refusent la suppression si des LEÇONS
existent en dessous. La cascade du modèle reste correcte pour des
thèmes/chapitres/notions VIDES ; on ne veut juste jamais effacer du contenu
rédigé par mégarde.
"""

from django.db.models import Count, Exists, OuterRef
from rest_framework.decorators import action
from rest_framework.response import Response

from .admin_views import StructureViewSet, formater_compte
from .models import Chapitre, Lecon, Notion, Programme, Theme
from .programme_serializers import (
    ChapitreReadSerializer,
    ChapitreWriteSerializer,
    NotionReadSerializer,
    NotionWriteSerializer,
    ProgrammeDetailSerializer,
    ProgrammeReadSerializer,
    ProgrammeWriteSerializer,
    ThemeReadSerializer,
    ThemeWriteSerializer,
)


class ReordonnableMixin:
    """
    Actions monter/descendre : échangent le champ `ordre` avec le voisin
    adjacent (même parent, désigné par `champ_parent`). Sur une borne (déjà
    premier/dernier), ne fait rien et renvoie 200 avec l'élément inchangé —
    idempotent plutôt qu'une erreur ; plus simple à consommer côté front
    (bouton "monter" désactivé ou pas, le clic reste sans danger).
    """

    champ_parent: str

    def _freres(self, instance) -> list:
        parent_id = getattr(instance, f"{self.champ_parent}_id")
        return list(
            self.get_queryset().filter(**{self.champ_parent: parent_id}).order_by("ordre")
        )

    def _reponse(self, instance) -> Response:
        data = self.read_serializer_class(instance, context=self.get_serializer_context()).data
        return Response(data)

    def _deplacer(self, decalage: int) -> Response:
        instance = self.get_object()
        freres = self._freres(instance)
        position = next(i for i, f in enumerate(freres) if f.pk == instance.pk)
        nouvelle_position = position + decalage

        if nouvelle_position < 0 or nouvelle_position >= len(freres):
            return self._reponse(instance)

        voisin = freres[nouvelle_position]
        instance.ordre, voisin.ordre = voisin.ordre, instance.ordre
        type(instance).objects.bulk_update([instance, voisin], ["ordre"])
        return self._reponse(instance)

    @action(detail=True, methods=["post"])
    def monter(self, request, pk=None):
        return self._deplacer(-1)

    @action(detail=True, methods=["post"])
    def descendre(self, request, pk=None):
        return self._deplacer(1)


class ProgrammeViewSet(StructureViewSet):
    """
    GET  /api/admin/programmes/       → liste avec compteurs
    GET  /api/admin/programmes/{id}/  → arbre imbriqué complet
    POST/PUT/PATCH/DELETE             → CRUD standard
    """

    read_serializer_class = ProgrammeReadSerializer
    write_serializer_class = ProgrammeWriteSerializer
    queryset = (
        Programme.objects.select_related("matiere", "niveau", "serie")
        .annotate(
            nb_themes=Count("themes", distinct=True),
            nb_chapitres=Count("themes__chapitres", distinct=True),
            nb_notions=Count("themes__chapitres__notions", distinct=True),
            nb_lecons=Count("themes__chapitres__notions__lecon", distinct=True),
        )
        .order_by("matiere__nom", "niveau__ordre")
    )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProgrammeDetailSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("themes__chapitres__notions__lecon")
        return queryset

    def get_dependances(self, instance: Programme) -> list[str]:
        nb = Lecon.objects.filter(notion__chapitre__theme__programme=instance).count()
        return [formater_compte(nb, "leçon")] if nb else []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer : {dependances[0]} rattachée(s). Supprimez-les d'abord."


class ThemeViewSet(ReordonnableMixin, StructureViewSet):
    champ_parent = "programme"
    read_serializer_class = ThemeReadSerializer
    write_serializer_class = ThemeWriteSerializer
    queryset = Theme.objects.annotate(
        nb_chapitres=Count("chapitres", distinct=True),
        nb_notions=Count("chapitres__notions", distinct=True),
    ).order_by("programme", "ordre")

    def get_queryset(self):
        queryset = super().get_queryset()
        programme_id = self.request.query_params.get("programme")
        if programme_id:
            queryset = queryset.filter(programme_id=programme_id)
        return queryset

    def get_dependances(self, instance: Theme) -> list[str]:
        nb = Lecon.objects.filter(notion__chapitre__theme=instance).count()
        return [formater_compte(nb, "leçon")] if nb else []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer : {dependances[0]} rattachée(s). Supprimez-les d'abord."


class ChapitreViewSet(ReordonnableMixin, StructureViewSet):
    champ_parent = "theme"
    read_serializer_class = ChapitreReadSerializer
    write_serializer_class = ChapitreWriteSerializer
    queryset = Chapitre.objects.annotate(
        nb_notions=Count("notions", distinct=True),
    ).order_by("theme", "ordre")

    def get_queryset(self):
        queryset = super().get_queryset()
        theme_id = self.request.query_params.get("theme")
        if theme_id:
            queryset = queryset.filter(theme_id=theme_id)
        return queryset

    def get_dependances(self, instance: Chapitre) -> list[str]:
        nb = Lecon.objects.filter(notion__chapitre=instance).count()
        return [formater_compte(nb, "leçon")] if nb else []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return f"Impossible de supprimer : {dependances[0]} rattachée(s). Supprimez-les d'abord."


class NotionViewSet(ReordonnableMixin, StructureViewSet):
    champ_parent = "chapitre"
    read_serializer_class = NotionReadSerializer
    write_serializer_class = NotionWriteSerializer
    queryset = Notion.objects.annotate(
        a_lecon=Exists(Lecon.objects.filter(notion=OuterRef("pk"))),
    ).order_by("chapitre", "ordre")

    def get_queryset(self):
        queryset = super().get_queryset()
        chapitre_id = self.request.query_params.get("chapitre")
        if chapitre_id:
            queryset = queryset.filter(chapitre_id=chapitre_id)
        return queryset

    def get_dependances(self, instance: Notion) -> list[str]:
        a_lecon = getattr(instance, "a_lecon", None)
        if a_lecon is None:
            a_lecon = Lecon.objects.filter(notion=instance).exists()
        return ["leçon"] if a_lecon else []

    def message_suppression_impossible(self, instance, dependances: list[str]) -> str:
        return "Cette notion a une leçon. Supprimez la leçon d'abord."
