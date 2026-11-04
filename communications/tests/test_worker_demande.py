"""Worker à la demande : file d'attente sans worker, arrêt propre, jamais de renvoi d'un message incertain. Aucun réseau."""
import io
import threading
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from comptes.models import User
from communications import fournisseurs, services
from communications.models import Campagne, MessageSms, ParametresCommunication

BASE = "/api/admin/communications/"
ACTIF = dict(COMMUNICATIONS_SMS_ACTIVES=True, COMMUNICATIONS_FOURNISSEUR="simule", COMMUNICATIONS_DEBIT_PAR_MINUTE=60000)


def user(tel, **extra):
    return User.objects.create_user(tel, password="Motdepasse-2026", prenom="Aicha", nom="Test", role=User.Role.ELEVE,
                                    statut=User.Statut.ACTIF, **extra)


class Base(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("+22790000001", password="Motdepasse-2026", prenom="A", nom="B", role=User.Role.ADMIN,
                                              statut=User.Statut.ACTIF)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        p = ParametresCommunication.charger()
        p.plafond_mensuel_fcfa, p.cout_segment_fcfa = 1000, Decimal("10")
        p.save()
        self.eleves = [user(f"+2279000070{i}") for i in range(5)]
        self.n = 0

    def lancer(self, nb=5):
        self.n += 1
        d = self.api.post(BASE + "campagnes/apercu/", {
            "cle": f"cle-worker-{self.n:03d}", "type": "sms", "texte": "Bonjour {prenom}", "mode": "ids",
            "ids": [e.id for e in self.eleves[:nb]], "filtres": {}}, format="json").json()
        with override_settings(**ACTIF):
            self.assertEqual(self.api.post(f"{BASE}campagnes/{d['id']}/confirmer/", {}, format="json").status_code, 200)
        return d["id"]


class FileSansWorker(Base):
    def test_confirmer_n_envoie_rien_et_la_campagne_reste_en_attente(self):
        cid = self.lancer()
        c = self.api.get(f"{BASE}campagnes/{cid}/").json()
        self.assertEqual(c["statut"], "en_cours")
        self.assertEqual(c["messages"]["en_attente"], 5)
        self.assertEqual(sum(c["messages"][k] for k in ("accepte", "echec", "incertain", "en_cours")), 0)
        self.assertEqual(self.api.get(BASE + "parametres/").json()["file_attente"]["en_attente"], 5)

    def test_apres_des_jours_sans_worker_aucune_perte_ni_envoi_spontane(self):
        cid = self.lancer()
        with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            MessageSms.objects.update(mis_a_jour_le=timezone.now() - timedelta(days=3))
            # les services annexes (aperçu, historique, récupération) ne déclenchent aucun envoi
            self.api.get(BASE + "campagnes/")
            services.recuperer_interrompus()
        env.assert_not_called()
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="en_attente").count(), 5)

    def test_le_demarrage_du_worker_envoie_chaque_message_exactement_une_fois(self):
        cid = self.lancer()
        vus = []
        with override_settings(**ACTIF), mock.patch.object(
                fournisseurs.FournisseurSimule, "envoyer", side_effect=lambda n, t: (vus.append(n), ("accepte", "ok"))[1]):
            out = io.StringIO()
            call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
            call_command("traiter_communications", "--jusqu-a-vide", stdout=out)   # second démarrage : rien à refaire
        self.assertEqual(len(vus), 5)
        self.assertEqual(len(set(vus)), 5)
        c = Campagne.objects.get(id=cid)
        self.assertEqual(c.statut, "terminee")
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="accepte", tentatives=1).count(), 5)

    def test_deux_workers_simultanes_ne_doublent_aucun_message(self):
        self.lancer()
        vus, verrou = [], threading.Lock()

        def faux(n, t):
            with verrou:
                vus.append(n)
            return ("accepte", "ok")

        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=faux):
            services.traiter_lot()
            services.traiter_lot()
        self.assertEqual(len(vus), len(set(vus)))

    def test_envois_desactives_le_mode_a_la_demande_sort_sans_rien_faire(self):
        cid = self.lancer()
        out = io.StringIO()
        with override_settings(COMMUNICATIONS_SMS_ACTIVES=False), mock.patch("requests.post") as post:
            with self.assertRaises(CommandError):   # des messages attendent mais rien ne peut partir : code de sortie 1
                call_command("traiter_communications", "--jusqu-a-vide", stdout=out)
        post.assert_not_called()
        self.assertIn("désactivés", out.getvalue())
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="en_attente").count(), 5)

    def test_commande_etat_en_lecture_seule(self):
        self.lancer()
        out = io.StringIO()
        with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            call_command("traiter_communications", "--etat", stdout=out)
        env.assert_not_called()
        self.assertIn("En attente : 5", out.getvalue())


class ArretPropre(Base):
    def test_arret_demande_les_messages_non_demarres_restent_en_attente(self):
        cid = self.lancer()
        envoyes = []

        def faux(n, t):
            envoyes.append(n)
            return ("accepte", "ok")

        etat = {"stop": False}

        def arret():
            return etat["stop"]

        def pause():
            etat["stop"] = True   # SIGTERM reçu après le premier message

        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=faux):
            n = services.traiter_lot(pause=pause, arret=arret)
        self.assertEqual((n, len(envoyes)), (1, 1))
        statuts = list(MessageSms.objects.filter(campagne_id=cid).order_by("id").values_list("statut", flat=True))
        self.assertEqual(statuts, ["accepte", "en_attente", "en_attente", "en_attente", "en_attente"])
        self.assertEqual(Campagne.objects.get(id=cid).statut, "en_cours")   # pas « terminée » tant qu'il reste de la file
        # reprise : les 4 restants partent, aucun doublon
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=faux):
            services.traiter_lot()
        self.assertEqual(len(envoyes), 5)
        self.assertEqual(len(set(envoyes)), 5)

    def test_au_plus_un_message_en_vol_a_la_fois(self):
        self.lancer()
        en_vol = []

        def faux(n, t):
            en_vol.append(MessageSms.objects.filter(statut="en_cours").count())
            return ("accepte", "ok")

        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=faux):
            services.traiter_lot()
        self.assertEqual(set(en_vol), {1})

    def test_coupure_brutale_en_plein_envoi_donne_incertain_et_jamais_de_renvoi(self):
        cid = self.lancer()

        class Coupure(BaseException):   # simule un SIGKILL : aucune gestion d'erreur ne s'exécute
            pass

        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=Coupure()):
            with self.assertRaises(Coupure):
                services.traiter_lot()
        m = MessageSms.objects.filter(campagne_id=cid, statut="en_cours")
        self.assertEqual(m.count(), 1)                     # un seul message ambigu, pas un lot
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="en_attente").count(), 4)
        MessageSms.objects.filter(statut="en_cours").update(mis_a_jour_le=timezone.now() - timedelta(minutes=30))
        envoyes = []
        with override_settings(**ACTIF), mock.patch.object(
                fournisseurs.FournisseurSimule, "envoyer", side_effect=lambda n, t: (envoyes.append(n), ("accepte", "ok"))[1]):
            call_command("traiter_communications", "--jusqu-a-vide", stdout=io.StringIO())
            call_command("traiter_communications", "--jusqu-a-vide", stdout=io.StringIO())
        incertain = MessageSms.objects.get(campagne_id=cid, statut="incertain")
        self.assertEqual((incertain.dernier_code, incertain.tentatives), ("interrompu", 1))
        self.assertEqual(len(envoyes), 4)                  # les 4 autres seulement ; l'incertain n'est jamais renvoyé
        self.assertEqual(Campagne.objects.get(id=cid).statut, "terminee")

    def test_relance_des_echecs_ne_touche_pas_aux_incertains(self):
        cid = self.lancer(2)
        MessageSms.objects.filter(campagne_id=cid).update(statut="incertain", dernier_code="interrompu")
        Campagne.objects.filter(id=cid).update(statut="terminee")
        r = self.api.post(f"{BASE}campagnes/{cid}/relancer-echecs/")
        self.assertEqual(MessageSms.objects.filter(campagne_id=cid, statut="incertain").count(), 2)
        self.assertNotEqual(r.status_code, 500)
