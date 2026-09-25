"""
Paiement NITA — second moyen (avec les cartes Fahimta) de créditer
abonnement_actif_jusqu_au. Voir comptes/nita.py pour le client HTTP/mock et
le catalogue de plans, comptes/models.py pour PaiementNita.

GET  n/a
POST /api/eleve/nita/initier/   (élève connecté)  → crée l'achat NITA, renvoie {reference, requestId}
POST /api/nita/callback/        (PUBLIC, pas de JWT — appelé par NITA)     → déclencheur, RE-VÉRIFIE toujours
POST /api/eleve/nita/verifier/  (élève connecté)  → filet de secours, même logique de crédit que le callback
POST /api/nita/mock/confirmer/  (admin, actif SEULEMENT si NITA_MOCK)      → simule une confirmation NITA

RÈGLES DE SÉCURITÉ (voir comptes/nita.py pour le détail) :
- Le webhook NE FAIT JAMAIS confiance au statut reçu dans son body/sa query
  — il ré-interroge activement NITA (nita_check_status) avant de créditer.
- Idempotence stricte : `crediter_paiement_nita()` verrouille la ligne
  PaiementNita (select_for_update) et vérifie qu'elle n'est pas déjà
  "confirme" avant de toucher à l'abonnement — callback et "vérifier" (ou
  deux appels concurrents du même mécanisme) partagent CETTE MÊME fonction,
  jamais deux implémentations séparées du crédit.
"""

from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PaiementNita, User
from .nita import (
    PLANS_NITA,
    NitaError,
    generer_request_id,
    nita_check_status,
    nita_creer_achat,
    normaliser_telephone_nita,
)
from .nita_serializers import (
    InitierPaiementNitaSerializer,
    MockConfirmerSerializer,
    VerifierPaiementNitaSerializer,
)
from .permissions import IsAdminRole, IsEleveActif


def crediter_paiement_nita(paiement_id: int) -> bool:
    """Crédite l'abonnement pour ce PaiementNita SI ET SEULEMENT SI il
    n'est pas déjà "confirme" — appelée uniquement après que l'appelant a
    lui-même vérifié activement le statut auprès de NITA (jamais sur la
    seule foi d'un body de callback). select_for_update() sur la ligne
    PaiementNita : deux appels concurrents (ex. le webhook et "vérifier
    maintenant" arrivant en même temps) se sérialisent sur CE verrou — le
    second constate, une fois le premier terminé, que le statut est déjà
    "confirme" et ne crédite pas une seconde fois. Retourne True si CET
    appel a effectivement crédité, False si c'était déjà fait avant."""
    with transaction.atomic():
        paiement = PaiementNita.objects.select_for_update().get(pk=paiement_id)
        if paiement.statut == PaiementNita.Statut.CONFIRME:
            return False

        user = User.objects.select_for_update().get(pk=paiement.user_id)
        aujourdhui = timezone.localdate()
        base = max(aujourdhui, user.abonnement_actif_jusqu_au or aujourdhui)
        user.abonnement_actif_jusqu_au = base + timedelta(days=paiement.duree_jours)
        user.save(update_fields=["abonnement_actif_jusqu_au"])

        paiement.statut = PaiementNita.Statut.CONFIRME
        paiement.date_confirmation = timezone.now()
        paiement.save(update_fields=["statut", "date_confirmation"])

    return True


class InitierPaiementNitaView(APIView):
    """POST /api/eleve/nita/initier/ — { "plan": "mensuel" }."""

    permission_classes = [IsEleveActif]

    def post(self, request):
        serializer = InitierPaiementNitaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_id = serializer.validated_data["plan"]
        plan = PLANS_NITA[plan_id]
        user = request.user

        request_id = generer_request_id()
        telephone_nita = normaliser_telephone_nita(user.telephone)
        # URL publique du webhook, construite depuis LA requête entrante :
        # correcte quel que soit le domaine de déploiement (dev/ngrok/prod),
        # jamais un domaine codé en dur dans le code source.
        url_callback = request.build_absolute_uri("/api/nita/callback/")

        # La ligne existe dès ici (reference_nita encore vide) : un échec de
        # l'appel NITA juste après reste traçable ("echoue"), jamais une
        # tentative silencieusement perdue.
        paiement = PaiementNita.objects.create(
            user=user,
            telephone=user.telephone,
            montant=plan["montant"],
            duree_jours=plan["duree_jours"],
            request_id=request_id,
            statut=PaiementNita.Statut.EN_ATTENTE,
        )

        try:
            reference = nita_creer_achat(
                request_id=request_id,
                montant=plan["montant"],
                motif=f"Abonnement Fahimta - {plan['label']}",
                telephone_nita=telephone_nita,
                url_callback=url_callback,
            )
        except NitaError as exc:
            paiement.statut = PaiementNita.Statut.ECHOUE
            paiement.save(update_fields=["statut"])
            return Response(
                {"detail": f"Impossible de démarrer le paiement NITA. {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        paiement.reference_nita = reference
        paiement.save(update_fields=["reference_nita"])

        return Response(
            {"reference": reference, "requestId": request_id},
            status=status.HTTP_201_CREATED,
        )


class NitaCallbackView(APIView):
    """
    POST /api/nita/callback/ — PUBLIC (appelé par les serveurs NITA, jamais
    par le navigateur de l'élève) : pas d'authentification JWT possible,
    donc AllowAny — mais ce n'est PAS un blanc-seing : le body envoyé par
    l'appelant n'est JAMAIS cru sur parole. Seul `requestId` en est extrait
    pour retrouver LE PaiementNita concerné ; tout le reste (le paiement
    est-il réellement confirmé ?) est re-vérifié activement auprès de NITA
    (nita_check_status) avant tout crédit — voir crediter_paiement_nita.

    Répond toujours 200 à NITA (même sur un cas métier non abouti :
    requestId inconnu, pas encore payé, NITA injoignable pour la
    vérification) pour éviter des retentatives en boucle côté NITA sur un
    cas qui ne se résoudra pas différemment ; seule une erreur serveur
    réellement inattendue renvoie autre chose.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        request_id = request.data.get("requestId") or request.query_params.get("requestId")
        if not request_id:
            return Response({"detail": "requestId manquant."}, status=status.HTTP_200_OK)

        paiement = PaiementNita.objects.filter(request_id=request_id).first()
        if paiement is None:
            return Response({"detail": "requestId inconnu."}, status=status.HTTP_200_OK)

        if paiement.statut == PaiementNita.Statut.CONFIRME:
            return Response({"detail": "Déjà confirmé."}, status=status.HTTP_200_OK)

        try:
            telephone_nita = normaliser_telephone_nita(paiement.telephone)
            paye = nita_check_status(
                request_id=paiement.request_id,
                reference=paiement.reference_nita,
                telephone_nita=telephone_nita,
            )
        except NitaError as exc:
            # Le webhook a un requestId valide mais la ré-vérification
            # échoue (NITA injoignable côté vérif) : on ne crédite PAS, le
            # paiement reste en_attente — "vérifier maintenant" ou un
            # prochain appel du webhook (NITA réessaie ses callbacks)
            # pourra réussir plus tard.
            return Response({"detail": f"Vérification NITA impossible : {exc}"}, status=status.HTTP_200_OK)

        if not paye:
            return Response({"detail": "Paiement non confirmé pour l'instant."}, status=status.HTTP_200_OK)

        crediter_paiement_nita(paiement.pk)
        return Response({"detail": "OK"}, status=status.HTTP_200_OK)


class VerifierPaiementNitaView(APIView):
    """
    POST /api/eleve/nita/verifier/ — { "requestId": "FAH-..." } : filet de
    secours ACTIF (branché dès le départ, pas laissé "dormant" comme dans
    l'intégration source) — l'élève clique "J'ai payé, vérifier maintenant"
    si le webhook n'est pas encore arrivé. MÊME logique de crédit que le
    webhook (crediter_paiement_nita) : aucune divergence possible entre les
    deux chemins.

    Filtré sur `user=request.user` : un élève ne peut vérifier/déclencher
    que SES PROPRES tentatives de paiement, jamais un requestId qui ne lui
    appartient pas.
    """

    permission_classes = [IsEleveActif]

    def post(self, request):
        serializer = VerifierPaiementNitaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = serializer.validated_data["requestId"]

        paiement = PaiementNita.objects.filter(request_id=request_id, user=request.user).first()
        if paiement is None:
            return Response({"detail": "Paiement introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if paiement.statut == PaiementNita.Statut.CONFIRME:
            user = User.objects.get(pk=paiement.user_id)
            return Response(
                {
                    "confirme": True,
                    "message": "Paiement déjà confirmé.",
                    "abonnement_actif_jusqu_au": user.abonnement_actif_jusqu_au,
                }
            )

        try:
            telephone_nita = normaliser_telephone_nita(paiement.telephone)
            paye = nita_check_status(
                request_id=paiement.request_id,
                reference=paiement.reference_nita,
                telephone_nita=telephone_nita,
            )
        except NitaError as exc:
            return Response(
                {"detail": f"NITA injoignable pour l'instant. Réessaie dans quelques secondes. ({exc})"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not paye:
            return Response({"confirme": False, "message": "Paiement pas encore confirmé."})

        crediter_paiement_nita(paiement.pk)
        user = User.objects.get(pk=paiement.user_id)
        return Response(
            {
                "confirme": True,
                "message": "✅ Paiement confirmé, abonnement crédité.",
                "abonnement_actif_jusqu_au": user.abonnement_actif_jusqu_au,
            }
        )


class NitaMockConfirmerView(APIView):
    """
    POST /api/nita/mock/confirmer/ — { "requestId": "FAH-..." } : bascule
    la réponse SIMULÉE de nita_check_status() à "payé" pour ce requestId
    (voir comptes.nita.nita_check_status). N'existe RÉELLEMENT que si
    settings.NITA_MOCK est vrai (jamais en production) ; réservé admin en
    plus, en défense en profondeur — sert uniquement à tester tout le
    circuit (initier → callback/vérifier → crédit → idempotence) sans
    jamais appeler la vraie API NITA ni engager de vrai argent.
    """

    permission_classes = [IsAdminRole]

    def post(self, request):
        if not settings.NITA_MOCK:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = MockConfirmerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = serializer.validated_data["requestId"]

        if not PaiementNita.objects.filter(request_id=request_id).exists():
            return Response({"detail": "requestId inconnu."}, status=status.HTTP_404_NOT_FOUND)

        # Pas de TTL explicite : la valeur est nettoyée avec le reste du
        # cache local (LocMemCache) au redémarrage du process ; un test qui
        # simule un paiement n'a pas besoin d'expiration entre-temps.
        cache.set(f"nita_mock_paye_{request_id}", True)
        return Response({"detail": f"Paiement simulé confirmé pour {request_id}."})
