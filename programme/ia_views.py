"""Vues admin pour la génération et la vérification IA de sections de leçon.

Réservées à IsAdminRole (JWT). Ne modifient JAMAIS la Lecon en base : elles
renvoient le contenu généré / l'avis, à charge du front (étape 2 — hors
scope ici) de proposer l'aperçu puis l'insertion effective.
"""

import json
import logging
import time

from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.exceptions import NotAcceptable
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsAdminRole

from .ia.exceptions import IAConfigurationInvalide, IAErreur, RefusBudget, SectionInconnue
from .ia.service import generer_section, generer_section_flux, verifier_contenu, verifier_contenu_flux
from .ia_serializers import GenererSectionSerializer, VerifierContenuSerializer
from .models import Notion, PromptSectionNotion

logger = logging.getLogger(__name__)

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
    if isinstance(exc, RefusBudget):  # budget épuisé / interrupteur : code propre (503), pas une panne fournisseur
        return exc.statut_http
    if isinstance(exc, IAConfigurationInvalide):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    return status.HTTP_502_BAD_GATEWAY


class NegociationFlux(DefaultContentNegotiation):
    """Négociation propre à GenererSectionView (les autres endpoints gardent celle de DRF).

    Le front du flux demande `Accept: text/event-stream`, qu'aucun renderer DRF ne couvre : sans cela DRF
    répond 406 avant même d'exécuter la vue. On l'accepte ici et on retient le premier renderer de la vue (JSON) :
    il sert aux refus avant flux (budget, clé...). Le flux lui-même est un StreamingHttpResponse qui ne passe
    jamais par un renderer. Un autre type inconnu reste un 406."""

    def select_renderer(self, request, renderers, format_suffix=None):
        try:
            return super().select_renderer(request, renderers, format_suffix)
        except NotAcceptable:
            if "text/event-stream" in request.META.get("HTTP_ACCEPT", "").lower() and renderers:
                return renderers[0], renderers[0].media_type
            raise


class GenererSectionView(APIView):
    """POST /api/admin/ia/generer/  { notion_id, section }
    -> { contenu } (Markdown) pour les sections texte, { exercices: [...] } pour "exercices"."""

    permission_classes = [IsAdminRole]
    content_negotiation_class = NegociationFlux

    def post(self, request):
        serializer = GenererSectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notion_id = serializer.validated_data["notion_id"]
        section = serializer.validated_data["section"]

        notion, erreur = _recuperer_notion(notion_id)
        if erreur is not None:
            return erreur

        prompt_perso = (
            PromptSectionNotion.objects.filter(notion=notion, section=section)
            .values_list("texte", flat=True)
            .first()
        )

        if serializer.validated_data["stream"]:
            try:
                evenements = generer_section_flux(notion, section, prompt_perso=prompt_perso)
            except SectionInconnue as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except IAErreur as exc:  # refus avant tout flux (clé, budget...) : vraie erreur HTTP, comme sans stream
                return Response({"detail": str(exc)}, status=_statut_pour_erreur(exc))
            return _reponse_sse(evenements)

        try:
            resultat = generer_section(notion, section, prompt_perso=prompt_perso)
        except SectionInconnue as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IAErreur as exc:
            return Response({"detail": str(exc)}, status=_statut_pour_erreur(exc))

        return Response(_corps_generation(resultat))


def _corps_generation(resultat) -> dict:
    """Corps JSON d'une génération réussie (identique en bloc et dans l'événement
    "fin" du flux). Le contenu partiel est renvoyé même tronqué (pour ne rien
    perdre), mais TOUJOURS accompagné de `tronque` — jamais présenté comme
    complet sans ce signal explicite. Voir ResultatGeneration."""
    data: dict = {"tronque": resultat.tronque}
    if resultat.tronque:
        data["message"] = (
            "La génération a été coupée avant la fin (limite de tokens atteinte). "
            "Le contenu est incomplet — régénère, ou complète-le manuellement avant de publier."
        )
    if isinstance(resultat.contenu, list):
        data["exercices"] = resultat.contenu
    else:
        data["contenu"] = resultat.contenu
    return data


def _sse(donnees: dict) -> str:
    return "data: " + json.dumps(donnees, ensure_ascii=False) + "\n\n"


def _reponse_sse(evenements, corps_fin=None) -> StreamingHttpResponse:
    """Flux Server-Sent Events. Évènements JSON, un par message `data:` :
      {"type":"delta","texte":"..."}                fragment de texte
      {"type":"fin", ...corps habituel...}          succès (contenu/exercices, tronque, message)
      {"type":"erreur","detail":"...","status":N}   échec en cours de route (le statut HTTP est déjà 200)
    Des octets partent dès l'ouverture puis régulièrement (commentaires ": ..."
    inclus) : le routeur Heroku ne déclenche donc plus de H12.
    `corps_fin` met en forme la valeur de l'événement final (défaut : corps d'une génération ;
    la vérification passe `lambda avis: {"avis": avis}`)."""
    corps_fin = corps_fin or _corps_generation

    def flux():
        yield ": ouverture\n\n"  # premier octet immédiat (limite Heroku : 30 s)
        dernier = time.monotonic()
        try:
            for type_evenement, valeur in evenements:
                if type_evenement == "delta":
                    if valeur:
                        yield _sse({"type": "delta", "texte": valeur})
                        dernier = time.monotonic()
                    elif time.monotonic() - dernier >= 10:
                        yield ": battement\n\n"
                        dernier = time.monotonic()
                else:
                    yield _sse({"type": "fin", **corps_fin(valeur)})
        except IAErreur as exc:
            yield _sse({"type": "erreur", "detail": str(exc), "status": _statut_pour_erreur(exc)})
        except Exception:  # noqa: BLE001 : le contenu de l'erreur n'est jamais renvoyé tel quel
            logger.exception("Erreur inattendue pendant la génération IA en flux")
            yield _sse({"type": "erreur", "detail": "Erreur inattendue pendant la génération.", "status": 500})
        finally:
            evenements.close()  # client parti ou fin : solde le budget via le générateur sous-jacent

    reponse = StreamingHttpResponse(flux(), content_type="text/event-stream; charset=utf-8")
    reponse["Cache-Control"] = "no-cache"
    reponse["X-Accel-Buffering"] = "no"
    return reponse


class VerifierContenuView(APIView):
    """POST /api/admin/ia/verifier/  { section, contenu, notion_id? } -> { avis }.

    L'avis est un texte IA faillible, JAMAIS une validation — voir le system
    prompt dans programme.ia.service.SYSTEM_VERIFICATION.
    """

    permission_classes = [IsAdminRole]
    content_negotiation_class = NegociationFlux  # accepte `Accept: text/event-stream` (sinon 406 avant la vue)

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

        if serializer.validated_data["stream"]:
            try:
                evenements = verifier_contenu_flux(section, contenu, notion=notion)
            except SectionInconnue as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except IAErreur as exc:  # refus avant tout flux (clé, budget...) : vraie erreur HTTP JSON
                return Response({"detail": str(exc)}, status=_statut_pour_erreur(exc))
            return _reponse_sse(evenements, corps_fin=lambda avis: {"avis": avis})

        try:
            avis = verifier_contenu(section, contenu, notion=notion)
        except SectionInconnue as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IAErreur as exc:
            return Response({"detail": str(exc)}, status=_statut_pour_erreur(exc))

        return Response({"avis": avis})
