"""
Serializers pour l'espace élève : lecture seule, dédiés (jamais les
serializers admin, qui exposent trop — statut de leçon, ids internes de
vidéos/ressources, compteurs de brouillons, etc.).

La classe (niveau + série) vient toujours de request.user côté vue ; ces
serializers se contentent de mettre en forme des querysets déjà filtrés.
"""

from rest_framework import serializers

from .lecon_serializers import construire_chemin
from .models import Chapitre, Exercice, Lecon, Notion, Programme, Ressource, TermeGlossaire, Theme, Video
from .programme_serializers import construire_libelle


class InfosProgrammeMixin:
    """Champs matiere/niveau/serie/libelle communs aux deux serializers Programme élève."""

    def get_matiere(self, obj: Programme) -> dict:
        return {"id": obj.matiere_id, "nom": obj.matiere.nom}

    def get_niveau(self, obj: Programme) -> dict:
        return {"id": obj.niveau_id, "nom": obj.niveau.nom}

    def get_serie(self, obj: Programme) -> dict | None:
        return {"id": obj.serie_id, "nom": obj.serie.nom} if obj.serie_id else None

    def get_libelle(self, obj: Programme) -> str:
        return construire_libelle(obj)


# --- GET /api/eleve/mon-programme/ ---

class ProgrammeEleveSerializer(InfosProgrammeMixin, serializers.ModelSerializer):
    matiere = serializers.SerializerMethodField()
    niveau = serializers.SerializerMethodField()
    serie = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
    nb_lecons_publiees = serializers.SerializerMethodField()

    class Meta:
        model = Programme
        fields = ["id", "matiere", "niveau", "serie", "libelle", "nb_lecons_publiees"]

    def get_nb_lecons_publiees(self, obj: Programme) -> int:
        valeur = getattr(obj, "nb_lecons_publiees", None)
        if valeur is not None:
            return valeur
        return Lecon.objects.filter(
            notion__chapitre__theme__programme=obj, statut=Lecon.Statut.PUBLIE
        ).count()


# --- GET /api/eleve/programmes/{id}/ : arbre filtré ---

class NotionEleveSerializer(serializers.ModelSerializer):
    """Une notion, visible même sans leçon publiée ("leçon à venir" côté front)."""

    a_lecon_publiee = serializers.SerializerMethodField()
    lecon_id = serializers.SerializerMethodField()

    class Meta:
        model = Notion
        fields = ["id", "titre", "ordre", "a_lecon_publiee", "lecon_id"]

    def _lecon_publiee(self, obj: Notion) -> Lecon | None:
        lecon = getattr(obj, "lecon", None)
        return lecon if lecon and lecon.statut == Lecon.Statut.PUBLIE else None

    def get_a_lecon_publiee(self, obj: Notion) -> bool:
        return self._lecon_publiee(obj) is not None

    def get_lecon_id(self, obj: Notion) -> int | None:
        lecon = self._lecon_publiee(obj)
        return lecon.id if lecon else None


class ChapitreEleveSerializer(serializers.ModelSerializer):
    notions = NotionEleveSerializer(many=True, read_only=True)

    class Meta:
        model = Chapitre
        fields = ["id", "titre", "ordre", "notions"]


class ThemeEleveSerializer(serializers.ModelSerializer):
    chapitres = ChapitreEleveSerializer(many=True, read_only=True)

    class Meta:
        model = Theme
        fields = ["id", "titre", "volume_horaire", "ordre", "chapitres"]


class ProgrammeDetailEleveSerializer(InfosProgrammeMixin, serializers.ModelSerializer):
    matiere = serializers.SerializerMethodField()
    niveau = serializers.SerializerMethodField()
    serie = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
    themes = ThemeEleveSerializer(many=True, read_only=True)

    class Meta:
        model = Programme
        fields = ["id", "matiere", "niveau", "serie", "libelle", "themes"]


# --- GET /api/eleve/lecons/{id}/ : contenu complet d'une leçon publiée ---

class ExerciceEleveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercice
        fields = ["id", "enonce", "corrige", "difficulte", "ordre"]


class VideoEleveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ["titre", "url", "description", "ordre"]


class RessourceEleveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ressource
        fields = ["titre", "url", "ordre"]


class LeconEleveSerializer(serializers.ModelSerializer):
    notion = serializers.SerializerMethodField()
    exercices = ExerciceEleveSerializer(many=True, read_only=True)
    videos = VideoEleveSerializer(many=True, read_only=True)
    ressources = RessourceEleveSerializer(many=True, read_only=True)

    class Meta:
        model = Lecon
        fields = [
            "id", "titre",
            "notion",
            "histoire",
            "objectifs_pedagogiques", "prerequis_texte",
            "cours_redige", "demonstrations", "a_retenir",
            "sujet_examen",
            "exercices", "videos", "ressources",
        ]

    def get_notion(self, obj: Lecon) -> dict:
        chapitre = obj.notion.chapitre
        theme = chapitre.theme
        programme = theme.programme
        return {
            "id": obj.notion_id,
            "titre": obj.notion.titre,
            "chapitre": {"id": chapitre.id, "titre": chapitre.titre},
            "theme": {"id": theme.id, "titre": theme.titre},
            "programme": {"id": programme.id, "libelle": construire_libelle(programme)},
        }


# --- (optionnel) GET /api/eleve/mes-lecons/ : liste plate ---

class LeconListeEleveSerializer(serializers.ModelSerializer):
    notion = serializers.SerializerMethodField()
    chemin = serializers.SerializerMethodField()

    class Meta:
        model = Lecon
        fields = ["id", "titre", "notion", "chemin"]

    def get_notion(self, obj: Lecon) -> dict:
        return {"id": obj.notion_id, "titre": obj.notion.titre}

    def get_chemin(self, obj: Lecon) -> str:
        return construire_chemin(obj.notion)


# --- GET /api/eleve/glossaire/{slug}/ et /api/eleve/glossaire/?slugs=... ---

class TermeGlossaireEleveSerializer(serializers.ModelSerializer):
    """Le glossaire (définition/exemple) est visible par tout élève actif,
    sans cloisonnement par classe — seul le LIEN vers la leçon l'est :
    `lecon_liee` n'est renvoyé que si la leçon existe, est publiée, ET
    appartient à la classe de l'élève (mêmes règles que /api/eleve/lecons/).
    """

    lecon_liee = serializers.SerializerMethodField()

    class Meta:
        model = TermeGlossaire
        fields = ["terme", "slug", "definition", "exemple", "lecon_liee"]

    def get_lecon_liee(self, obj: TermeGlossaire) -> dict | None:
        lecon = obj.lecon_liee
        if lecon is None or lecon.statut != Lecon.Statut.PUBLIE:
            return None

        user = self.context["request"].user
        programme = lecon.notion.chapitre.theme.programme
        if programme.niveau_id != user.niveau_id or programme.serie_id != user.serie_id:
            return None

        return {"id": lecon.id, "titre": lecon.titre}
