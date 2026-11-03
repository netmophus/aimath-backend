"""
Worker des tâches IA (process type Heroku `worker`) : python manage.py traiter_taches_ia

Plusieurs threads, chacun avec SA connexion PostgreSQL, réclament des tâches en parallèle (FOR UPDATE SKIP LOCKED :
aucune tâche n'est prise deux fois, même avec plusieurs dynos worker). Les appels IA sont des attentes réseau : quelques
threads suffisent. SIGTERM (redémarrage Heroku) : on cesse de réclamer, on laisse 20 s aux tâches en cours ; celles qui
ne finissent pas seront reprises par un autre worker à l'expiration de leur bail (tentatives bornées).
"""

import logging
import signal
import threading
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from traitement_ia import service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Traite les tâches IA en attente (worker)."

    def add_arguments(self, parser):
        parser.add_argument("--threads", type=int, default=int(settings.IA_WORKER_THREADS))
        parser.add_argument("--intervalle", type=float, default=float(settings.IA_WORKER_INTERVALLE_SECONDES))
        parser.add_argument("--une-fois", action="store_true", help="Traite ce qui est disponible puis s'arrête (tests, maintenance).")

    def handle(self, *args, **options):
        arret = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, lambda *_: arret.set())
            except (ValueError, OSError):  # hors thread principal
                pass
        fils = [threading.Thread(target=self._boucle, args=(arret, options), name=f"ia-{i}") for i in range(options["threads"])]
        for f in fils:
            f.start()
        derniere_purge = 0.0
        while any(f.is_alive() for f in fils):
            time.sleep(0.5)
            if time.monotonic() - derniere_purge > 600 and not options["une_fois"]:
                derniere_purge = time.monotonic()
                try:
                    logger.info("purge : %s tâche(s) expirée(s)", service.purger())
                except Exception:  # noqa: BLE001
                    logger.exception("purge impossible")
            if arret.is_set():
                break
        for f in fils:
            f.join(timeout=20)

    def _boucle(self, arret, options):
        nom = service.identifiant_travailleur()
        try:
            while not arret.is_set():
                tache = service.reclamer(nom)
                if tache is None:
                    if options["une_fois"]:
                        return
                    arret.wait(options["intervalle"])
                    continue
                try:
                    service.executer(tache)
                except Exception:  # noqa: BLE001 : le worker ne doit jamais mourir ; le bail permettra la reprise
                    logger.exception("tâche %s : échec d'enregistrement du résultat", tache.id)
                    connection.close()
        finally:
            connection.close()
