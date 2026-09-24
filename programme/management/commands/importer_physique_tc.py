"""
Import du programme officiel de Physique — Terminale C (Niger),
thèmes 2 à 5 uniquement (hors Mécanique, déjà saisie à la main ; hors Chimie,
hors périmètre).

Usage :
    python manage.py importer_physique_tc
    python manage.py importer_physique_tc --maj   # met à jour les 3 colonnes
                                                    # officielles des notions
                                                    # déjà existantes

Comportement :
  - Le programme Physique × Terminale × C DOIT déjà exister en base (matière
    "Physique", niveau "Terminale", série "C") : cette commande ne le crée
    jamais. S'il est introuvable, elle s'arrête avec un message clair.
  - Le Thème 1 "Mécanique" n'est ni recréé ni touché : il n'apparaît nulle
    part dans les données importées ici.
  - Les thèmes sont retrouvés par leur ORDRE dans le programme (2, 3, 4, 5 —
    à la suite du Thème 1 Mécanique), PAS par leur titre : le titre déjà en
    base pour l'ordre 3 est "Électromagnétisme" (avec accent) alors que le
    fichier de données écrit "Electromagnétisme" (sans accent) — matcher par
    titre aurait donc créé un doublon. Si le thème n'existe pas encore pour
    cet ordre, il est créé avec le titre du fichier de données.
  - Chapitres et notions : get_or_create sur le titre dans leur parent — une
    notion déjà existante n'est jamais dupliquée ni touchée, sauf --maj (qui
    ne met à jour que les 3 colonnes officielles, jamais le titre/l'ordre).
  - Idempotent : relancer la commande (avec ou sans --maj) ne crée jamais de
    doublon.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programme.models import Programme, Theme, Chapitre, Notion

from ._donnees_physique_tle_c import PHYSIQUE_TLE_C

# Ordre du premier thème importé ici : le Thème 1 (Mécanique) occupe déjà
# l'ordre 1 en base, donc "Vibration et propagation" (1er thème du fichier de
# données) commence à l'ordre 2, et ainsi de suite jusqu'à 5.
ORDRE_PREMIER_THEME = 2


class Command(BaseCommand):
    help = (
        "Importe le programme officiel de Physique — Terminale C "
        "(thèmes 2 à 5 : Vibration et propagation, Électromagnétisme, "
        "Oscillations électriques, Phénomènes corpusculaires). "
        "Le Thème 1 Mécanique n'est pas touché."
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
            ).get(matiere__nom="Physique", niveau__nom="Terminale", serie__nom="C")
        except Programme.DoesNotExist:
            raise CommandError(
                "Aucun programme Physique × Terminale × C trouvé en base.\n"
                "Cette commande ne crée PAS la matière ni le programme : "
                "crée-le d'abord (ex. depuis /admin/programmes), puis relance "
                "cette commande."
            )

        self.stdout.write(f"Programme cible : {programme}")

        n_themes_crees = n_themes_reutilises = 0
        n_chap_crees = n_chap_existants = 0
        n_notions_creees = n_notions_maj = n_notions_ignorees = 0

        for i, bloc in enumerate(PHYSIQUE_TLE_C, start=ORDRE_PREMIER_THEME):
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

                # En physique, 1 chapitre = 1 notion : le titre de la notion
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
