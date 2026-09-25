"""
Serializers admin pour la Lecon (le contenu produit) et ses éléments
imbriqués (Exercice, Video, Ressource).

Convention de synchronisation des listes imbriquées (exercices, videos,
ressources) en création ET en modification — voir `_synchroniser` sur
LeconEcritureSerializer :
  - un objet SANS "id" est créé ;
  - un objet AVEC "id" met à jour l'existant (l'id doit appartenir à cette
    leçon, sinon 400) ;
  - un id déjà présent en base mais absent de la liste envoyée est supprimé.
Le front doit donc toujours envoyer la liste COMPLÈTE souhaitée pour chaque
collection, pas un delta.

Les ressources de type fichier (upload) sont hors scope ici : seules les
ressources "url" sont gérées en écriture pour l'instant.
"""

from django.db import transaction
from rest_framework import serializers

from .models import Exercice, Lecon, Notion, Ressource, Video
from .programme_serializers import construire_libelle


def construire_chemin(notion: Notion) -> str:
    """Ex: "Terminale C · Thème 4 · Fonctions logarithmes"."""
    chapitre = notion.chapitre
    theme = chapitre.theme
    programme = theme.programme
    classe = f"{programme.niveau.nom} {programme.serie.nom}" if programme.serie_id else programme.niveau.nom
    return f"{classe} · Thème {theme.ordre} · {chapitre.titre}"


# --- Éléments imbriqués : lecture ---

class ExerciceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercice
        fields = ["id", "enonce", "corrige", "difficulte", "ordre"]


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ["id", "titre", "url", "description", "ordre"]


class RessourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ressource
        fields = ["id", "titre", "url", "ordre", "fichier"]


# --- Éléments imbriqués : écriture (id optionnel = upsert, voir plus haut) ---

class ExerciceEcritureSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Exercice
        fields = ["id", "enonce", "corrige", "difficulte", "ordre"]


class VideoEcritureSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Video
        fields = ["id", "titre", "url", "description", "ordre"]


class RessourceEcritureSerializer(serializers.ModelSerializer):
    """Ressources "url" uniquement : l'upload de fichier viendra plus tard
    (endpoint multipart dédié), donc `fichier` n'est pas exposé ici.

    `url` est rendu obligatoire ICI, au niveau du serializer d'écriture —
    le modèle la garde `blank=True` (Ressource pourra un jour n'avoir qu'un
    `fichier`), mais tant que seul le mode "url" est géré, une ressource sans
    url n'a aucun contenu utile.
    """

    id = serializers.IntegerField(required=False)
    url = serializers.URLField()

    class Meta:
        model = Ressource
        fields = ["id", "titre", "url", "ordre"]


# --- Lecon : liste (légère) ---

class LeconListeSerializer(serializers.ModelSerializer):
    notion = serializers.SerializerMethodField()
    chemin = serializers.SerializerMethodField()
    nb_exercices = serializers.SerializerMethodField()
    nb_videos = serializers.SerializerMethodField()

    class Meta:
        model = Lecon
        fields = [
            "id", "titre", "statut", "est_gratuit", "notion", "chemin",
            "nb_exercices", "nb_videos", "cree_le", "modifie_le",
        ]

    def get_notion(self, obj: Lecon) -> dict:
        return {"id": obj.notion_id, "titre": obj.notion.titre}

    def get_chemin(self, obj: Lecon) -> str:
        return construire_chemin(obj.notion)

    def get_nb_exercices(self, obj: Lecon) -> int:
        valeur = getattr(obj, "nb_exercices", None)
        return valeur if valeur is not None else obj.exercices.count()

    def get_nb_videos(self, obj: Lecon) -> int:
        valeur = getattr(obj, "nb_videos", None)
        return valeur if valeur is not None else obj.videos.count()


# --- Lecon : détail complet ---

class LeconDetailSerializer(serializers.ModelSerializer):
    notion = serializers.SerializerMethodField()
    prerequis_lecons = serializers.SerializerMethodField()
    exercices = ExerciceSerializer(many=True, read_only=True)
    videos = VideoSerializer(many=True, read_only=True)
    ressources = RessourceSerializer(many=True, read_only=True)

    class Meta:
        model = Lecon
        fields = [
            "id", "titre", "statut", "est_gratuit",
            "notion",
            "histoire",
            "objectifs_pedagogiques",
            "prerequis_texte", "prerequis_lecons",
            "cours_redige", "demonstrations", "a_retenir",
            "sujet_examen",
            "exercices", "videos", "ressources",
            "cree_le", "modifie_le",
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

    def get_prerequis_lecons(self, obj: Lecon) -> list:
        return [{"id": l.id, "titre": l.titre} for l in obj.prerequis_lecons.all()]


# --- Lecon : création / modification ---

class LeconEcritureSerializer(serializers.ModelSerializer):
    notion = serializers.PrimaryKeyRelatedField(queryset=Notion.objects.all())
    prerequis_lecons = serializers.PrimaryKeyRelatedField(
        queryset=Lecon.objects.all(), many=True, required=False
    )
    exercices = ExerciceEcritureSerializer(many=True, required=False)
    videos = VideoEcritureSerializer(many=True, required=False)
    ressources = RessourceEcritureSerializer(many=True, required=False)

    class Meta:
        model = Lecon
        fields = [
            "notion", "titre",
            "histoire",
            "objectifs_pedagogiques",
            "prerequis_texte", "prerequis_lecons",
            "cours_redige", "demonstrations", "a_retenir",
            "sujet_examen",
            "statut", "est_gratuit",
            "exercices", "videos", "ressources",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            # Une leçon ne change pas de notion après coup (relation 1↔1
            # posée à la création) : on l'expose en lecture seule à l'update
            # plutôt que de gérer un transfert vers une autre notion.
            self.fields["notion"].read_only = True

    def validate_notion(self, notion: Notion) -> Notion:
        if self.instance is None and hasattr(notion, "lecon"):
            raise serializers.ValidationError("Cette notion a déjà une leçon.")
        return notion

    def validate_prerequis_lecons(self, valeur):
        if self.instance is not None and self.instance in valeur:
            raise serializers.ValidationError("Une leçon ne peut pas être son propre prérequis.")
        return valeur

    def create(self, validated_data: dict) -> Lecon:
        exercices_data = validated_data.pop("exercices", [])
        videos_data = validated_data.pop("videos", [])
        ressources_data = validated_data.pop("ressources", [])
        prerequis_lecons = validated_data.pop("prerequis_lecons", [])

        with transaction.atomic():
            lecon = Lecon.objects.create(**validated_data)
            lecon.prerequis_lecons.set(prerequis_lecons)
            self._synchroniser(lecon.exercices, Exercice, exercices_data)
            self._synchroniser(lecon.videos, Video, videos_data)
            self._synchroniser(lecon.ressources, Ressource, ressources_data)
        return lecon

    def update(self, instance: Lecon, validated_data: dict) -> Lecon:
        exercices_data = validated_data.pop("exercices", None)
        videos_data = validated_data.pop("videos", None)
        ressources_data = validated_data.pop("ressources", None)
        prerequis_lecons = validated_data.pop("prerequis_lecons", None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if prerequis_lecons is not None:
                instance.prerequis_lecons.set(prerequis_lecons)
            if exercices_data is not None:
                self._synchroniser(instance.exercices, Exercice, exercices_data)
            if videos_data is not None:
                self._synchroniser(instance.videos, Video, videos_data)
            if ressources_data is not None:
                self._synchroniser(instance.ressources, Ressource, ressources_data)
        return instance

    @staticmethod
    def _synchroniser(related_manager, model, items_data: list) -> None:
        """Applique la convention upsert/suppression documentée en tête de fichier."""
        existants = {obj.id: obj for obj in related_manager.all()}
        ids_conserves = set()

        for item_data in items_data:
            item_data = dict(item_data)
            item_id = item_data.pop("id", None)
            if item_id is not None:
                obj = existants.get(item_id)
                if obj is None or item_id in ids_conserves:
                    raise serializers.ValidationError(
                        f"{model.__name__} : id {item_id} invalide ou dupliqué pour cette leçon."
                    )
                for attr, value in item_data.items():
                    setattr(obj, attr, value)
                obj.save()
                ids_conserves.add(item_id)
            else:
                model.objects.create(lecon=related_manager.instance, **item_data)

        a_supprimer = existants.keys() - ids_conserves
        if a_supprimer:
            model.objects.filter(id__in=a_supprimer).delete()
