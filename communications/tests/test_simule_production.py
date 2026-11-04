"""Le fournisseur simulé est interdit hors développement et tests : aucun faux « accepté » dans une campagne réelle."""
import io
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from communications import fournisseurs, services
from communications.models import Campagne, MessageSms
from communications.tests.test_worker_demande import ACTIF, BASE, Base

PRODUCTION = dict(ACTIF, COMMUNICATIONS_SIMULE_AUTORISE=False)   # reproduit la production : simulé configuré, non autorisé


class SimuleInterditEnProduction(Base):
    def test_le_simule_reste_autorise_pour_les_tests_automatises(self):
        self.assertTrue(settings.COMMUNICATIONS_SIMULE_AUTORISE)

    def test_le_worker_refuse_d_envoyer_et_n_enregistre_aucun_faux_accepte(self):
        cid = self.lancer()
        with override_settings(**PRODUCTION), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env, \
                mock.patch("requests.post") as post:
            self.assertEqual(services.garde_envoi(), "fournisseur_simule_interdit")
            self.assertEqual(services.traiter_lot(), 0)
        env.assert_not_called()
        post.assert_not_called()
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="en_attente").count(), 5)
        self.assertEqual(MessageSms.objects.filter(statut="accepte").count(), 0)
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid).values_list("tentatives", flat=True).distinct().get(), 0)

    def test_la_commande_ponctuelle_sort_en_erreur(self):
        self.lancer()
        out = io.StringIO()
        with override_settings(**PRODUCTION):
            with self.assertRaises(CommandError) as cm:
                call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
        self.assertIn("simulé est interdit", str(cm.exception))
        self.assertEqual(MessageSms.objects.exclude(statut="en_attente").count(), 0)

    def test_la_commande_etat_indique_le_blocage_en_lecture_seule(self):
        self.lancer()
        out = io.StringIO()
        with override_settings(**PRODUCTION), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            call_command("traiter_communications", "--etat", stdout=out)
        env.assert_not_called()
        self.assertIn("simulé est interdit", out.getvalue())
        self.assertIn("En attente : 5", out.getvalue())

    def test_la_confirmation_est_refusee_en_production_avec_le_simule(self):
        d = self.api.post(BASE + "campagnes/apercu/", {
            "cle": "cle-simule-prod", "type": "sms", "texte": "Bonjour", "mode": "ids", "ids": [self.eleves[0].id], "filtres": {}},
            format="json").json()
        with override_settings(**PRODUCTION):
            r = self.api.post(f"{BASE}campagnes/{d['id']}/confirmer/", {}, format="json")
            parametres = self.api.get(BASE + "parametres/").json()
        self.assertEqual((r.status_code, r.json()["code"]), (409, "fournisseur_simule_interdit"))
        self.assertEqual(Campagne.objects.get(id=d["id"]).statut, "apercu")
        self.assertFalse(parametres["envois_actifs"])   # l'écran désactive la confirmation

    def test_avec_un_fournisseur_reel_la_garde_laisse_passer(self):
        with override_settings(**dict(ACTIF, COMMUNICATIONS_FOURNISSEUR="lam", COMMUNICATIONS_SIMULE_AUTORISE=False)):
            self.assertIsNone(services.garde_envoi())   # LAM reste utilisable : le blocage ne vise que le simulé

    def test_pas_de_contournement_par_variable_d_environnement(self):
        src = open(settings.BASE_DIR / "config" / "settings.py", encoding="utf-8").read()
        ligne = next(l for l in src.splitlines() if l.startswith("COMMUNICATIONS_SIMULE_AUTORISE"))
        self.assertNotIn("config(", ligne)
