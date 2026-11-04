from rest_framework import serializers

from programme.models import Lecon, Programme

from . import fichiers
from .models import DemandeAide

MESSAGE_MAX = 1000


class CreerDemandeSerializer(serializers.Serializer):
    cle = serializers.CharField(min_length=8, max_length=64)
    type = serializers.ChoiceField(choices=DemandeAide.Type.choices)
    programme = serializers.IntegerField(required=False, allow_null=True)
    lecon = serializers.IntegerField(required=False, allow_null=True)
    message = serializers.CharField(max_length=MESSAGE_MAX, trim_whitespace=True)
    piece_jointe = serializers.FileField(required=False, allow_null=True)

    def validate_message(self, valeur):
        valeur = valeur.strip()
        if not valeur:
            raise serializers.ValidationError("Écris ton message.")
        return valeur

    def validate(self, data):
        eleve = self.context["request"].user
        programme = lecon = None
        if data.get("programme") is not None:
            # Seuls les programmes de SA classe : un id d'une autre classe est refusé comme inexistant.
            programme = Programme.objects.filter(
                pk=data["programme"], niveau_id=eleve.niveau_id, serie_id=eleve.serie_id
            ).first()
            if programme is None:
                raise serializers.ValidationError({"programme": "Matière introuvable."})
        if data.get("lecon") is not None:
            if programme is None:
                raise serializers.ValidationError({"lecon": "Choisis d'abord une matière."})
            lecon = Lecon.objects.filter(
                pk=data["lecon"], statut=Lecon.Statut.PUBLIE, notion__chapitre__theme__programme=programme
            ).first()
            if lecon is None:
                raise serializers.ValidationError({"lecon": "Leçon introuvable pour cette matière."})
        data["programme_obj"], data["lecon_obj"] = programme, lecon
        fichier = data.pop("piece_jointe", None)
        if fichier:
            try:
                data["octets"], data["type_fichier"] = fichiers.controler(fichier)
            except ValueError as e:
                raise serializers.ValidationError({"piece_jointe": str(e)})
        return data


def _ref(obj, nom):
    return {"id": obj.id, "nom": nom} if obj else None


class DemandeSerializer(serializers.ModelSerializer):
    """Vue ÉLÈVE : jamais le nom de l'administrateur qui a répondu."""

    matiere = serializers.SerializerMethodField()
    lecon = serializers.SerializerMethodField()
    a_piece_jointe = serializers.BooleanField(read_only=True)
    a_reponse = serializers.SerializerMethodField()

    class Meta:
        model = DemandeAide
        fields = ["id", "type", "matiere", "lecon", "message", "a_piece_jointe", "statut", "a_reponse", "reponse",
                  "reponse_le", "cree_le", "traitee_le"]

    def get_matiere(self, o):
        return _ref(o.programme, o.programme.matiere.nom) if o.programme else None

    def get_lecon(self, o):
        return _ref(o.lecon, o.lecon.titre) if o.lecon else None

    def get_a_reponse(self, o):
        return bool(o.reponse.strip())


class DemandeAdminSerializer(DemandeSerializer):
    eleve = serializers.SerializerMethodField()

    class Meta(DemandeSerializer.Meta):
        fields = DemandeSerializer.Meta.fields + ["eleve", "mis_a_jour_le"]

    def get_eleve(self, o):
        e = o.eleve
        classe = " ".join(p for p in (e.niveau.nom if e.niveau else "", e.serie.nom if e.serie else "") if p)
        return {"id": e.id, "nom": f"{e.prenom} {e.nom}".strip(), "telephone": e.telephone, "classe": classe}


class TraiterDemandeSerializer(serializers.Serializer):
    statut = serializers.ChoiceField(choices=DemandeAide.Statut.choices, required=False)
    reponse = serializers.CharField(required=False, allow_blank=True, max_length=5000)
