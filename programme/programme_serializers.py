"""
Serializers admin pour la hiérarchie du programme officiel :
Programme → Theme → Chapitre → Notion. Le contenu rédigé (Lecon) n'est
jamais modifié ici — seulement compté/vérifié pour les garde-fous de
suppression (voir programme_views.py).

Même convention que admin_serializers.py (structure scolaire) : serializer
de LECTURE (compteurs via annotation, repli sur count() direct si absente)
séparé du serializer d'ÉCRITURE (FK en id bruts).
"""

from rest_framework import serializers

from .models import Chapitre, Lecon, Matiere, Niveau, Notion, Programme, Serie, Theme


def construire_libelle(programme: Programme) -> str:
    """Ex: "Mathématiques — Terminale C" (ou juste le niveau si pas de série)."""
    classe = f"{programme.niveau.nom} {programme.serie.nom}" if programme.serie_id else programme.niveau.nom
    return f"{programme.matiere.nom} — {classe}"


# --- Notion ---

class NotionReadSerializer(serializers.ModelSerializer):
    a_lecon = serializers.SerializerMethodField()

    class Meta:
        model = Notion
        fields = [
            "id", "titre", "ordre", "chapitre",
            "contenus_officiels", "objectifs_officiels", "commentaires_officiels",
            "a_lecon",
        ]

    def get_a_lecon(self, obj: Notion) -> bool:
        valeur = getattr(obj, "a_lecon", None)
        return bool(valeur) if valeur is not None else hasattr(obj, "lecon")


class NotionWriteSerializer(serializers.ModelSerializer):
    chapitre = serializers.PrimaryKeyRelatedField(queryset=Chapitre.objects.all())

    class Meta:
        model = Notion
        fields = [
            "id", "chapitre", "titre", "ordre",
            "contenus_officiels", "objectifs_officiels", "commentaires_officiels",
        ]


# --- Chapitre ---

class ChapitreReadSerializer(serializers.ModelSerializer):
    nb_notions = serializers.SerializerMethodField()

    class Meta:
        model = Chapitre
        fields = ["id", "titre", "ordre", "theme", "nb_notions"]

    def get_nb_notions(self, obj: Chapitre) -> int:
        valeur = getattr(obj, "nb_notions", None)
        return valeur if valeur is not None else obj.notions.count()


class ChapitreWriteSerializer(serializers.ModelSerializer):
    theme = serializers.PrimaryKeyRelatedField(queryset=Theme.objects.all())

    class Meta:
        model = Chapitre
        fields = ["id", "theme", "titre", "ordre"]


# --- Theme ---

class ThemeReadSerializer(serializers.ModelSerializer):
    nb_chapitres = serializers.SerializerMethodField()
    nb_notions = serializers.SerializerMethodField()

    class Meta:
        model = Theme
        fields = ["id", "titre", "volume_horaire", "ordre", "programme", "nb_chapitres", "nb_notions"]

    def get_nb_chapitres(self, obj: Theme) -> int:
        valeur = getattr(obj, "nb_chapitres", None)
        return valeur if valeur is not None else obj.chapitres.count()

    def get_nb_notions(self, obj: Theme) -> int:
        valeur = getattr(obj, "nb_notions", None)
        return valeur if valeur is not None else Notion.objects.filter(chapitre__theme=obj).count()


class ThemeWriteSerializer(serializers.ModelSerializer):
    programme = serializers.PrimaryKeyRelatedField(queryset=Programme.objects.all())

    class Meta:
        model = Theme
        fields = ["id", "programme", "titre", "volume_horaire", "ordre"]


# --- Programme (liste / création / modification) ---

class ProgrammeReadSerializer(serializers.ModelSerializer):
    matiere = serializers.SerializerMethodField()
    niveau = serializers.SerializerMethodField()
    serie = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
    nb_themes = serializers.SerializerMethodField()
    nb_chapitres = serializers.SerializerMethodField()
    nb_notions = serializers.SerializerMethodField()
    nb_lecons = serializers.SerializerMethodField()

    class Meta:
        model = Programme
        fields = [
            "id", "matiere", "niveau", "serie", "libelle",
            "nb_themes", "nb_chapitres", "nb_notions", "nb_lecons",
        ]

    def get_matiere(self, obj: Programme) -> dict:
        return {"id": obj.matiere_id, "nom": obj.matiere.nom}

    def get_niveau(self, obj: Programme) -> dict:
        return {"id": obj.niveau_id, "nom": obj.niveau.nom}

    def get_serie(self, obj: Programme) -> dict | None:
        return {"id": obj.serie_id, "nom": obj.serie.nom} if obj.serie_id else None

    def get_libelle(self, obj: Programme) -> str:
        return construire_libelle(obj)

    def get_nb_themes(self, obj: Programme) -> int:
        valeur = getattr(obj, "nb_themes", None)
        return valeur if valeur is not None else obj.themes.count()

    def get_nb_chapitres(self, obj: Programme) -> int:
        valeur = getattr(obj, "nb_chapitres", None)
        return valeur if valeur is not None else Chapitre.objects.filter(theme__programme=obj).count()

    def get_nb_notions(self, obj: Programme) -> int:
        valeur = getattr(obj, "nb_notions", None)
        return valeur if valeur is not None else Notion.objects.filter(chapitre__theme__programme=obj).count()

    def get_nb_lecons(self, obj: Programme) -> int:
        valeur = getattr(obj, "nb_lecons", None)
        if valeur is not None:
            return valeur
        return Lecon.objects.filter(notion__chapitre__theme__programme=obj).count()


class ProgrammeWriteSerializer(serializers.ModelSerializer):
    matiere = serializers.PrimaryKeyRelatedField(queryset=Matiere.objects.all())
    niveau = serializers.PrimaryKeyRelatedField(queryset=Niveau.objects.all())
    serie = serializers.PrimaryKeyRelatedField(
        queryset=Serie.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Programme
        fields = ["id", "matiere", "niveau", "serie"]

    def validate(self, attrs):
        niveau = attrs.get("niveau") or (self.instance.niveau if self.instance else None)
        serie = attrs["serie"] if "serie" in attrs else (self.instance.serie if self.instance else None)

        if serie is not None and niveau is not None and serie.niveau_id != niveau.id:
            raise serializers.ValidationError(
                {"serie": "Cette série n'appartient pas au niveau choisi."}
            )
        return attrs


# --- Arbre imbriqué complet (GET /api/admin/programmes/{id}/) ---

class NotionArbreSerializer(serializers.ModelSerializer):
    a_lecon = serializers.SerializerMethodField()

    class Meta:
        model = Notion
        fields = [
            "id", "titre", "ordre",
            "contenus_officiels", "objectifs_officiels", "commentaires_officiels",
            "a_lecon",
        ]

    def get_a_lecon(self, obj: Notion) -> bool:
        return hasattr(obj, "lecon")


class ChapitreArbreSerializer(serializers.ModelSerializer):
    notions = NotionArbreSerializer(many=True, read_only=True)

    class Meta:
        model = Chapitre
        fields = ["id", "titre", "ordre", "notions"]


class ThemeArbreSerializer(serializers.ModelSerializer):
    chapitres = ChapitreArbreSerializer(many=True, read_only=True)

    class Meta:
        model = Theme
        fields = ["id", "titre", "volume_horaire", "ordre", "chapitres"]


class ProgrammeDetailSerializer(serializers.ModelSerializer):
    """GET détail : renvoie l'arbre complet (themes → chapitres → notions)."""

    matiere = serializers.SerializerMethodField()
    niveau = serializers.SerializerMethodField()
    serie = serializers.SerializerMethodField()
    libelle = serializers.SerializerMethodField()
    themes = ThemeArbreSerializer(many=True, read_only=True)

    class Meta:
        model = Programme
        fields = ["id", "matiere", "niveau", "serie", "libelle", "themes"]

    def get_matiere(self, obj: Programme) -> dict:
        return {"id": obj.matiere_id, "nom": obj.matiere.nom}

    def get_niveau(self, obj: Programme) -> dict:
        return {"id": obj.niveau_id, "nom": obj.niveau.nom}

    def get_serie(self, obj: Programme) -> dict | None:
        return {"id": obj.serie_id, "nom": obj.serie.nom} if obj.serie_id else None

    def get_libelle(self, obj: Programme) -> str:
        return construire_libelle(obj)
