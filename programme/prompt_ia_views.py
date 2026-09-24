"""CRUD des prompts personnalisés par section, pour une Notion donnée.

Volontairement séparé de programme.lecon_views / lecon_serializers : un
prompt personnalisé est rattaché à la NOTION (comme la génération elle-même,
voir programme.ia_views._recuperer_notion), pas à la Leçon — ce fichier ne
touche donc jamais au flux de sauvegarde de la leçon.
"""

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsAdminRole

from .models import Notion, PromptSectionNotion
from .prompt_ia_serializers import SECTIONS_CLES, PromptsNotionSerializer


class PromptsNotionView(APIView):
    """GET/PUT /api/admin/ia/prompts/{notion_id}/

    { histoire, objectifs, prerequis, cours, demonstrations, a_retenir,
    exercices } — texte du prompt personnalisé de chaque section, ou ""
    si aucun (= génération par défaut pour cette section).

    PUT reçoit le même objet : pour chaque section, texte non vide = upsert,
    texte vide = suppression de la ligne existante (retour au défaut).
    """

    permission_classes = [IsAdminRole]

    def _recuperer_notion(self, notion_id: int) -> tuple[Notion | None, Response | None]:
        try:
            return Notion.objects.get(pk=notion_id), None
        except Notion.DoesNotExist:
            return None, Response({"detail": "Notion introuvable."}, status=status.HTTP_404_NOT_FOUND)

    def _serialiser(self, notion: Notion) -> dict:
        existants = {
            p.section: p.texte for p in PromptSectionNotion.objects.filter(notion=notion)
        }
        return {cle: existants.get(cle, "") for cle in SECTIONS_CLES}

    def get(self, request, notion_id: int):
        notion, erreur = self._recuperer_notion(notion_id)
        if erreur is not None:
            return erreur
        return Response(self._serialiser(notion))

    def put(self, request, notion_id: int):
        notion, erreur = self._recuperer_notion(notion_id)
        if erreur is not None:
            return erreur

        serializer = PromptsNotionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            existants = {
                p.section: p
                for p in PromptSectionNotion.objects.select_for_update().filter(notion=notion)
            }
            for section, texte in serializer.validated_data.items():
                texte = texte.strip()
                existant = existants.get(section)

                if texte:
                    if existant is None:
                        PromptSectionNotion.objects.create(notion=notion, section=section, texte=texte)
                    elif existant.texte != texte:
                        existant.texte = texte
                        existant.save(update_fields=["texte", "modifie_le"])
                elif existant is not None:
                    existant.delete()

        return Response(self._serialiser(notion))
