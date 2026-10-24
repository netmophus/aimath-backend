"""
POST /api/eleve/resoudre/ — réception et VALIDATION d'un exercice déposé par
un élève (« Résoudre mon exercice »), avec en option sa LECTURE par l'IA.

Le corps est vérifié, puis la réponse l'atteste (`valide: true`) en précisant
que rien n'a été enregistré (`enregistre: false`) ni résolu (`traite: false`).
Aucun fichier n'est écrit sur disque ; ni quota ni paiement.

ÉTAPE 5 : si le client envoie `analyser=true` ET que la lecture est activée
côté serveur (voir programme.lecture_exercice.lecture_activee — désactivée par
défaut, réservée au développement), l'exercice est lu par le modèle et la
réponse contient `analyse` (description structurée, SANS résolution). Sinon
`analyse` vaut null et `analyse_disponible` le dit : l'appelant retombe sur la
simple validation, sans erreur. `correction` (facultatif) transmet la remarque
de l'élève après relecture, pour une nouvelle lecture.

Même règle de sécurité que programme/eleve_views.py : le programme demandé
doit appartenir à la classe de l'élève (request.user) ; un id hors classe, ou
inexistant, donne le même 404 — jamais de 403 qui confirmerait son existence.
"""

from django.conf import settings
from django.http import Http404
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from comptes.permissions import IsEleveActif

from .eleve_views import _programmes_de_la_classe
from .exercice_serializers import DepotExerciceSerializer, matiere_resolvable
from .ia.exceptions import IAConfigurationInvalide, IAErreur, IAQuotaDepasse, IATimeout
from .lecture_exercice import (
    ContexteProgramme,
    LectureDejaEnCours,
    LectureRefusee,
    LectureTropLongue,
    PageExercice,
    lecture_activee,
    lire_exercice,
)
from .correction.service import correction_activee
from .professeur.seance import professeur_actif
from .programme_serializers import construire_libelle


class DepotExerciceView(APIView):
    permission_classes = [IsEleveActif]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = DepotExerciceSerializer(data=request.data)

        # 1) Accès au programme d'abord, avant toute lecture de fichier : un id
        #    étranger à la classe de l'élève → 404, quel que soit le reste.
        valeur = request.data.get("programme")
        programme = self._programme_accessible(request, valeur)
        if programme is None and self._id_programme(valeur) is not None:
            raise Http404

        # 2) Validation complète du corps (mode, énoncé, fichiers). Si
        #    `programme` est absent/illisible, l'erreur de champ est renvoyée ici.
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data
        if programme is None:  # défensif : ne devrait pas arriver une fois le corps valide
            raise Http404

        if not matiere_resolvable(programme.matiere.nom):
            return Response(
                {"programme": ["La résolution d'exercices n'est pas disponible pour cette matière."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fichiers = donnees["fichiers_valides"]

        analyse_disponible = lecture_activee()
        resultat = None
        if donnees["analyser"] and analyse_disponible:
            try:
                resultat = self._lire(request, programme, donnees)
            except LectureDejaEnCours as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            except (LectureRefusee, LectureTropLongue) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            except IAConfigurationInvalide:
                return self._erreur_ia(
                    "L'analyse des exercices n'est pas configurée sur le serveur.", status.HTTP_503_SERVICE_UNAVAILABLE
                )
            except IAQuotaDepasse:
                return self._erreur_ia(
                    "Le service d'analyse est momentanément saturé. Réessaie dans quelques minutes.",
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            except IATimeout:
                return self._erreur_ia(
                    "L'analyse a pris trop de temps. Réessaie, avec moins de pages si possible.",
                    status.HTTP_504_GATEWAY_TIMEOUT,
                )
            except IAErreur:
                return self._erreur_ia("L'analyse a échoué. Réessaie dans un instant.", status.HTTP_502_BAD_GATEWAY)

        reponse = {
            "valide": True,
            "enregistre": False,
            "traite": False,
            "analyse_disponible": analyse_disponible,
            "correction_disponible": analyse_disponible and correction_activee(),
            "professeur_disponible": analyse_disponible and professeur_actif(),
            "analysee": resultat is not None,
            "analyse": resultat.analyse if resultat else None,
            "analyse_depuis_cache": resultat.depuis_cache if resultat else False,
            "message": (
                "Ton exercice est valide, mais il n'a pas encore été enregistré ni traité : "
                "la résolution n'est pas encore disponible."
            ),
            "recapitulatif": {
                "programme": {
                    "id": programme.id,
                    "matiere": programme.matiere.nom,
                    "libelle": construire_libelle(programme),
                },
                "mode": donnees["mode"],
                "nb_fichiers": len(fichiers),
                "fichiers": fichiers,
                "enonce_caracteres": len(donnees["enonce"]),
            },
        }
        if resultat and settings.DEBUG:
            # Suivi de coût en développement seulement.
            reponse["meta_dev"] = {
                "modele": resultat.modele,
                "tokens_entree": resultat.tokens_entree,
                "tokens_sortie": resultat.tokens_sortie,
            }
        return Response(reponse, status=status.HTTP_200_OK)

    @staticmethod
    def _erreur_ia(message: str, code: int) -> Response:
        return Response({"detail": message}, status=code)

    @staticmethod
    def _lire(request, programme, donnees):
        """Lit les fichiers (dans l'ordre d'envoi) puis appelle le service de lecture.
        Les octets ne vivent qu'en mémoire, le temps de la requête."""
        pages = []
        for fichier, infos in zip(donnees.get("fichiers") or [], donnees["fichiers_valides"]):
            fichier.seek(0)
            pages.append(PageExercice(nom=infos["nom"], type=infos["type"], octets=fichier.read()))
            fichier.seek(0)

        niveau = programme.niveau.nom
        classe = f"{niveau} {programme.serie.nom}" if programme.serie_id else niveau
        return lire_exercice(
            utilisateur_id=request.user.id,
            programme_id=programme.id,
            contexte=ContexteProgramme(matiere=programme.matiere.nom, classe=classe),
            pages=pages,
            enonce=donnees["enonce"],
            correction=donnees["correction"],
        )

    @staticmethod
    def _id_programme(valeur) -> int | None:
        try:
            return int(valeur)
        except (TypeError, ValueError):
            return None

    def _programme_accessible(self, request, valeur):
        identifiant = self._id_programme(valeur)
        if identifiant is None:
            return None
        return (
            _programmes_de_la_classe(request.user)
            .select_related("matiere", "niveau", "serie")
            .filter(pk=identifiant)
            .first()
        )
