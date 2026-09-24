"""
Import du programme officiel de Mathématiques — Terminale D (Niger),
en totalité (3 thèmes).

Usage :
    python manage.py importer_maths_td
    python manage.py importer_maths_td --maj   # met à jour les 3 colonnes
                                                # officielles des notions
                                                # déjà existantes

Comportement (même modèle que importer_physique_tc / importer_chimie_tc /
importer_svt_tc) :
  - Le programme Mathématiques × Terminale × D DOIT déjà exister en base :
    cette commande ne le crée jamais. Si introuvable, elle s'arrête avec un
    message clair.
  - Les thèmes sont retrouvés par leur ORDRE dans le programme (1 à 3), pas
    par leur titre — même robustesse que les commandes sœurs face à un
    éventuel écart de libellé.
  - Chapitres et notions : get_or_create sur le titre dans leur parent — une
    notion déjà existante n'est jamais dupliquée ni touchée, sauf --maj.
  - Idempotent : relancer la commande (avec ou sans --maj) ne crée jamais de
    doublon.

STRUCTURE MIXTE (différence avec physique/chimie/SVT, où 1 chapitre = 1
notion) : un chapitre du fichier de données porte SOIT une clé "notions"
(liste de plusieurs sous-notions, chacune avec son propre titre/contenus/
objectifs/commentaires, numérotées 1, 2, 3… dans cet ordre), SOIT
directement les clés contenus/objectifs/commentaires sur le chapitre lui-
même (une seule notion, dont le titre reprend celui du chapitre, ordre 1).
Voir _donnees_maths_tle_d.py pour le détail. Cette commande gère les deux
cas via _extraire_notions() ci-dessous.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programme.models import Programme, Theme, Chapitre, Notion

from ._donnees_maths_tle_d import MATHS_TLE_D


def _extraire_notions(chap: dict) -> list[dict]:
    """Renvoie la liste des notions d'un chapitre, quel que soit son format
    dans le fichier de données (voir la note de structure mixte ci-dessus).
    Chaque élément renvoyé a la forme {titre, contenus, objectifs,
    commentaires} — uniformisé, indépendamment du cas d'origine.
    """
    if "notions" in chap:
        return chap["notions"]
    return [{
        "titre": chap["titre"],
        "contenus": chap["contenus"],
        "objectifs": chap["objectifs"],
        "commentaires": chap["commentaires"],
    }]


class Command(BaseCommand):
    help = (
        "Importe le programme officiel de Mathématiques — Terminale D "
        "(3 thèmes : Organisation des calculs, Applications affines du "
        "plan, Organisation des données ; structure mixte, certains "
        "chapitres ont plusieurs notions)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--maj",
            action="store_true",
            help=(
                "Pour les notions déjà existantes, met à jour leurs 3 colonnes "
                "officielles (contenus/objectifs/commentaires) depuis le fichier "
                "de données. Sans cette option, une notion déjà existante n'est "
                "jamais modifiée."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            programme = Programme.objects.select_related(
                "matiere", "niveau", "serie"
            ).get(matiere__nom="Mathématiques", niveau__nom="Terminale", serie__nom="D")
        except Programme.DoesNotExist:
            raise CommandError(
                "Aucun programme Mathématiques × Terminale × D trouvé en base.\n"
                "Cette commande ne crée PAS la matière ni le programme : "
                "crée-le d'abord (ex. depuis /admin/programmes), puis relance "
                "cette commande."
            )

        self.stdout.write(f"Programme cible : {programme}")

        n_themes_crees = n_themes_reutilises = 0
        n_chap_crees = n_chap_existants = 0
        n_notions_creees = n_notions_maj = n_notions_ignorees = 0

        for i, bloc in enumerate(MATHS_TLE_D, start=1):
            theme, theme_cree = Theme.objects.get_or_create(
                programme=programme,
                ordre=i,
                defaults={"titre": bloc["theme"], "volume_horaire": bloc["volume_horaire"]},
            )
            if theme_cree:
                n_themes_crees += 1
                self.stdout.write(self.style.SUCCESS(f"  + Thème {i} créé : {theme.titre}"))
            else:
                n_themes_reutilises += 1
                self.stdout.write(f"  = Thème {i} déjà existant, réutilisé : {theme.titre}")
                if theme.titre != bloc["theme"]:
                    self.stdout.write(self.style.WARNING(
                        f"    (le titre en base « {theme.titre} » diffère de celui du "
                        f"fichier de données « {bloc['theme']} » — titre en base conservé "
                        f"tel quel, aucune modification.)"
                    ))

            for j, chap in enumerate(bloc["chapitres"], start=1):
                chapitre, chap_cree = Chapitre.objects.get_or_create(
                    theme=theme, titre=chap["titre"], defaults={"ordre": j}
                )
                if chap_cree:
                    n_chap_crees += 1
                else:
                    n_chap_existants += 1

                for k, notion_data in enumerate(_extraire_notions(chap), start=1):
                    notion, notion_cree = Notion.objects.get_or_create(
                        chapitre=chapitre,
                        titre=notion_data["titre"],
                        defaults={
                            "ordre": k,
                            "contenus_officiels": notion_data["contenus"],
                            "objectifs_officiels": notion_data["objectifs"],
                            "commentaires_officiels": notion_data["commentaires"],
                        },
                    )
                    if notion_cree:
                        n_notions_creees += 1
                    elif options["maj"]:
                        notion.contenus_officiels = notion_data["contenus"]
                        notion.objectifs_officiels = notion_data["objectifs"]
                        notion.commentaires_officiels = notion_data["commentaires"]
                        notion.save(update_fields=[
                            "contenus_officiels", "objectifs_officiels", "commentaires_officiels",
                        ])
                        n_notions_maj += 1
                    else:
                        n_notions_ignorees += 1

        self.stdout.write(self.style.SUCCESS(
            "\nImport terminé.\n"
            f"  Thèmes   : {n_themes_crees} créés, {n_themes_reutilises} déjà existants.\n"
            f"  Chapitres: {n_chap_crees} créés, {n_chap_existants} déjà existants.\n"
            f"  Notions  : {n_notions_creees} créées, {n_notions_maj} mises à jour (--maj), "
            f"{n_notions_ignorees} déjà existantes et inchangées."
        ))
