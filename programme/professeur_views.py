"""
API du Professeur particulier IA (étape 7, mathématiques seulement).

  POST /api/eleve/professeur/seances/                       démarrer (ou reprendre) une séance
  GET  /api/eleve/professeur/seances/<id>/                  état public de la séance
  POST /api/eleve/professeur/seances/<id>/reponse/          envoyer une réponse
  POST /api/eleve/professeur/seances/<id>/indice/           indice suivant (3 niveaux)
  POST /api/eleve/professeur/seances/<id>/explication/      « je n'ai pas compris », autre explication, exemple, pourquoi, question
  POST /api/eleve/professeur/seances/<id>/solution/         solution de l'ÉTAPE courante (si débloquée)
  POST /api/eleve/professeur/seances/<id>/suivante/         étape suivante (ou fin de l'exercice)

À chaque requête : JWT + IsEleveActif ; la séance doit appartenir à l'élève
(sinon 404 générique) ; le programme de la séance doit toujours appartenir à
sa classe ; la fonction doit être activée (désactivée par défaut, réservée au
développement). Les réponses ne contiennent jamais le plan, ni les réponses
attendues. Le navigateur n'envoie jamais d'historique.
"""

from django.conf import settings
from django.http import Http404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsEleveActif

from .correction.service import CorrectionRefusee
from .eleve_views import _programmes_de_la_classe
from .ia.exceptions import IAConfigurationInvalide, IAErreur, IAQuotaDepasse, IATimeout
from .lecture_exercice import ContexteProgramme, LectureTropLongue
from .professeur import seance
from .professeur.reponses import LONGUEUR_MAX_REPONSE
from .professeur.tour import TYPES_DEMANDE

TAILLE_MAX_ANALYSE_CARACTERES = 60_000


class DemarrerSerializer(serializers.Serializer):
    programme = serializers.IntegerField()
    analyse = serializers.DictField()

    def validate_analyse(self, valeur):
        import json

        if len(json.dumps(valeur, ensure_ascii=False)) > TAILLE_MAX_ANALYSE_CARACTERES:
            raise serializers.ValidationError("L'énoncé est trop volumineux.")
        return valeur


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=0)


class ReponseSerializer(VersionSerializer):
    texte = serializers.CharField(allow_blank=True, max_length=LONGUEUR_MAX_REPONSE + 200, trim_whitespace=True)


class ExplicationSerializer(VersionSerializer):
    type = serializers.ChoiceField(choices=list(TYPES_DEMANDE))
    texte = serializers.CharField(allow_blank=True, required=False, default="", max_length=LONGUEUR_MAX_REPONSE + 200)


def _erreur(message: str, code: int, motif: str = "erreur", **extra) -> Response:
    return Response({"detail": message, "code": motif, **extra}, status=code)


def _erreur_ia(exc: Exception) -> Response:
    if isinstance(exc, (CorrectionRefusee, LectureTropLongue)):
        return _erreur(str(exc), status.HTTP_400_BAD_REQUEST, "refuse")
    if isinstance(exc, IAConfigurationInvalide):
        return _erreur("Le professeur n'est pas configuré sur le serveur.", status.HTTP_503_SERVICE_UNAVAILABLE, "ia_indisponible")
    if isinstance(exc, IAQuotaDepasse):
        return _erreur("Le professeur est momentanément saturé. Réessaie dans quelques minutes.", status.HTTP_503_SERVICE_UNAVAILABLE, "ia_saturee")
    if isinstance(exc, IATimeout):
        return _erreur("Le professeur a pris trop de temps à répondre. Réessaie dans un instant.", status.HTTP_504_GATEWAY_TIMEOUT, "ia_lente")
    return _erreur("Le professeur n'a pas pu répondre. Réessaie dans un instant.", status.HTTP_502_BAD_GATEWAY, "ia_erreur")


def _reponse_etat(etat: dict, code=status.HTTP_200_OK, **extra) -> Response:
    corps = {"seance": seance.vue_publique(etat), **extra}
    if settings.DEBUG:
        corps["meta_dev"] = {**etat["jetons"], "appels_ia": etat["nb_appels_ia"]}
    return Response(corps, status=code)


class _BaseView(APIView):
    permission_classes = [IsEleveActif]

    def _programme(self, request, programme_id):
        return (
            _programmes_de_la_classe(request.user).select_related("matiere", "niveau", "serie").filter(pk=programme_id).first()
        )

    def _garde(self):
        if not seance.professeur_actif():
            return _erreur("Le Professeur particulier n'est pas encore disponible.", status.HTTP_503_SERVICE_UNAVAILABLE, "professeur_desactive")
        return None

    def _executer(self, operation):
        try:
            return operation()
        except seance.EtatObsolete as exc:
            return _erreur(str(exc), exc.statut_http, exc.code)
        except seance.ProfesseurErreur as exc:
            return _erreur(str(exc), exc.statut_http, exc.code)
        except (CorrectionRefusee, LectureTropLongue, IAErreur) as exc:
            return _erreur_ia(exc)


class SeancesView(_BaseView):
    def post(self, request):
        try:
            identifiant = int(request.data.get("programme"))
        except (TypeError, ValueError):
            identifiant = None
        programme = self._programme(request, identifiant) if identifiant is not None else None
        if identifiant is not None and programme is None:
            raise Http404
        if (refus := self._garde()) is not None:
            return refus
        serializer = DemarrerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if programme is None:
            raise Http404
        niveau = programme.niveau.nom
        classe = f"{niveau} {programme.serie.nom}" if programme.serie_id else niveau

        def operation():
            etat = seance.demarrer(
                utilisateur_id=request.user.id, programme_id=programme.id,
                contexte=ContexteProgramme(matiere=programme.matiere.nom, classe=classe),
                analyse_brute=serializer.validated_data["analyse"],
            )
            return _reponse_etat(etat, status.HTTP_200_OK if etat.get("reprise") else status.HTTP_201_CREATED, reprise=bool(etat.get("reprise")))

        return self._executer(operation)


class _SeanceView(_BaseView):
    """Base des vues portant sur une séance existante : propriété, programme et activation vérifiés à chaque requête."""

    serializer_class = VersionSerializer

    def _charger(self, request, id_seance):
        etat = seance.charger(id_seance, request.user.id)
        if self._programme(request, etat["programme_id"]) is None:
            raise seance.SeanceIntrouvable("Cette séance n'existe plus ou a expiré.")
        return etat

    def _traiter(self, request, id_seance, action):
        if (refus := self._garde()) is not None:
            return refus

        def operation():
            self._charger(request, id_seance)
            donnees = self.serializer_class(data=request.data)
            donnees.is_valid(raise_exception=True)
            return _reponse_etat(action(donnees.validated_data))

        return self._executer(operation)

    def _executer(self, operation):
        try:
            return operation()
        except seance.EtatObsolete as exc:
            try:
                courant = seance.charger(self.kwargs["id"], self.request.user.id)
                return _erreur(str(exc), exc.statut_http, exc.code, seance=seance.vue_publique(courant))
            except seance.ProfesseurErreur:
                return _erreur(str(exc), exc.statut_http, exc.code)
        except seance.ProfesseurErreur as exc:
            return _erreur(str(exc), exc.statut_http, exc.code)
        except IAErreur as exc:
            return _erreur_ia(exc)


class SeanceDetailView(_SeanceView):
    def get(self, request, id):
        if (refus := self._garde()) is not None:
            return refus
        return self._executer(lambda: _reponse_etat(self._charger(request, id)))


class ReponseView(_SeanceView):
    serializer_class = ReponseSerializer

    def post(self, request, id):
        return self._traiter(request, id, lambda d: seance.repondre(id, request.user.id, d["version"], d["texte"]))


class IndiceView(_SeanceView):
    def post(self, request, id):
        return self._traiter(request, id, lambda d: seance.indice(id, request.user.id, d["version"]))


class ExplicationView(_SeanceView):
    serializer_class = ExplicationSerializer

    def post(self, request, id):
        return self._traiter(request, id, lambda d: seance.explication(id, request.user.id, d["version"], d["type"], d["texte"]))


class SolutionView(_SeanceView):
    def post(self, request, id):
        return self._traiter(request, id, lambda d: seance.solution(id, request.user.id, d["version"]))


class SuivanteView(_SeanceView):
    def post(self, request, id):
        return self._traiter(request, id, lambda d: seance.suivante(id, request.user.id, d["version"]))
