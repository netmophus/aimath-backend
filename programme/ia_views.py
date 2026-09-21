"""Vues admin pour la génération et la vérification IA de sections de leçon.

Réservées à IsAdminRole (JWT). Ne modifient JAMAIS la Lecon en base : elles
renvoient le contenu généré / l'avis, à charge du front (étape 2 — hors
scope ici) de proposer l'aperçu puis l'insertion effective.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsAdminRole

from .ia.exceptions import IAConfigurationInvalide, IAErreur, SectionInconnue
from .ia.service import generer_section, verifier_contenu
from .ia_serializers import GenererSectionSerializer, VerifierContenuSerializer
from .models import Notion

_SELECT_RELATED_NOTION = (
    "chapitre__theme__programme__matiere",
    "chapitre__theme__programme__niveau",
    "chapitre__theme__programme__serie",
)


def _recuperer_notion(notion_id: int) -> tuple[Notion | None, Response | None]:
    """Renvoie (notion, None) ou (None, réponse_404) — évite de dupliquer le
    try/except Notion.DoesNotExist dans les deux vues."""
    try:
        return Notion.objects.select_related(*_SELECT_RELATED_NOTION).get(pk=notion_id), None
    except Notion.DoesNotExist:
        return None, Response({"detail": "Notion introuvable."}, status=status.HTTP_404_NOT_FOUND)


def _statut_pour_erreur(exc: IAErreur) -> int:
    """Erreur de réglage serveur (clé absente, fournisseur inconnu, leçon
    modèle manquante) -> 500 : le client n'y peut rien. Toute autre erreur IA
    (quota, timeout, réponse vide ou mal formée) -> 502 : c'est le
    fournisseur en amont qui a fait défaut, pas notre API."""
    if isinstance(exc, IAConfigurationInvalide):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    return status.HTTP_502_BAD_GATEWAY


class GenererSectionView(APIView):
    """POST /api/admin/ia/generer/  { notion_id, section }
    -> { contenu } (Markdown) pour les sections texte, { exercices: [...] } pour "exercices"."""

    permission_classes = [IsAdminRole]

    def post(self, request):
        serializer = GenererSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notion_id = serializer.validated_data["notion_id"]
        section = serializer.validated_data["section"]

        notion, erreur = _recuperer_notion(notion_id)
        if erreur is not None:
            return erreur

        try:
            resultat = generer_section(notion, section)
        except SectionInconnue as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IAErreur as exc:
            return Response({"detail": str(exc)}, status=_statut_pour_erreur(exc))

        if isinstance(resultat, list):
            return Response({"exercices": resultat})
        return Response({"contenu": resultat})


class VerifierContenuView(APIView):
    """POST /api/admin/ia/verifier/  { section, contenu, notion_id? } -> { avis }.

    L'avis est un texte IA faillible, JAMAIS une validation — voir le system
    prompt dans programme.ia.service.SYSTEM_VERIFICATION.
    """

    permission_classes = [IsAdminRole]

    def post(self, request):
        serializer = VerifierContenuSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = serializer.validated_data["section"]
        contenu = serializer.validated_data["contenu"]
        notion_id = serializer.validated_data.get("notion_id")

        notion = None
        if notion_id is not None:
            notion, erreur = _recuperer_notion(notion_id)
            if erreur is not None:
                return erreur

        try:
            avis = verifier_contenu(section, contenu, notion=notion)
        except SectionInconnue as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IAErreur as exc:
            return Response({"detail": str(exc)}, status=_statut_pour_erreur(exc))

        return Response({"avis": avis})
