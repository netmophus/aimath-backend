from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from aide.models import DemandeAide


class Command(BaseCommand):
    help = "Espace occupé en base par les pièces jointes de l'Aide (lecture seule). Code de sortie 1 au-delà du seuil."

    def handle(self, *args, **options):
        seuil_mo = getattr(settings, "AIDE_ESPACE_ALERTE_MO", 200)
        total = DemandeAide.objects.filter(piece_jointe_taille__gt=0).aggregate(n=Count("id"), octets=Sum("piece_jointe_taille"))
        octets = total["octets"] or 0
        mo = octets / (1024 * 1024)
        self.stdout.write(f"Pièces jointes : {total['n']} ({mo:.1f} Mo). Seuil d'alerte : {seuil_mo} Mo.")
        if mo >= seuil_mo:
            self.stderr.write("ALERTE : espace des pièces jointes au-dessus du seuil.")
            raise SystemExit(1)
