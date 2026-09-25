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
from django.utils import timezone

from comptes.cartes import generer_code_unique
from comptes.models import CarteFahimta


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
        lot = options["lot"] or f"lot-{timezone.now():%Y%m%d-%H%M%S}"

        if quantite <= 0:
            self.stderr.write(self.style.ERROR("--quantite doit être un entier positif."))
            return
        if duree_jours <= 0:
            self.stderr.write(self.style.ERROR("--duree-jours doit être un entier positif."))
            return

        # Exclusion locale en plus de la vérification en base (voir
        # generer_code_unique) : évite qu'un même code candidat, généré deux
        # fois dans CE lot avant que le premier soit écrit en base, ne passe
        # les deux la vérification d'existence (toujours "pas encore en
        # base" au moment du 2e check) — quasi impossible vu l'espace de
        # codes, mais gratuit à garantir ici.
        codes_du_lot: set[str] = set()
        cartes = []
        for _ in range(quantite):
            code = generer_code_unique(exclure=codes_du_lot)
            codes_du_lot.add(code)
            cartes.append(CarteFahimta(code=code, duree_jours=duree_jours, lot=lot))

        CarteFahimta.objects.bulk_create(cartes)

        self.stdout.write(self.style.SUCCESS(
            f"\n{quantite} carte(s) créée(s) — lot \"{lot}\", {duree_jours} jour(s) chacune.\n"
        ))
        for carte in cartes:
            self.stdout.write(f"  {carte.code}")
