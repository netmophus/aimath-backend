from django.core.management.base import BaseCommand

from budget_ia.service import reconcilier_abandonnees


class Command(BaseCommand):
    help = "Solde les réservations IA restées ouvertes (processus interrompu) : coût réservé conservé, statut « inconnue »."

    def handle(self, *args, **options):
        self.stdout.write(f"{reconcilier_abandonnees()} réservation(s) périmée(s) soldée(s).")
