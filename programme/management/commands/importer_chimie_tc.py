"""
Import du programme officiel de Chimie — Terminale C (Niger), en totalité
(3 thèmes, contrairement à la physique où le Thème 1 Mécanique était déjà
saisi à la main — ici rien n'existe encore, le programme est vide).

Usage :
    python manage.py importer_chimie_tc
    python manage.py importer_chimie_tc --maj   # met à jour les 3 colonnes
                                                  # officielles des notions
                                                  # déjà existantes

Comportement (même modèle que importer_physique_tc) :
  - Le programme Chimie × Terminale × C DOIT déjà exister en base (matière
    "Chimie", niveau "Terminale", série "C") : cette commande ne le crée
    jamais. S'il est introuvable, elle s'arrête avec un message clair.
  - Les thèmes sont retrouvés par leur ORDRE dans le programme (1, 2, 3),
    pas par leur titre — même robustesse que importer_physique_tc face à un
    éventuel écart de libellé entre la base et le fichier de données, même si
    aucun thème n'existe encore ici pour le moment.
  - Chapitres et notions : get_or_create sur le titre dans leur parent — une
    notion déjà existante n'est jamais dupliquée ni touchée, sauf --maj (qui
    ne met à jour que les 3 colonnes officielles, jamais le titre/l'ordre).
  - Idempotent : relancer la commande (avec ou sans --maj) ne crée jamais de
    doublon.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programme.models import Programme, Theme, Chapitre, Notion

from ._donnees_chimie_tle_c import CHIMIE_TLE_C

# Contrairement à la physique (Thème 1 Mécanique déjà en place, import à
# partir de l'ordre 2), la chimie est vide : le premier thème du fichier de
# données prend l'ordre 1.
ORDRE_PREMIER_THEME = 1


class Command(BaseCommand):
    help = (
        "Importe le programme officiel de Chimie — Terminale C "
        "(3 thèmes : Chimie générale (Acides et Bases en solution aqueuse), "
        "Chimie organique, Cinétique chimique)."
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
            ).get(matiere__nom="Chimie", niveau__nom="Terminale", serie__nom="C")
        except Programme.DoesNotExist:
            raise CommandError(
                "Aucun programme Chimie × Terminale × C trouvé en base.\n"
                "Cette commande ne crée PAS la matière ni le programme : "
                "crée-le d'abord (ex. depuis /admin/programmes), puis relance "
                "cette commande."
            )

        self.stdout.write(f"Programme cible : {programme}")

        n_themes_crees = n_themes_reutilises = 0
        n_chap_crees = n_chap_existants = 0
        n_notions_creees = n_notions_maj = n_notions_ignorees = 0

        for i, bloc in enumerate(CHIMIE_TLE_C, start=ORDRE_PREMIER_THEME):
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

                # En chimie, 1 chapitre = 1 notion : le titre de la notion
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
