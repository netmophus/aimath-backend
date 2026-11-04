"""Garde avant chaque envoi, et absence de tout autre point d'envoi que le worker Communications. Aucun réseau."""
import io
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from communications import fournisseurs, services
from communications.models import Campagne, MessageSms, ParametresCommunication
from communications.tests.test_worker_demande import ACTIF, BASE, Base, user

RACINE = Path(settings.BASE_DIR)


class GardeAvantChaqueEnvoi(Base):
    def attendre(self):
        """Tous les messages restent en attente et rien n'est parti."""
        self.assertEqual(MessageSms.objects.filter(statut="en_attente").count(), 5)
        self.assertEqual(MessageSms.objects.exclude(statut="en_attente").count(), 0)

    def tenter(self, **reglages):
        with override_settings(**{**ACTIF, **reglages}), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env, \
                mock.patch("requests.post") as post:
            n = services.traiter_lot()
        env.assert_not_called()
        post.assert_not_called()
        self.assertEqual(n, 0)

    def test_envois_desactives(self):
        self.lancer()
        self.tenter(COMMUNICATIONS_SMS_ACTIVES=False)
        self.attendre()

    def test_fournisseur_inconnu_ne_replie_pas_sur_le_simule(self):
        self.lancer()
        self.tenter(COMMUNICATIONS_FOURNISSEUR="LAM ")   # faute de frappe : jamais de faux « accepté »
        self.attendre()
        with override_settings(**{**ACTIF, "COMMUNICATIONS_FOURNISSEUR": "kibiya"}):
            self.assertEqual(services.garde_envoi(), "fournisseur_inconnu")

    def test_plafond_ou_tarif_retires_apres_la_confirmation(self):
        self.lancer()
        ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=0)
        self.tenter()
        self.attendre()
        ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=1000, cout_segment_fcfa=None)
        self.tenter()
        self.attendre()

    def test_budget_depasse_apres_la_confirmation(self):
        self.lancer()                                   # 5 messages à 10 FCFA = 50
        ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=20)
        self.tenter()
        self.attendre()

    def test_le_budget_est_recontrole_entre_deux_messages(self):
        self.lancer()
        vus = []

        def faux(n, t):
            vus.append(n)
            return ("accepte", "ok")

        def baisser_le_plafond():
            ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=20)

        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=faux):
            n = services.traiter_lot(pause=baisser_le_plafond)
        self.assertEqual((n, len(vus)), (1, 1))        # arrêt au contrôle suivant
        self.assertEqual(MessageSms.objects.filter(statut="en_attente").count(), 4)
        self.assertEqual(Campagne.objects.get(id=MessageSms.objects.first().campagne_id).statut, "en_cours")

    def test_commande_ponctuelle_bloquee_sort_en_erreur_si_des_messages_attendent(self):
        self.lancer()
        for reglage in (dict(COMMUNICATIONS_SMS_ACTIVES=False), dict(COMMUNICATIONS_FOURNISSEUR="inconnu")):
            out = io.StringIO()
            with override_settings(**{**ACTIF, **reglage}), mock.patch("requests.post") as post:
                with self.assertRaises(CommandError) as cm:
                    call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
            post.assert_not_called()
            self.assertIn("5 message(s) restent en attente", str(cm.exception))
            self.attendre()

    def test_commande_ponctuelle_file_vide_termine_normalement_meme_desactivee(self):
        out = io.StringIO()
        with override_settings(COMMUNICATIONS_SMS_ACTIVES=False):
            call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
        self.assertIn("Rien n'est traité", out.getvalue())

    def test_bloquee_en_cours_de_route_sort_en_erreur_et_garde_le_reste(self):
        self.lancer()
        out = io.StringIO()

        def baisser(*_a):
            ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=20)

        with override_settings(**ACTIF), mock.patch.object(
                fournisseurs.FournisseurSimule, "envoyer", side_effect=lambda n, t: (baisser(), ("accepte", "ok"))[1]):
            with self.assertRaises(CommandError):
                call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
        self.assertEqual(MessageSms.objects.filter(statut="accepte").count(), 1)
        self.assertEqual(MessageSms.objects.filter(statut="en_attente").count(), 4)
        self.assertIn("1 message(s) traité(s)", out.getvalue())

    def test_commande_ponctuelle_signale_les_nouveaux_incertains(self):
        self.lancer(2)
        out = io.StringIO()
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=RuntimeError("boom")):
            call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
        self.assertEqual(MessageSms.objects.filter(statut="incertain").count(), 2)
        self.assertIn("2 nouveau(x)", out.getvalue())
        self.assertIn("à vérifier à la main", out.getvalue())


class AucunAutrePointDEnvoi(Base):
    """COMMUNICATIONS_SMS_ACTIVES=True avec le worker arrêté : aucun autre processus ne doit envoyer."""

    def test_activation_et_usage_complet_de_l_api_sans_worker_n_envoient_rien(self):
        eleve = user("+22790000801")
        en_attente = User_en_attente = user("+22790000802")
        from comptes.models import User
        User.objects.filter(id=en_attente.id).update(statut=User.Statut.EN_ATTENTE)
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env, \
                mock.patch.object(fournisseurs.FournisseurLam, "envoyer", create=True) as lam, mock.patch("requests.post") as post, \
                mock.patch("comptes.sms.envoyer_sms_detail") as detail:
            cid = self.lancer()
            self.api.get(BASE + "parametres/")
            self.api.get(BASE + "campagnes/")
            self.api.get(f"{BASE}campagnes/{cid}/")
            self.api.get(BASE + "messages/")
            self.api.get(BASE + "statut-activation/?ids=" + str(eleve.id))
            self.api.post(f"/api/admin/comptes/{User_en_attente.id}/approuver/")   # approbation : aucun SMS
            self.api.post(f"{BASE}campagnes/{cid}/confirmer/", {}, format="json")   # reconfirmation idempotente
        env.assert_not_called()
        lam.assert_not_called()
        detail.assert_not_called()
        post.assert_not_called()
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="en_attente").count(), 5)
        self.assertEqual(Campagne.objects.get(id=cid).statut, "en_cours")

    def test_seul_le_worker_appelle_le_traitement_des_envois(self):
        autorises = {"communications/services.py", "communications/management/commands/traiter_communications.py"}
        motif = re.compile(r"traiter_lot|_reserver_un|obtenir_fournisseur|_traiter_message")
        fautifs = []
        for chemin in RACINE.rglob("*.py"):
            rel = chemin.relative_to(RACINE).as_posix()
            if rel.startswith(("venv/", "staticfiles/")) or "/tests/" in rel or rel in autorises or rel == "communications/fournisseurs.py":
                continue
            if motif.search(chemin.read_text(encoding="utf-8", errors="ignore")):
                fautifs.append(rel)
        self.assertEqual(fautifs, [])

    def test_aucun_thread_signal_ou_demarrage_automatique_dans_le_module(self):
        for nom in ("services.py", "views.py", "apps.py", "models.py", "serializers.py", "urls.py", "eleve_urls.py", "admin.py"):
            src = (RACINE / "communications" / nom).read_text(encoding="utf-8")
            self.assertNotRegex(src, r"threading\.Thread|post_save|receiver\(|def ready|subprocess|Timer\(|apscheduler|celery", nom)

    def test_procfile_seul_le_process_communications_lance_le_worker_et_demarre_a_zero(self):
        lignes = [l.strip() for l in (RACINE / "Procfile").read_text(encoding="utf-8").splitlines() if l.strip()]
        avec = [l for l in lignes if "traiter_communications" in l]
        self.assertEqual(avec, ["communications: python manage.py traiter_communications"])
        self.assertTrue(any(l.startswith("release:") and l.endswith("migrate --noinput") and "communications" not in l for l in lignes))
        self.assertTrue(any(l.startswith("worker:") and "traiter_taches_ia" in l for l in lignes))
        for l in lignes:
            if l.startswith(("web:", "worker:", "release:")):
                self.assertNotIn("communications", l)
        for absent in ("app.json", "heroku.yml"):   # aucune formation (nombre de dynos) imposée par le dépôt
            self.assertFalse((RACINE / absent).exists(), absent)

    def test_les_commandes_de_demarrage_des_autres_process_n_appellent_pas_le_worker(self):
        src_ia = (RACINE / "traitement_ia" / "management" / "commands" / "traiter_taches_ia.py")
        if src_ia.exists():
            self.assertNotIn("communications", src_ia.read_text(encoding="utf-8"))
