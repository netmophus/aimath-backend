"""Worker OTP dédié : envoie les codes de récupération de mot de passe en attente (file persistante PostgreSQL).

  python manage.py traiter_envoi_codes_otp            process Heroku `otp` : boucle permanente
  python manage.py traiter_envoi_codes_otp --une-fois un seul passage (nettoyage + envois dus), puis sortie
  python manage.py traiter_envoi_codes_otp --etat     lecture seule : état de la file, rien n'est envoyé

Fonctionnement de la boucle permanente :
- Toutes les OTP_SONDAGE_SECONDES : nettoyage (lignes « en cours » trop anciennes -> incertain ; lignes périmées ->
  expiré), signe de vie en base, puis envoi des lignes dues.
- Service non activé (OTP_SMS_ACTIFS faux) ou secret OTP_CLE_SECRETE absent : le worker reste en veille, n'envoie rien
  et ne donne pas de signe de vie ; les demandes répondent alors « service temporairement indisponible ».
- SIGTERM / Ctrl+C : le message en cours est terminé, puis le worker sort proprement. Une coupure brutale en plein envoi
  laisse une ligne « en cours » qui devient « incertain » (jamais renvoyée).
- Indépendant de `traiter_taches_ia` (fahimta ai) et de `traiter_communications` (campagnes).
"""

import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from recuperation import envoi


class Command(BaseCommand):
    help = "Envoie les codes de récupération de mot de passe en attente (worker OTP dédié)."

    def add_arguments(self, parser):
        parser.add_argument("--une-fois", action="store_true", help="Un seul passage puis sortie.")
        parser.add_argument("--etat", action="store_true", help="Affiche l'état de la file (lecture seule).")

    def handle(self, *args, **options):
        if options["etat"]:
            f = envoi.etat_file()
            secret = len(getattr(settings, "OTP_CLE_SECRETE", "") or "") >= 32
            self.stdout.write(
                f"Service activé : {'oui' if settings.OTP_SMS_ACTIFS else 'non'} | secret présent : {'oui' if secret else 'non'} | "
                + " | ".join(f"{k} : {v}" for k, v in f.items()))
            return

        if options["une_fois"]:
            n = envoi.passage_envoi_otp()
            self.stdout.write(f"{n} envoi(s) traité(s).")
            return

        arret = threading.Event()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: arret.set())
            except ValueError:   # pas dans le fil principal
                pass

        self.stdout.write("Worker OTP démarré.")
        veille_signalee = False
        while not arret.is_set():
            close_old_connections()
            try:
                if envoi.peut_envoyer():
                    veille_signalee = False
                    envoi.passage_envoi_otp()
                elif not veille_signalee:
                    self.stdout.write("Service OTP non activé ou secret absent : veille, aucun envoi.")
                    veille_signalee = True
            except Exception:   # noqa: BLE001 - la boucle doit survivre à une erreur de base passagère
                self.stderr.write("Erreur de traitement (sans texte ni code), nouvelle tentative au prochain passage.")
            arret.wait(settings.OTP_SONDAGE_SECONDES)
        self.stdout.write("Worker OTP arrêté proprement.")
