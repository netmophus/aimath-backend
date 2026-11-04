"""Worker des communications SMS, distinct du worker de fahimta ai. Seul point d'entrée des envois de campagne.

Trois usages :
  python manage.py traiter_communications --jusqu-a-vide   (recommandé, à la demande) : traite tout ce qui est en
        attente, puis s'arrête de lui-même. Idéal avec `heroku run:detached`.
  python manage.py traiter_communications                  (process Heroku `communications`, boucle permanente)
  python manage.py traiter_communications --etat           (lecture seule : file d'attente, rien n'est envoyé)

Avant CHAQUE message, services.garde_envoi() vérifie : envois activés, fournisseur connu, plafond et tarif définis,
budget non dépassé. Au premier blocage le worker s'arrête et les messages restent EN_ATTENTE. Avec --jusqu-a-vide, un
blocage alors que des messages attendent se termine par un code de sortie 1 (visible dans les logs Heroku).
À SIGTERM ou Ctrl+C, le worker termine le message en cours puis sort ; les messages non démarrés restent EN_ATTENTE.
Un message dont l'envoi a été coupé en plein vol devient INCERTAIN et n'est jamais renvoyé automatiquement."""

import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from communications import services


class Command(BaseCommand):
    help = "Envoie par lots les messages des campagnes SMS confirmées."

    def add_arguments(self, parser):
        parser.add_argument("--une-fois", action="store_true", help="Un seul passage (un lot).")
        parser.add_argument("--jusqu-a-vide", action="store_true", help="Traite toute la file puis s'arrête.")
        parser.add_argument("--etat", action="store_true", help="Affiche la file d'attente et sort (lecture seule).")

    def _etat(self):
        f = services.file_attente()
        self.stdout.write(f"En attente : {f['en_attente']} | en cours d'envoi : {f['en_cours']} | incertains : {f['incertains']}")
        motif = services.garde_envoi()
        self.stdout.write(f"Envoi possible : {'oui' if not motif else 'non, ' + services.MOTIFS_GARDE[motif]} | "
                          f"fournisseur : {settings.COMMUNICATIONS_FOURNISSEUR}")

    def handle(self, *args, **options):
        if options["etat"]:
            self._etat()
            return

        unique = options["une_fois"] or options["jusqu_a_vide"]
        motif = services.garde_envoi()
        if motif and unique:
            self.stdout.write(f"Rien n'est traité : {services.MOTIFS_GARDE[motif]}")
            attente = services.file_attente()["en_attente"]
            if options["jusqu_a_vide"] and attente:
                raise CommandError(f"{attente} message(s) restent en attente : {services.MOTIFS_GARDE[motif]}")
            return

        arret = threading.Event()
        for nom in ("SIGTERM", "SIGINT"):
            sig = getattr(signal, nom, None)
            if sig is not None:
                try:
                    signal.signal(sig, lambda *_: arret.set())
                except ValueError:   # hors du thread principal (tests)
                    pass

        delai = 60.0 / max(1, settings.COMMUNICATIONS_DEBIT_PAR_MINUTE)
        total, sans_progres = 0, 0
        incertains_avant = services.file_attente()["incertains"]
        while not arret.is_set():
            n = services.traiter_lot(pause=lambda: arret.wait(delai), arret=arret.is_set)
            total += n
            if options["une_fois"]:
                break
            if n == 0:
                if options["jusqu_a_vide"]:
                    attente = services.file_attente()["en_attente"]
                    if attente == 0:
                        break   # file vide : fin normale
                    blocage = services.garde_envoi()
                    if blocage:
                        self._bilan(total, "bloqué", incertains_avant)
                        raise CommandError(f"{attente} message(s) restent en attente : {services.MOTIFS_GARDE[blocage]}")
                    sans_progres += 1   # messages réservés par un autre processus : on patiente un peu
                    if sans_progres >= 12:
                        self._bilan(total, "messages réservés par un autre processus", incertains_avant)
                        raise CommandError(f"{attente} message(s) restent en attente (réservés par un autre processus).")
                arret.wait(5)
            else:
                sans_progres = 0
        self._bilan(total, "arrêt demandé, sortie propre" if arret.is_set() else "terminé", incertains_avant)

    def _bilan(self, total, etat, incertains_avant):
        f = services.file_attente()
        nouveaux = f["incertains"] - incertains_avant
        self.stdout.write(f"{total} message(s) traité(s) ({etat}). Restent en attente : {f['en_attente']} ; "
                          f"incertains : {f['incertains']}" + (f" (dont {nouveaux} nouveau(x) : à vérifier à la main)." if nouveaux > 0 else "."))
