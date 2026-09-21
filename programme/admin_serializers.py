"""
Serializers admin pour la structure scolaire (Cycle, Niveau, Serie, Matiere).

Chaque ressource a un serializer de LECTURE (avec objets imbriqués lisibles
et compteurs d'utilisation) et un serializer d'ÉCRITURE (champs FK en id
bruts). Les compteurs lisent d'abord une éventuelle annotation de queryset
(nb_*), posée par les ViewSets pour éviter le N+1 sur les listes ; à défaut
(ex. objet tout juste créé), ils retombent sur un count() direct — un seul
objet à ce moment-là, donc sans risque de N+1.
"""

from rest_framework import serializers

from .models import Cycle, Matiere, Niveau, Serie


class CycleReadSerializer(serializers.ModelSerializer):
    nb_niveaux = serializers.SerializerMethodField()

    class Meta:
        model = Cycle
        fields = ["id", "nom", "ordre", "nb_niveaux"]

    def get_nb_niveaux(self, obj: Cycle) -> int:
        valeur = getattr(obj, "nb_niveaux", None)
        return valeur if valeur is not None else obj.niveaux.count()


class CycleWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cycle
        fields = ["id", "nom", "ordre"]


class NiveauReadSerializer(serializers.ModelSerializer):
    cycle = serializers.SerializerMethodField()
    nb_series = serializers.SerializerMethodField()
    nb_programmes = serializers.SerializerMethodField()
    nb_eleves = serializers.SerializerMethodField()

    class Meta:
        model = Niveau
        fields = ["id", "nom", "ordre", "cycle", "nb_series", "nb_programmes", "nb_eleves"]

    def get_cycle(self, obj: Niveau) -> dict:
        return {"id": obj.cycle_id, "nom": obj.cycle.nom}

    def get_nb_series(self, obj: Niveau) -> int:
        valeur = getattr(obj, "nb_series", None)
        return valeur if valeur is not None else obj.series.count()

    def get_nb_programmes(self, obj: Niveau) -> int:
        valeur = getattr(obj, "nb_programmes", None)
        return valeur if valeur is not None else obj.programmes.count()

    def get_nb_eleves(self, obj: Niveau) -> int:
        valeur = getattr(obj, "nb_eleves", None)
        return valeur if valeur is not None else obj.eleves.count()


class NiveauWriteSerializer(serializers.ModelSerializer):
    cycle = serializers.PrimaryKeyRelatedField(queryset=Cycle.objects.all())

    class Meta:
        model = Niveau
        fields = ["id", "cycle", "nom", "ordre"]


class SerieReadSerializer(serializers.ModelSerializer):
    niveau = serializers.SerializerMethodField()
    nb_programmes = serializers.SerializerMethodField()
    nb_eleves = serializers.SerializerMethodField()

    class Meta:
        model = Serie
        fields = ["id", "nom", "niveau", "nb_programmes", "nb_eleves"]

    def get_niveau(self, obj: Serie) -> dict:
        return {"id": obj.niveau_id, "nom": obj.niveau.nom}

    def get_nb_programmes(self, obj: Serie) -> int:
        valeur = getattr(obj, "nb_programmes", None)
        return valeur if valeur is not None else obj.programmes.count()

    def get_nb_eleves(self, obj: Serie) -> int:
        valeur = getattr(obj, "nb_eleves", None)
        return valeur if valeur is not None else obj.eleves.count()


class SerieWriteSerializer(serializers.ModelSerializer):
    niveau = serializers.PrimaryKeyRelatedField(queryset=Niveau.objects.all())

    class Meta:
        model = Serie
        fields = ["id", "niveau", "nom"]


class MatiereReadSerializer(serializers.ModelSerializer):
    nb_programmes = serializers.SerializerMethodField()

    class Meta:
        model = Matiere
        fields = ["id", "nom", "nb_programmes"]

    def get_nb_programmes(self, obj: Matiere) -> int:
        valeur = getattr(obj, "nb_programmes", None)
        return valeur if valeur is not None else obj.programmes.count()


class MatiereWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Matiere
        fields = ["id", "nom"]
