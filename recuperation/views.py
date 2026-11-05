from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .services import ErreurRecuperation, ip_client


class _Anonyme(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []   # aucun jeton n'est lu : endpoints publics, bornés par recuperation.services

    @staticmethod
    def _erreur(exc: ErreurRecuperation) -> Response:
        corps = {"detail": exc.message, "code": exc.code}
        if exc.details:
            corps["details"] = exc.details
        reponse = Response(corps, status=exc.statut_http)
        if exc.retry_after:
            reponse["Retry-After"] = str(exc.retry_after)
            corps["retry_after"] = exc.retry_after
        return reponse


class _Telephone(serializers.Serializer):
    telephone = serializers.CharField(max_length=32)


class _Verification(_Telephone):
    code = serializers.CharField(max_length=12)


class _Reinitialisation(_Telephone):
    autorisation = serializers.CharField(max_length=200)
    nouveau_mot_de_passe = serializers.CharField(trim_whitespace=False, max_length=200)
    confirmation = serializers.CharField(trim_whitespace=False, max_length=200)


class DemanderCodeView(_Anonyme):
    """POST /api/auth/mot-de-passe-oublie/demander/ { telephone } : réponse neutre, qu'un compte existe ou non."""

    def post(self, request):
        s = _Telephone(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            return Response(services.demander_code(s.validated_data["telephone"], ip_client(request)))
        except ErreurRecuperation as exc:
            return self._erreur(exc)


class VerifierCodeView(_Anonyme):
    """POST .../verifier/ { telephone, code } : renvoie une autorisation temporaire à usage unique."""

    def post(self, request):
        s = _Verification(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            return Response(services.verifier_code(s.validated_data["telephone"], s.validated_data["code"], ip_client(request)))
        except ErreurRecuperation as exc:
            return self._erreur(exc)


class ReinitialiserView(_Anonyme):
    """POST .../reinitialiser/ { telephone, autorisation, nouveau_mot_de_passe, confirmation }. Pas de connexion auto."""

    def post(self, request):
        s = _Reinitialisation(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        try:
            return Response(services.reinitialiser(v["telephone"], v["autorisation"], v["nouveau_mot_de_passe"],
                                                   v["confirmation"], ip_client(request)))
        except ErreurRecuperation as exc:
            return self._erreur(exc)
