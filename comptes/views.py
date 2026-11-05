from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from programme.models import Cycle

from .cartes import (
    enregistrer_echec,
    formater_date_fr,
    normaliser_code,
    reinitialiser_echecs,
    trop_de_tentatives,
)
from .jetons import RefreshVersionne
from .models import CarteFahimta
from .permissions import IsEleveActif
from .sms import envoyer_sms
from recuperation.services import (
    ErreurRecuperation,
    effacer_echecs_changement,
    enregistrer_echec_changement,
    ip_client,
    verifier_blocage_changement,
)
from .serializers import (
    ActiverCarteSerializer,
    CarteRecueEleveSerializer,
    ChangerMotDePasseSerializer,
    CyclePublicSerializer,
    InscriptionEleveSerializer,
    MeSerializer,
    ModifierMotDePasseSerializer,
    ProfilEleveSerializer,
    TelephoneTokenObtainPairSerializer,
)


class InscriptionEleveView(generics.CreateAPIView):
    """POST /api/auth/register/ — inscription élève, compte en_attente."""

    serializer_class = InscriptionEleveSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        classe = user.niveau.nom if user.niveau else None
        if user.serie:
            classe = f"{classe} {user.serie.nom}"

        return Response(
            {
                "message": (
                    "Inscription enregistrée. Ton compte est en attente de "
                    "validation par un administrateur."
                ),
                "utilisateur": {
                    "prenom": user.prenom,
                    "nom": user.nom,
                    "telephone": user.telephone,
                    "classe": classe,
                    "statut": user.statut,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class ClassesPubliquesView(generics.ListAPIView):
    """
    GET /api/auth/classes/ — hiérarchie Cycle → Niveau → Série, publique
    (AllowAny) : alimente la cascade du formulaire d'inscription élève
    (/register), qui tourne sans authentification. Rien de sensible n'est
    exposé (juste les cycles/niveaux/séries existants, id + nom).
    Pas de pagination : réponse = tableau brut, la hiérarchie est petite.
    """

    serializer_class = CyclePublicSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    queryset = Cycle.objects.prefetch_related("niveaux__series").order_by("ordre")


class TelephoneTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — connexion par téléphone + mot de passe."""

    serializer_class = TelephoneTokenObtainPairSerializer


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me/ — profil de l'utilisateur connecté."""

    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


def _jetons_pour(user) -> dict:
    """Nouveaux jetons pour l'appareil courant : les anciens sont refusés après un changement de mot de passe."""
    refresh = RefreshVersionne.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class ChangerMotDePasseView(APIView):
    """
    POST /api/auth/changer-mot-de-passe/ — { "nouveau_mot_de_passe" }

    Changement FORCÉ uniquement (après réinitialisation par un admin) : réservé aux comptes actifs dont
    doit_changer_mdp est vrai. Pour un changement volontaire, voir ModifierMotDePasseView (ancien mot de passe exigé).
    Agit TOUJOURS sur request.user. Renvoie de nouveaux jetons : les anciens sont invalidés.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.doit_changer_mdp or user.statut != user.Statut.ACTIF:
            return Response({"detail": "Changement non autorisé par ce parcours. Utilise « Modifier mon mot de passe »."},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = ChangerMotDePasseSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        user.doit_changer_mdp = False
        user.save(update_fields=["password", "doit_changer_mdp"])

        return Response({"message": "Mot de passe modifié.", **_jetons_pour(user)})


class ModifierMotDePasseView(APIView):
    """
    POST /api/auth/modifier-mot-de-passe/ — { "mot_de_passe_actuel", "nouveau_mot_de_passe", "confirmation" }

    Changement VOLONTAIRE d'un utilisateur connecté et actif. Le mot de passe actuel est vérifié (check_password) ;
    5 erreurs en 15 minutes verrouillent temporairement le changement. Ne touche jamais doit_changer_mdp à la
    hausse. Les autres sessions sont invalidées ; de nouveaux jetons sont renvoyés pour l'appareil courant.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.statut != user.Statut.ACTIF:
            return Response({"detail": "Compte non actif."}, status=status.HTTP_403_FORBIDDEN)
        ip = ip_client(request)
        try:
            verifier_blocage_changement(user, ip)
        except ErreurRecuperation as exc:
            reponse = Response({"detail": exc.message}, status=exc.statut_http)
            if exc.retry_after:
                reponse["Retry-After"] = str(exc.retry_after)
            return reponse

        serializer = ModifierMotDePasseSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        actuel = serializer.validated_data["mot_de_passe_actuel"]
        if not user.check_password(actuel):
            enregistrer_echec_changement(user, ip)
            return Response({"mot_de_passe_actuel": ["Mot de passe actuel incorrect."]}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["nouveau_mot_de_passe"])
        user.save(update_fields=["password"])
        effacer_echecs_changement(user)
        return Response({"message": "Mot de passe modifié.", **_jetons_pour(user)})


class ProfilEleveView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH/PUT /api/eleve/profil/ — profil enrichi de l'élève connecté.

    IsEleveActif (pas seulement IsAuthenticated) : cohérent avec le reste de
    l'espace élève (voir programme/eleve_views.py). get_object() renvoie
    TOUJOURS request.user, jamais un id de l'URL ou du corps — impossible de
    modifier le profil de quelqu'un d'autre par ce endpoint.
    """

    serializer_class = ProfilEleveSerializer
    permission_classes = [IsEleveActif]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user


class ActiverCarteView(APIView):
    """
    POST /api/eleve/activer-carte/ — { "code": "FH-XXXX-XXXX-XXXX" }

    Crédite l'abonnement de l'élève connecté (request.user UNIQUEMENT —
    jamais un id passé par le client) avec la durée de la carte. Transaction
    atomique + select_for_update() sur la carte : deux activations
    simultanées du même code ne peuvent pas toutes les deux réussir, la
    seconde trouve la carte déjà "utilisee" une fois le verrou de la
    première relâché.

    Nouvelle date = max(aujourd'hui, échéance actuelle) + durée de la carte
    — un abonnement déjà actif est PROLONGÉ, jamais raccourci ni remplacé.
    """

    permission_classes = [IsEleveActif]

    def post(self, request):
        user = request.user

        if trop_de_tentatives(user):
            return Response(
                {"detail": "Trop de tentatives. Réessaie dans une heure."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = ActiverCarteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = normaliser_code(serializer.validated_data["code"])

        with transaction.atomic():
            carte = CarteFahimta.objects.select_for_update().filter(code=code).first()

            if carte is None:
                enregistrer_echec(user)
                return Response({"detail": "Code invalide."}, status=status.HTTP_400_BAD_REQUEST)

            if carte.statut == CarteFahimta.Statut.UTILISEE:
                enregistrer_echec(user)
                return Response(
                    {"detail": "Ce code a déjà été utilisé."}, status=status.HTTP_400_BAD_REQUEST
                )

            aujourdhui = timezone.localdate()
            base = max(aujourdhui, user.abonnement_actif_jusqu_au or aujourdhui)
            nouvelle_date = base + timedelta(days=carte.duree_jours)

            user.abonnement_actif_jusqu_au = nouvelle_date
            user.save(update_fields=["abonnement_actif_jusqu_au"])

            carte.statut = CarteFahimta.Statut.UTILISEE
            carte.utilisee_par = user
            carte.date_activation = timezone.now()
            carte.save(update_fields=["statut", "utilisee_par", "date_activation"])

        reinitialiser_echecs(user)

        # SMS de confirmation (voir comptes.sms) — APRÈS le commit, jamais
        # dans le bloc atomique : envoyer_sms() ne lève jamais, mais un SMS
        # ne doit de toute façon jamais retarder/conditionner la réponse de
        # succès d'une activation déjà actée en base.
        envoyer_sms(
            user.telephone,
            f"Fahimta : ton abonnement est actif jusqu'au {formater_date_fr(nouvelle_date)}. Bon travail !",
        )

        return Response(
            {
                "message": (
                    f"Abonnement activé ! Tu as accès à tous les cours "
                    f"jusqu'au {formater_date_fr(nouvelle_date)}."
                ),
                "abonnement_actif_jusqu_au": nouvelle_date,
            }
        )


class MesCartesEleveView(generics.ListAPIView):
    """
    GET /api/eleve/mes-cartes/ — TOUTES les cartes qui concernent l'élève
    connecté (request.user UNIQUEMENT), code en clair (voir
    CarteRecueEleveSerializer) : celles qu'un vendeur lui a attribuées
    (attribuee_a, à activer ou déjà activées) ET celles qu'il a activées
    lui-même sans être passé par un vendeur (utilisee_par seul — un code
    acheté/obtenu autrement, sans attribuee_a jamais renseigné). Les deux
    ensembles se recouvrent pour une carte vendue puis activée par ce même
    élève (attribuee_a ET utilisee_par pointent alors vers lui) — le OR
    évite un doublon dans ce cas.

    Distinct de l'activation elle-même (ActiverCarteView ci-dessus) : cette
    vue ne fait que LISTER, l'élève active ensuite en collant le code sur
    /eleve/abonnement.
    """

    serializer_class = CarteRecueEleveSerializer
    permission_classes = [IsEleveActif]

    def get_queryset(self):
        user = self.request.user
        return (
            CarteFahimta.objects.filter(Q(attribuee_a=user) | Q(utilisee_par=user))
            # Une seule clé de tri, la plus pertinente en priorité : date
            # d'activation si activée, sinon date d'attribution, sinon (cas
            # limite théorique) date de création.
            .annotate(date_tri=Coalesce("date_activation", "date_attribution", "date_creation"))
            .order_by("-date_tri")
        )
