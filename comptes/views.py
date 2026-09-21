from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    InscriptionEleveSerializer,
    MeSerializer,
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


class TelephoneTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — connexion par téléphone + mot de passe."""

    serializer_class = TelephoneTokenObtainPairSerializer


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me/ — profil de l'utilisateur connecté."""

    serializer_class = MeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
