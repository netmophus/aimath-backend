from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsEleveActif

from .models import TacheIA
from .service import etat_public, reprise, taches_de


class TacheDetailView(APIView):
    """GET /api/eleve/taches/<id>/ : état d'une tâche de L'ÉLÈVE CONNECTÉ ; 404 pour toute autre (aucune fuite)."""

    permission_classes = [IsEleveActif]

    def get(self, request, id):
        tache = TacheIA.objects.filter(pk=id, utilisateur=request.user).first()
        if tache is None:
            raise Http404
        return Response(etat_public(tache))


class TacheListeView(APIView):
    """GET /api/eleve/taches/ : tâches récentes de l'élève connecté (actives, ou terminées depuis moins de
    IA_TACHE_RESULTAT_SECONDES = 2 h). Aucune tâche d'un autre utilisateur, jamais."""

    permission_classes = [IsEleveActif]

    def get(self, request):
        return Response({"taches": taches_de(request.user)})


class RepriseView(APIView):
    """GET /api/eleve/reprise/?programme=<id> : de quoi reprendre après actualisation (analyse, lecture, correction, séance
    fahimta ai) pour UN programme de la classe de l'élève. Lecture seule : aucun appel IA, aucune facturation."""

    permission_classes = [IsEleveActif]

    def get(self, request):
        from programme.eleve_views import _programmes_de_la_classe

        try:
            identifiant = int(request.query_params.get("programme"))
        except (TypeError, ValueError):
            raise Http404
        if not _programmes_de_la_classe(request.user).filter(pk=identifiant).exists():
            raise Http404
        return Response(reprise(request.user, identifiant))
