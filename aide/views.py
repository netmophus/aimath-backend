from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsAdminRole, IsEleveActif

from .models import DemandeAide
from .serializers import CreerDemandeSerializer, DemandeAdminSerializer, DemandeSerializer, TraiterDemandeSerializer

MAX_PAR_JOUR = 10
MAX_PAR_MINUTE = 3
LISTE_MAX = 100
_RELATIONS = ("programme__matiere", "lecon")


def _piece_jointe(demande: DemandeAide) -> HttpResponse:
    if not demande.a_piece_jointe or demande.piece_jointe is None:
        raise Http404
    rep = HttpResponse(bytes(demande.piece_jointe), content_type=demande.piece_jointe_type)
    rep["X-Content-Type-Options"] = "nosniff"
    rep["Cache-Control"] = "private, no-store"
    rep["Content-Disposition"] = 'inline; filename="piece-jointe"'
    return rep


class DemandesEleveView(APIView):
    """GET : MES demandes (jamais celles d'un autre). POST : crée une demande (idempotent grâce à `cle`)."""

    permission_classes = [IsEleveActif]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        qs = (DemandeAide.objects.filter(eleve=request.user).select_related(*_RELATIONS)
              .defer("piece_jointe")[:LISTE_MAX])
        return Response(DemandeSerializer(qs, many=True).data)

    def post(self, request):
        ser = CreerDemandeSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        existante = (DemandeAide.objects.filter(eleve=request.user, cle=d["cle"])
                     .select_related(*_RELATIONS).defer("piece_jointe").first())
        if existante:   # double envoi : la même demande, rien n'est recréé
            return Response(DemandeSerializer(existante).data, status=status.HTTP_200_OK)

        maintenant = timezone.now()
        recentes = DemandeAide.objects.filter(eleve=request.user)
        if (recentes.filter(cree_le__gte=maintenant - timedelta(minutes=1)).count() >= MAX_PAR_MINUTE
                or recentes.filter(cree_le__gte=maintenant - timedelta(days=1)).count() >= MAX_PAR_JOUR):
            return Response({"detail": "Trop de demandes. Réessaie plus tard."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            with transaction.atomic():
                demande = DemandeAide.objects.create(
                    eleve=request.user, cle=d["cle"], type=d["type"], programme=d["programme_obj"], lecon=d["lecon_obj"],
                    message=d["message"],
                    piece_jointe=d.get("octets"), piece_jointe_type=d.get("type_fichier", ""),
                    piece_jointe_taille=len(d["octets"]) if d.get("octets") else 0,
                )
        except IntegrityError:   # deux envois simultanés avec la même clé
            demande = DemandeAide.objects.get(eleve=request.user, cle=d["cle"])
            return Response(DemandeSerializer(demande).data, status=status.HTTP_200_OK)
        return Response(DemandeSerializer(demande).data, status=status.HTTP_201_CREATED)


class DemandeEleveDetailView(RetrieveAPIView):
    """Le queryset est limité à l'élève connecté : l'id d'un autre élève donne un 404 générique."""

    permission_classes = [IsEleveActif]
    serializer_class = DemandeSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return DemandeAide.objects.filter(eleve=self.request.user).select_related(*_RELATIONS).defer("piece_jointe")


class PieceJointeEleveView(APIView):
    permission_classes = [IsEleveActif]

    def get(self, request, id):
        try:
            demande = DemandeAide.objects.get(pk=id, eleve=request.user)
        except DemandeAide.DoesNotExist:
            raise Http404
        return _piece_jointe(demande)


# --- Administration (rôle admin) ---

class DemandesAdminListeView(ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = DemandeAdminSerializer

    def get_queryset(self):
        qs = DemandeAide.objects.select_related("eleve", "eleve__niveau", "eleve__serie", *_RELATIONS).defer("piece_jointe")
        p = self.request.query_params
        if p.get("type") in DemandeAide.Type.values:
            qs = qs.filter(type=p["type"])
        if p.get("statut") in DemandeAide.Statut.values:
            qs = qs.filter(statut=p["statut"])
        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(message__icontains=q) | Q(reponse__icontains=q) | Q(eleve__nom__icontains=q)
                           | Q(eleve__prenom__icontains=q) | Q(eleve__telephone__icontains=q)
                           | Q(lecon__titre__icontains=q) | Q(programme__matiere__nom__icontains=q))
        return qs


class DemandeAdminDetailView(APIView):
    permission_classes = [IsAdminRole]

    def _obtenir(self, id):
        try:
            return (DemandeAide.objects.select_related("eleve", "eleve__niveau", "eleve__serie", *_RELATIONS)
                    .defer("piece_jointe").get(pk=id))
        except DemandeAide.DoesNotExist:
            raise Http404

    def get(self, request, id):
        return Response(DemandeAdminSerializer(self._obtenir(id)).data)

    def patch(self, request, id):
        demande = self._obtenir(id)
        ser = TraiterDemandeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        maintenant = timezone.now()
        champs = ["mis_a_jour_le"]
        if "reponse" in d:
            nouvelle = d["reponse"].strip()
            if nouvelle != demande.reponse.strip():
                demande.reponse = nouvelle
                demande.reponse_par = request.user if nouvelle else None
                demande.reponse_le = maintenant if nouvelle else None
                champs += ["reponse", "reponse_par", "reponse_le"]
                if nouvelle and "statut" not in d and demande.statut == DemandeAide.Statut.RECUE:
                    demande.statut = DemandeAide.Statut.EN_COURS
        if "statut" in d:
            demande.statut = d["statut"]
        if demande.statut == DemandeAide.Statut.TRAITEE:
            demande.traitee_le = demande.traitee_le or maintenant
        else:
            demande.traitee_le = None
        champs += ["statut", "traitee_le"]
        demande.save(update_fields=champs)
        return Response(DemandeAdminSerializer(demande).data)


class PieceJointeAdminView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, id):
        try:
            demande = DemandeAide.objects.get(pk=id)
        except DemandeAide.DoesNotExist:
            raise Http404
        return _piece_jointe(demande)
