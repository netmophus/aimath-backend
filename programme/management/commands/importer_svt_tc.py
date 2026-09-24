"""
Import du programme officiel de SVT (Sciences de la Vie et de la Terre) —
Terminale C (Niger), en totalité (5 thèmes).

Usage :
    python manage.py importer_svt_tc
    python manage.py importer_svt_tc --maj   # met à jour les 3 colonnes
                                              # officielles des notions
                                              # déjà existantes

Comportement (même modèle que importer_physique_tc / importer_chimie_tc) :
  - Le programme SVT × Terminale × C DOIT déjà exister en base : cette
    commande ne le crée jamais. Le nom de la matière n'étant pas garanti
    ("SVT" ou "Sciences de la Vie et de la Terre" selon comment elle a été
    saisie), les DEUX sont essayés. Si aucun des deux ne donne de programme,
    la commande s'arrête avec un message clair.
  - Les thèmes sont retrouvés par leur ORDRE dans le programme (1 à 5), pas
    par leur titre — même robustesse que les deux commandes sœurs face à un
    éventuel écart de libellé.
  - Chapitres et notions : get_or_create sur le titre dans leur parent — une
    notion déjà existante n'est jamais dupliquée ni touchée, sauf --maj (qui
    ne met à jour que les 3 colonnes officielles, jamais le titre/l'ordre).
  - Idempotent : relancer la commande (avec ou sans --maj) ne crée jamais de
    doublon.

ATTENTION AU DÉCOMPTE : le fichier de données source (DONNEES_import_
svt_tleC.py) affirme dans son commentaire "8 chapitres (= 8 notions)", mais
son contenu réel, vérifié programmatiquement, en contient 10 (3+2+3+1+1
selon les 5 thèmes). Le contenu n'a pas été modifié (consigne explicite) —
c'est bien 10 notions qui seront créées, pas 8.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programme.models import Programme, Theme, Chapitre, Notion

from ._donnees_svt_tle_c import SVT_TLE_C

NOMS_MATIERE_POSSIBLES = ["SVT", "Sciences de la Vie et de la Terre"]


class Command(BaseCommand):
    help = (
        "Importe le programme officiel de SVT — Terminale C "
        "(5 thèmes : processus géologiques, ressources géologiques, "
        "appareils génitaux, régulation des naissances, communication "
        "humorale)."
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

    def _trouver_programme(self):
        for nom_matiere in NOMS_MATIERE_POSSIBLES:
            try:
                return Programme.objects.select_related("matiere", "niveau", "serie").get(
                    matiere__nom=nom_matiere, niveau__nom="Terminale", serie__nom="C"
                )
            except Programme.DoesNotExist:
                continue
        raise CommandError(
            "Aucun programme SVT × Terminale × C trouvé en base (essayé avec "
            f"matière = {NOMS_MATIERE_POSSIBLES!r}).\n"
            "Cette commande ne crée PAS la matière ni le programme : "
            "crée-le d'abord (ex. depuis /admin/programmes), puis relance "
            "cette commande."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        programme = self._trouver_programme()
        self.stdout.write(f"Programme cible : {programme} (matière : {programme.matiere.nom!r})")

        n_themes_crees = n_themes_reutilises = 0
        n_chap_crees = n_chap_existants = 0
        n_notions_creees = n_notions_maj = n_notions_ignorees = 0

        for i, bloc in enumerate(SVT_TLE_C, start=1):
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

                # En SVT, 1 chapitre = 1 notion : le titre de la notion
                # reprend celui du chapitre (pas de sous-notions).
                notion, notion_cree = Notion.objects.get_or_create(
                    chapitre=chapitre,
                    titre=chap["titre"],
                    defaults={
                        "ordre": 1,
                        "contenus_officiels": chap["contenus"],
                        "objectifs_officiels": chap["objectifs"],
                        "commentaires_officiels": chap["commentaires"],
                    },
                )
                if notion_cree:
                    n_notions_creees += 1
                elif options["maj"]:
                    notion.contenus_officiels = chap["contenus"]
                    notion.objectifs_officiels = chap["objectifs"]
                    notion.commentaires_officiels = chap["commentaires"]
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
