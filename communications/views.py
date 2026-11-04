from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsAdminRole, IsEleveActif

from . import services
from .models import Campagne, MessageSms, ParametresCommunication, PreferenceCommunication
from .serializers import (ApercuSerializer, DecisionParentaleSerializer, ParametresSerializer, PreferenceEleveSerializer,
                          PreferenceSerializer, campagne_dict, message_dict, parametres_dict)

User = get_user_model()


class AdminActif(IsAdminRole):
    """Administrateur au statut actif : un administrateur suspendu ou en attente ne peut ni régler ni envoyer, même avec un jeton encore valide.
    (IsAdminRole, partagé avec tout le reste de l'application, n'est pas modifié.)"""

    def has_permission(self, request, view) -> bool:
        return super().has_permission(request, view) and request.user.statut == User.Statut.ACTIF


def _erreur(e: services.ErreurMetier):
    return Response({"detail": e.message, "code": e.code}, status=e.statut_http)


class ParametresView(APIView):
    permission_classes = [AdminActif]

    def get(self, request):
        return Response(parametres_dict())

    def patch(self, request):
        ser = ParametresSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        p = ParametresCommunication.charger()
        try:
            if "lien_whatsapp" in d:
                p.lien_whatsapp = services.valider_lien_whatsapp(d["lien_whatsapp"])
        except services.ErreurMetier as e:
            return _erreur(e)
        if "plafond_mensuel_fcfa" in d:
            p.plafond_mensuel_fcfa = d["plafond_mensuel_fcfa"]
        if "cout_segment_fcfa" in d:
            p.cout_segment_fcfa = d["cout_segment_fcfa"]
        p.mis_a_jour_par = request.user
        p.save()
        return Response(parametres_dict())


class ModelesView(APIView):
    permission_classes = [AdminActif]

    def get(self, request):
        return Response(services.MODELES)


class ApercuView(APIView):
    """Prépare une campagne et renvoie l'aperçu. N'ENVOIE RIEN."""
    permission_classes = [AdminActif]

    def post(self, request):
        ser = ApercuSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            camp, creee = services.preparer(request.user, d["cle"], d["type"], d["texte"], d["mode"], d["ids"],
                                            d["filtres"])
        except services.ErreurMetier as e:
            return _erreur(e)
        return Response(campagne_dict(camp, avec_apercu=True),
                        status=status.HTTP_201_CREATED if creee else status.HTTP_200_OK)


class ConfirmerView(APIView):
    permission_classes = [AdminActif]

    def post(self, request, id):
        try:
            camp, deja = services.confirmer(id, request.user, bool(request.data.get("attestation_consentement")))
        except services.ErreurMetier as e:
            return _erreur(e)
        data = campagne_dict(camp)
        data["deja_confirmee"] = deja
        return Response(data, status=status.HTTP_200_OK)


class ArreterView(APIView):
    permission_classes = [AdminActif]

    def post(self, request, id):
        try:
            return Response(campagne_dict(services.arreter(id)))
        except services.ErreurMetier as e:
            return _erreur(e)


class RelancerView(APIView):
    permission_classes = [AdminActif]

    def post(self, request, id):
        try:
            return Response(campagne_dict(services.relancer_echecs(id)))
        except services.ErreurMetier as e:
            return _erreur(e)


class CampagnesView(ListAPIView):
    """Historique. Les aperçus jamais confirmés n'en font pas partie : rien n'a été envoyé."""
    permission_classes = [AdminActif]

    def get_queryset(self):
        return Campagne.objects.exclude(statut=Campagne.Statut.APERCU).select_related("auteur")

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([campagne_dict(c) for c in page])


class CampagneDetailView(APIView):
    permission_classes = [AdminActif]

    def get(self, request, id):
        c = Campagne.objects.select_related("auteur").filter(id=id).first()
        if c is None:
            return Response({"detail": "Introuvable."}, status=404)
        return Response(campagne_dict(c))


class MessagesView(ListAPIView):
    """?campagne=<id> et/ou ?utilisateur=<id> ; ?statut=. Téléphones toujours masqués."""
    permission_classes = [AdminActif]

    def get_queryset(self):
        qs = (MessageSms.objects.exclude(campagne__statut=Campagne.Statut.APERCU)
              .select_related("utilisateur").order_by("-id"))
        p = self.request.query_params
        if p.get("campagne", "").isdigit():
            qs = qs.filter(campagne_id=int(p["campagne"]))
        if p.get("utilisateur", "").isdigit():
            qs = qs.filter(utilisateur_id=int(p["utilisateur"]))
        if p.get("statut") in MessageSms.Statut.values:
            qs = qs.filter(statut=p["statut"])
        return qs

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([message_dict(m) for m in page])


class StatutActivationView(APIView):
    permission_classes = [AdminActif]

    def get(self, request):
        ids = [int(x) for x in request.query_params.get("ids", "").split(",") if x.strip().isdigit()][:200]
        return Response(services.statuts_activation(ids))


class PreferenceView(APIView):
    """Administrateur : consulte les préférences d'un compte et son éventuelle opposition."""
    permission_classes = [AdminActif]

    def get(self, request, id):
        u = User.objects.filter(id=id).first()
        if not u:
            return Response({"detail": "Introuvable."}, status=404)
        return Response(services.etat_preferences(u, admin=True))

    def patch(self, request, id):
        u = User.objects.filter(id=id).first()
        if not u:
            return Response({"detail": "Introuvable."}, status=404)
        ser = PreferenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        pref, _ = PreferenceCommunication.objects.get_or_create(utilisateur=u)
        for champ, valeur in ser.validated_data.items():
            setattr(pref, champ, valeur)
        pref.save()
        return Response(services.etat_preferences(u, admin=True))


class ConsentementParentalView(APIView):
    """Administrateur : valide, refuse ou révoque l'accord parental après vérification (consigné)."""
    permission_classes = [AdminActif]

    def post(self, request, id):
        u = User.objects.filter(id=id).first()
        if not u:
            return Response({"detail": "Introuvable."}, status=404)
        ser = DecisionParentaleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            return Response(services.decider_parental(request.user, u, d["decision"], d.get("methode", ""), d.get("note", "")))
        except services.ErreurMetier as e:
            return _erreur(e)


class ConsentementsParentauxView(APIView):
    """Administrateur : file des demandes d'accord parental à vérifier."""
    permission_classes = [AdminActif]

    def get(self, request):
        qs = (PreferenceCommunication.objects.filter(parental_statut=PreferenceCommunication.Parental.DEMANDE)
              .select_related("utilisateur").order_by("parental_demande_le")[:100])
        return Response([{
            "utilisateur_id": p.utilisateur_id,
            "nom": f"{p.utilisateur.prenom} {p.utilisateur.nom}".strip(),
            "parental_telephone": p.parental_telephone,
            "demande_le": p.parental_demande_le,
            "majorite": services.majorite(p.utilisateur),
        } for p in qs])


class MesPreferencesView(APIView):
    """Élève : ses propres préférences uniquement (aucun identifiant dans l'URL)."""
    permission_classes = [IsEleveActif]

    def get(self, request):
        return Response(services.etat_preferences(request.user))

    def patch(self, request):
        ser = PreferenceEleveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            return Response(services.maj_preferences_eleve(
                request.user, d.get("sms_facultatifs"), d.get("invitations_whatsapp"), d.get("parental_telephone")))
        except services.ErreurMetier as e:
            return _erreur(e)
