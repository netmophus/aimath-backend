"""
Envoie un SMS de rappel aux élèves dont l'abonnement expire dans 10, 5, 3 ou
1 jour(s) — destinée à tourner une fois par jour (voir Heroku Scheduler,
documenté dans le rapport de la tâche, pas ici).

Usage :
    python manage.py envoyer_rappels_abonnement

ANTI-DOUBLON : une ligne RappelAbonnementEnvoye n'est créée qu'APRÈS un
envoi RÉUSSI (jamais avant) — si un SMS échoue (LAM injoignable), aucune
ligne n'est créée et une relance de la commande LE MÊME JOUR le retentera ;
si un SMS a réussi, la ligne existe déjà et une relance le saute — dans les
deux cas, jamais de double envoi pour le même (élève, seuil, échéance
visée). La contrainte d'unicité en base (voir RappelAbonnementEnvoye.Meta)
est un garde-fou supplémentaire contre une éventuelle exécution concurrente.
"""

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from comptes.cartes import formater_date_fr
from comptes.models import RappelAbonnementEnvoye, User
from comptes.sms import envoyer_sms

SEUILS_JOURS = [10, 5, 3, 1]


class Command(BaseCommand):
    help = "Envoie un SMS de rappel aux élèves dont l'abonnement expire dans 10/5/3/1 jour(s) (anti-doublon)."

    def handle(self, *args, **options):
        aujourdhui = timezone.localdate()
        resume: dict[int, int] = {}

        for seuil in SEUILS_JOURS:
            date_cible = aujourdhui + timedelta(days=seuil)
            eleves = User.objects.filter(
                role=User.Role.ELEVE,
                statut=User.Statut.ACTIF,
                abonnement_actif_jusqu_au=date_cible,
            )

            envoyes = 0
            for eleve in eleves:
                deja_envoye = RappelAbonnementEnvoye.objects.filter(
                    user=eleve, seuil_jours=seuil, date_expiration_visee=date_cible,
                ).exists()
                if deja_envoye:
                    continue

                texte = (
                    f"Fahimta : ton abonnement expire dans {seuil} jour{'s' if seuil > 1 else ''} "
                    f"(le {formater_date_fr(date_cible)}). Recharge avec une carte ou via NITA sur myfahimta.com."
                )

                # envoyer_sms() ne lève jamais (voir comptes.sms) — le
                # try/except reste un garde-fou en plus, pas le seul
                # mécanisme : "si un SMS échoue, continuer les autres".
                try:
                    succes = envoyer_sms(eleve.telephone, texte)
                except Exception as exc:  # noqa: BLE001 — ne jamais interrompre la boucle
                    self.stderr.write(self.style.ERROR(f"Erreur inattendue pour {eleve.telephone} : {exc}"))
                    succes = False

                if not succes:
                    continue

                try:
                    RappelAbonnementEnvoye.objects.create(
                        user=eleve, seuil_jours=seuil, date_expiration_visee=date_cible,
                    )
                except IntegrityError:
                    # Contrainte d'unicité déclenchée (exécution concurrente
                    # improbable mais possible) : le SMS est déjà parti,
                    # rien d'autre à faire — on ne le recompte simplement pas.
                    continue

                envoyes += 1

            resume[seuil] = envoyes

        self.stdout.write(self.style.SUCCESS(f"\nRappels d'abonnement — {aujourdhui.isoformat()}"))
        for seuil in SEUILS_JOURS:
            self.stdout.write(f"  J-{seuil} : {resume[seuil]} rappel(s) envoyé(s).")
