"""
Validation d'un exercice déposé par un élève (« Résoudre mon exercice »).

ÉTAPE 3 : validation SEULE. Rien n'est enregistré, rien n'est transmis à une
IA. Les règles reprennent celles de l'interface (lib/resoudre.ts côté front),
mais ne leur font JAMAIS confiance : le type réel d'un fichier est lu dans ses
premiers octets (signature), pas dans son nom ni dans le Content-Type envoyé
par le client.
"""

import unicodedata

from rest_framework import serializers

NB_MAX_IMAGES = 6
TAILLE_MAX_FICHIER_OCTETS = 10 * 1024 * 1024  # 10 Mo, par image ou PDF
TAILLE_MAX_TOTALE_OCTETS = 20 * 1024 * 1024  # 20 Mo pour l'ensemble de l'exercice
LONGUEUR_MAX_CORRECTION = 1000
LONGUEUR_MAX_ENONCE = 4000

MODE_CORRECTION = "correction"
MODE_PROFESSEUR = "professeur"
MODES = (MODE_CORRECTION, MODE_PROFESSEUR)

TYPE_JPEG = "image/jpeg"
TYPE_PNG = "image/png"
TYPE_WEBP = "image/webp"
TYPE_PDF = "application/pdf"
TYPES_IMAGE = (TYPE_JPEG, TYPE_PNG, TYPE_WEBP)

_LONGUEUR_ENTETE = 16


def detecter_type_reel(entete: bytes) -> str | None:
    """Type d'un fichier d'après sa signature, ou None si non reconnu."""
    if entete.startswith(b"\xff\xd8\xff"):
        return TYPE_JPEG
    if entete.startswith(b"\x89PNG\r\n\x1a\n"):
        return TYPE_PNG
    if entete[:4] == b"RIFF" and entete[8:12] == b"WEBP":
        return TYPE_WEBP
    if entete.startswith(b"%PDF-"):
        return TYPE_PDF
    return None


def formater_taille(octets: int) -> str:
    if octets < 1024 * 1024:
        return f"{max(1, round(octets / 1024))} Ko"
    return f"{octets / (1024 * 1024):.1f}".replace(".", ",") + " Mo"


def _nom_affichable(fichier) -> str:
    """Nom du fichier tel que renvoyé dans les messages : sans caractères de
    contrôle, tronqué (c'est une donnée fournie par le client)."""
    nom = "".join(c for c in (getattr(fichier, "name", "") or "") if c.isprintable())
    nom = nom.strip() or "fichier"
    return nom if len(nom) <= 80 else nom[:77] + "…"


def _decrire(fichier) -> dict:
    """Nom, taille et type RÉEL (None si non reconnu) d'un fichier téléversé."""
    fichier.seek(0)
    entete = fichier.read(_LONGUEUR_ENTETE)
    fichier.seek(0)
    return {"nom": _nom_affichable(fichier), "type": detecter_type_reel(entete), "taille": fichier.size}


def matiere_resolvable(nom_matiere: str) -> bool:
    """Mathématiques, Physique, Chimie, SVT (mêmes règles de reconnaissance
    que matiereResolvable dans lib/resoudre.ts, accents et casse ignorés)."""
    nom = unicodedata.normalize("NFD", nom_matiere or "")
    nom = "".join(c for c in nom if not unicodedata.combining(c)).strip().lower()
    return bool(
        nom.startswith(("math", "phys", "chim"))
        or nom == "svt"
        or nom.startswith("sciences de la vie")
    )


class DepotExerciceSerializer(serializers.Serializer):
    """Corps multipart de POST /api/eleve/resoudre/.

    Champs : `programme` (id), `mode`, `enonce` (optionnel, 4000 car. max) et
    `fichiers` (clé répétée : jusqu'à 6 images, OU un seul PDF). Il faut au
    moins un fichier ou un énoncé. `validated_data["fichiers_valides"]` donne,
    pour chaque fichier accepté, son nom, son type RÉEL et sa taille.
    """

    programme = serializers.IntegerField(
        error_messages={
            "required": "Indique le programme (la matière) de l'exercice.",
            "invalid": "Programme invalide.",
        }
    )
    mode = serializers.ChoiceField(
        choices=MODES,
        error_messages={
            "required": "Choisis un mode : correction complète ou professeur particulier.",
            "invalid_choice": "Mode inconnu : choisis la correction complète ou le professeur particulier.",
        },
    )
    enonce = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=LONGUEUR_MAX_ENONCE,
        error_messages={
            "max_length": f"L'énoncé ne doit pas dépasser {LONGUEUR_MAX_ENONCE} caractères.",
        },
    )
    analyser = serializers.BooleanField(required=False, default=False)
    correction = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=LONGUEUR_MAX_CORRECTION,
        error_messages={
            "max_length": f"Ta remarque ne doit pas dépasser {LONGUEUR_MAX_CORRECTION} caractères.",
        },
    )
    fichiers = serializers.ListField(
        child=serializers.FileField(allow_empty_file=True, use_url=False),
        required=False,
        allow_empty=True,
    )

    def validate_fichiers(self, fichiers):
        if len(fichiers) > NB_MAX_IMAGES:
            raise serializers.ValidationError(
                f"{NB_MAX_IMAGES} fichiers maximum par exercice ({len(fichiers)} reçus)."
            )

        erreurs: list[str] = []
        valides: list[dict] = []

        for fichier in fichiers:
            infos = _decrire(fichier)
            nom = infos["nom"]

            if infos["taille"] == 0:
                erreurs.append(f"« {nom} » est vide.")
            elif infos["taille"] > TAILLE_MAX_FICHIER_OCTETS:
                erreurs.append(
                    f"« {nom} » est trop volumineux ({formater_taille(infos['taille'])}) : 10 Mo maximum."
                )
            elif infos["type"] is None:
                erreurs.append(
                    f"« {nom} » n'est pas accepté : envoie des images JPG, PNG ou WebP, ou un PDF."
                )
            else:
                valides.append(infos)

        if erreurs:
            raise serializers.ValidationError(erreurs)

        nb_pdf = sum(1 for f in valides if f["type"] == TYPE_PDF)
        nb_images = len(valides) - nb_pdf

        total = sum(f["taille"] for f in valides)
        if total > TAILLE_MAX_TOTALE_OCTETS:
            raise serializers.ValidationError(
                f"L'exercice est trop volumineux ({formater_taille(total)} au total) : 20 Mo maximum "
                "pour l'ensemble des fichiers."
            )

        if nb_pdf and nb_images:
            raise serializers.ValidationError(
                "Un PDF ne peut pas être envoyé avec des images : choisis soit des images, soit un PDF."
            )
        if nb_pdf > 1:
            raise serializers.ValidationError("Un seul PDF par exercice.")

        return fichiers

    def validate(self, attrs):
        fichiers = attrs.get("fichiers") or []
        enonce = (attrs.get("enonce") or "").strip()

        if not fichiers and not enonce:
            raise serializers.ValidationError(
                "Ajoute une photo, un fichier, ou saisis l'énoncé de ton exercice."
            )

        attrs["enonce"] = enonce
        attrs["correction"] = (attrs.get("correction") or "").strip()
        attrs["fichiers_valides"] = [_decrire(f) for f in fichiers]
        return attrs

