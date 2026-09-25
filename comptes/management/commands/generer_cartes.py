"""
Génère un lot de cartes Fahimta prépayées.

Usage :
    python manage.py generer_cartes --quantite 5 --duree-jours 30
    python manage.py generer_cartes --quantite 100 --duree-jours 30 --lot "rentree-2026"

Sans --lot, un identifiant de lot est dérivé de l'horodatage
("lot-20260925-113000"). Affiche les codes générés en sortie — pour un export
destiné à l'impression/distribution, voir plutôt l'action CSV de l'admin
Django (CarteFahimtaAdmin, filtrable par lot).
"""

from django.core.management.base import BaseCommand

from comptes.cartes import generer_lot


class Command(BaseCommand):
    help = "Génère un lot de cartes Fahimta prépayées (codes uniques, non utilisées)."

    def add_arguments(self, parser):
        parser.add_argument("--quantite", type=int, required=True, help="Nombre de cartes à créer.")
        parser.add_argument(
            "--duree-jours", type=int, default=30, dest="duree_jours",
            help="Jours d'abonnement crédités par carte à l'activation (défaut : 30).",
        )
        parser.add_argument(
            "--lot", type=str, default=None,
            help="Identifiant du lot (défaut : dérivé de la date/heure).",
        )

    def handle(self, *args, **options):
        quantite = options["quantite"]
        duree_jours = options["duree_jours"]

        if quantite <= 0:
            self.stderr.write(self.style.ERROR("--quantite doit être un entier positif."))
            return
        if duree_jours <= 0:
            self.stderr.write(self.style.ERROR("--duree-jours doit être un entier positif."))
            return

        # generer_lot() : MÊME fonction que l'endpoint admin du back-office
        # custom (POST /api/admin/cartes/generer/) — la génération ne vit
        # qu'à un seul endroit (voir comptes/cartes.py).
        cartes = generer_lot(quantite=quantite, duree_jours=duree_jours, lot=options["lot"])

        self.stdout.write(self.style.SUCCESS(
            f"\n{quantite} carte(s) créée(s) — lot \"{cartes[0].lot}\", {duree_jours} jour(s) chacune.\n"
        ))
        for carte in cartes:
            self.stdout.write(f"  {carte.code}")
