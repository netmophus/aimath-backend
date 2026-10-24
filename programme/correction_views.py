"""
POST /api/eleve/correction/ — correction complète d'un exercice de maths à
partir de l'énoncé DÉJÀ lu et confirmé par l'élève (étape 6, pilote).

Corps JSON : {"programme": <id>, "analyse": {…énoncé confirmé, tel que renvoyé
par /api/eleve/resoudre/…}}. Aucun fichier : les documents ne sont pas relus.

Sécurité (même règles que le dépôt) : JWT + IsEleveActif ; le programme doit
appartenir à la classe de l'élève (sinon le même 404 générique) ; la matière
doit être les mathématiques ; la fonction est désactivée par défaut
(IA_CORRECTION_ACTIVE) et réservée au développement ; l'énoncé reçu est
re-normalisé côté serveur (types, longueurs) avant tout usage, et sa
cohérence (lisible, aucune partie incertaine, aucune figure non interprétée)
est revérifiée ici : on ne fait pas confiance à l'écran.
"""

from django.conf import settings
from django.http import Http404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsEleveActif

from .correction.service import (
    CorrectionDejaEnCours, CorrectionRefusee, corriger_exercice, correction_activee,
)
from .eleve_views import _programmes_de_la_classe
from .ia.exceptions import IAConfigurationInvalide, IAErreur, IAQuotaDepasse, IATimeout
from .lecture_exercice import ContexteProgramme, LectureTropLongue, normaliser_analyse
from .programme_serializers import construire_libelle
from .simulations import avec_simulations

TAILLE_MAX_ANALYSE_CARACTERES = 60_000


class CorrectionSerializer(serializers.Serializer):
    programme = serializers.IntegerField()
    analyse = serializers.DictField()

    def validate_analyse(self, valeur):
        import json

        if len(json.dumps(valeur, ensure_ascii=False)) > TAILLE_MAX_ANALYSE_CARACTERES:
            raise serializers.ValidationError("L'énoncé est trop volumineux pour être corrigé.")
        return valeur


class CorrectionExerciceView(APIView):
    permission_classes = [IsEleveActif]

    def post(self, request):
        try:
            identifiant = int(request.data.get("programme"))
        except (TypeError, ValueError):
            identifiant = None
        programme = None
        if identifiant is not None:
            programme = (
                _programmes_de_la_classe(request.user)
                .select_related("matiere", "niveau", "serie")
                .filter(pk=identifiant)
                .first()
            )
        if programme is None and identifiant is not None:
            raise Http404

        if not correction_activee():
            return Response(
                {"detail": "La correction complète n'est pas encore disponible.", "code": "correction_desactivee"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = CorrectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if programme is None:
            raise Http404

        niveau = programme.niveau.nom
        classe = f"{niveau} {programme.serie.nom}" if programme.serie_id else niveau
        contexte = ContexteProgramme(matiere=programme.matiere.nom, classe=classe)
        try:
            resultat = corriger_exercice(
                utilisateur_id=request.user.id,
                programme_id=programme.id,
                contexte=contexte,
                analyse_brute=serializer.validated_data["analyse"],
            )
        except CorrectionDejaEnCours as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (CorrectionRefusee, LectureTropLongue) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except IAConfigurationInvalide:
            return self._erreur("La correction n'est pas configurée sur le serveur.", status.HTTP_503_SERVICE_UNAVAILABLE)
        except IAQuotaDepasse:
            return self._erreur("Le service de correction est momentanément saturé. Réessaie dans quelques minutes.", status.HTTP_503_SERVICE_UNAVAILABLE)
        except IATimeout:
            return self._erreur("La correction a pris trop de temps. Réessaie dans un instant.", status.HTTP_504_GATEWAY_TIMEOUT)
        except IAErreur:
            return self._erreur("La correction a échoué. Réessaie dans un instant.", status.HTTP_502_BAD_GATEWAY)

        # Simulations : ajoutées à une COPIE (la correction en cache reste intacte) et seulement si le réglage les autorise.
        correction = avec_simulations(resultat.correction, normaliser_analyse(serializer.validated_data["analyse"], contexte), programme.matiere.nom)
        reponse = {
            "correction": correction,
            "correction_depuis_cache": resultat.depuis_cache,
            "programme": {"id": programme.id, "matiere": programme.matiere.nom, "libelle": construire_libelle(programme)},
        }
        if settings.DEBUG and not resultat.depuis_cache:
            reponse["meta_dev"] = {
                "modele": resultat.modele,
                "tokens_entree": resultat.tokens_entree,
                "tokens_sortie": resultat.tokens_sortie,
            }
        return Response(reponse, status=status.HTTP_200_OK)

    @staticmethod
    def _erreur(message: str, code: int) -> Response:
        return Response({"detail": message}, status=code)
