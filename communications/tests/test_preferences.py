"""Préférences de communication, consentements (dont accord parental vérifiable), notifications de service
et indépendance vis-à-vis des SMS existants. Aucun appel réseau."""
import inspect
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from comptes import sms as sms_mod
from comptes.models import User
from communications import services
from communications.models import Campagne, ParametresCommunication, PreferenceCommunication

MES = "/api/eleve/communication/preferences/"
ADMIN = "/api/admin/communications/"
ACTIF = dict(COMMUNICATIONS_SMS_ACTIVES=True, COMMUNICATIONS_FOURNISSEUR="simule")


def user(tel, role=User.Role.ELEVE, statut=User.Statut.ACTIF, **extra):
    return User.objects.create_user(tel, password="Motdepasse-2026", prenom="Aicha", nom="Test", role=role, statut=statut, **extra)


def il_y_a_ans(n):
    d = date.today()
    return d.replace(year=d.year - n, day=min(d.day, 28)) if d.month == 2 else d.replace(year=d.year - n)


class MesPreferences(TestCase):
    def setUp(self):
        self.eleve = user("+22790000201", date_naissance=il_y_a_ans(16))
        self.autre = user("+22790000202", date_naissance=il_y_a_ans(30))
        self.c = APIClient()
        self.c.force_authenticate(self.eleve)

    def test_authentification_et_role_requis(self):
        self.assertEqual(APIClient().get(MES).status_code, 401)
        for tel, role in (("+22790000301", User.Role.ADMIN), ("+22790000302", User.Role.VENDEUR)):
            c = APIClient()
            c.force_authenticate(user(tel, role))
            self.assertEqual(c.get(MES).status_code, 403)
        c = APIClient()
        c.force_authenticate(user("+22790000310", statut=User.Statut.EN_ATTENTE))
        self.assertEqual(c.get(MES).status_code, 403)

    def test_etat_initial_sans_consentement_et_sans_ligne_creee(self):
        d = self.c.get(MES).json()
        self.assertEqual((d["sms_facultatifs"], d["invitations_whatsapp"], d["majorite"], d["parental_statut"]),
                         (True, None, "mineur", "aucun"))
        self.assertFalse(d["invitation_possible"])
        self.assertFalse(PreferenceCommunication.objects.filter(utilisateur=self.eleve).exists())

    def test_modifie_uniquement_ses_propres_preferences(self):
        r = self.c.patch(MES, {"sms_facultatifs": False, "invitations_whatsapp": True, "utilisateur": self.autre.id}, format="json")
        self.assertEqual(r.status_code, 200)
        p = PreferenceCommunication.objects.get(utilisateur=self.eleve)
        self.assertEqual((p.opposition_facultatif, p.invitations_whatsapp), (True, True))
        self.assertIsNotNone(p.invitations_whatsapp_le)
        self.assertFalse(PreferenceCommunication.objects.filter(utilisateur=self.autre).exists())
        # l'API admin est inaccessible à un élève
        r = self.c.patch(f"{ADMIN}utilisateurs/{self.autre.id}/preferences/", {"opposition_facultatif": True}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_le_consentement_seul_ne_suffit_pas_pour_un_mineur(self):
        self.c.patch(MES, {"invitations_whatsapp": True}, format="json")
        self.assertFalse(self.c.get(MES).json()["invitation_possible"])

    def test_un_majeur_avec_consentement_explicite_est_invitable(self):
        c = APIClient()
        c.force_authenticate(self.autre)
        self.assertFalse(c.get(MES).json()["invitation_possible"])
        c.patch(MES, {"invitations_whatsapp": True}, format="json")
        self.assertTrue(c.get(MES).json()["invitation_possible"])

    def test_demande_parentale_et_garde_fous(self):
        self.assertEqual(self.c.patch(MES, {"parental_telephone": "90000201"}, format="json").status_code, 400)  # son numéro
        self.assertEqual(self.c.patch(MES, {"parental_telephone": "123"}, format="json").status_code, 400)
        r = self.c.patch(MES, {"parental_telephone": "96000333"}, format="json").json()
        self.assertEqual(r["parental_statut"], "demande")
        self.assertNotIn("96000333", str(r))   # numéro du parent masqué côté élève
        p = PreferenceCommunication.objects.get(utilisateur=self.eleve)
        self.assertEqual(p.parental_statut, "demande")
        self.assertIsNone(p.parental_decide_par)

    def test_l_eleve_ne_peut_pas_se_valider_lui_meme(self):
        self.c.patch(MES, {"parental_telephone": "96000333", "parental_statut": "valide"}, format="json")
        self.assertEqual(PreferenceCommunication.objects.get(utilisateur=self.eleve).parental_statut, "demande")
        r = self.c.post(f"{ADMIN}utilisateurs/{self.eleve.id}/consentement-parental/", {"decision": "valider", "methode": "appel"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_un_majeur_n_a_pas_de_demande_parentale(self):
        c = APIClient()
        c.force_authenticate(self.autre)
        self.assertEqual(c.patch(MES, {"parental_telephone": "96000444"}, format="json").status_code, 400)

    def test_age_inconnu_traite_comme_mineur(self):
        inconnu = user("+22790000203")
        c = APIClient()
        c.force_authenticate(inconnu)
        c.patch(MES, {"invitations_whatsapp": True}, format="json")
        d = c.get(MES).json()
        self.assertEqual((d["majorite"], d["invitation_possible"]), ("inconnue", False))


class AccordParental(TestCase):
    def setUp(self):
        self.admin = user("+22790000401", User.Role.ADMIN)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.eleve = user("+22790000402", date_naissance=il_y_a_ans(15))
        self.c = APIClient()
        self.c.force_authenticate(self.eleve)
        self.c.patch(MES, {"invitations_whatsapp": True, "parental_telephone": "96000555"}, format="json")
        self.url = f"{ADMIN}utilisateurs/{self.eleve.id}/consentement-parental/"

    def test_file_des_demandes_reservee_a_l_admin(self):
        self.assertEqual(self.c.get(ADMIN + "consentements-parentaux/").status_code, 403)
        liste = self.api.get(ADMIN + "consentements-parentaux/").json()
        self.assertEqual([x["utilisateur_id"] for x in liste], [self.eleve.id])

    def test_validation_exige_la_methode_et_est_consignee(self):
        self.assertEqual(self.api.post(self.url, {"decision": "valider"}, format="json").status_code, 400)
        r = self.api.post(self.url, {"decision": "valider", "methode": "appel", "note": "Parent joint"}, format="json")
        self.assertEqual((r.status_code, r.json()["parental_statut"]), (200, "valide"))
        p = PreferenceCommunication.objects.get(utilisateur=self.eleve)
        self.assertEqual((p.parental_decide_par_id, p.parental_methode), (self.admin.id, "appel"))
        self.assertIsNotNone(p.parental_decide_le)
        self.assertTrue(self.c.get(MES).json()["invitation_possible"])

    def test_pas_de_validation_sans_demande(self):
        autre = user("+22790000403", date_naissance=il_y_a_ans(15))
        r = self.api.post(f"{ADMIN}utilisateurs/{autre.id}/consentement-parental/", {"decision": "valider", "methode": "appel"}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "pas_de_demande"))

    def test_refus_revocation_et_changement_de_contact(self):
        self.api.post(self.url, {"decision": "valider", "methode": "formulaire"}, format="json")
        self.c.patch(MES, {"parental_telephone": "96000666"}, format="json")   # nouveau contact : validation annulée
        self.assertEqual(PreferenceCommunication.objects.get(utilisateur=self.eleve).parental_statut, "demande")
        self.api.post(self.url, {"decision": "valider", "methode": "presence"}, format="json")
        self.assertEqual(self.api.post(self.url, {"decision": "revoquer"}, format="json").json()["parental_statut"], "aucun")
        self.assertFalse(self.c.get(MES).json()["invitation_possible"])
        self.c.patch(MES, {"parental_telephone": "96000777"}, format="json")
        self.assertEqual(self.api.post(self.url, {"decision": "refuser"}, format="json").json()["parental_statut"], "refuse")

    def test_retrait_du_consentement_par_l_eleve(self):
        self.api.post(self.url, {"decision": "valider", "methode": "appel"}, format="json")
        self.c.patch(MES, {"invitations_whatsapp": False}, format="json")
        self.assertFalse(self.c.get(MES).json()["invitation_possible"])


class ServiceEtIndependanceSms(TestCase):
    def setUp(self):
        self.admin = user("+22790000501", User.Role.ADMIN)
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        p = ParametresCommunication.charger()
        p.plafond_mensuel_fcfa, p.cout_segment_fcfa = 1000, 10
        p.save()

    def apercu(self, ids, type_, texte):
        return self.api.post(ADMIN + "campagnes/apercu/", {
            "cle": f"cle-pref-{type_}-{ids[0]}-{len(texte)}", "type": type_, "texte": texte, "mode": "ids", "ids": ids, "filtres": {}}, format="json").json()

    def test_activation_exige_un_compte_reellement_actif(self):
        for i, st in enumerate((User.Statut.EN_ATTENTE, User.Statut.SUSPENDU)):
            u = user(f"+2279000060{i}", statut=st)
            d = self.apercu([u.id], "activation", "Bonjour")
            self.assertEqual((d["nb_destinataires"], d["exclusions"]["statut_non_actif"]), (0, 1))

    def test_activation_est_un_service_sans_opt_in_ni_accord_parental(self):
        mineur = user("+22790000610", date_naissance=il_y_a_ans(12))
        PreferenceCommunication.objects.create(utilisateur=mineur, opposition_facultatif=True)
        d = self.apercu([mineur.id], "activation", "Bonjour")
        self.assertEqual((d["categorie"], d["nb_destinataires"]), ("service", 1))

    def test_sms_et_invitation_sont_facultatifs(self):
        u = user("+22790000611", date_naissance=il_y_a_ans(30))
        self.assertEqual(self.apercu([u.id], "sms", "Info")["categorie"], "facultatif")

    def test_les_reglages_communications_n_affectent_pas_envoyer_sms(self):
        for actif in (False, True):
            with override_settings(COMMUNICATIONS_SMS_ACTIVES=actif, COMMUNICATIONS_FOURNISSEUR="simule", SMS_MOCK=True):
                with mock.patch("requests.post") as post:
                    self.assertTrue(sms_mod.envoyer_sms("90000601", "Bonjour"))
                    post.assert_not_called()   # SMS_MOCK reste le seul interrupteur des SMS existants

    def test_envoyer_sms_ne_lit_aucun_reglage_communications(self):
        src = inspect.getsource(sms_mod.envoyer_sms).lower()
        self.assertNotIn("communications", src)

    def test_le_worker_est_inoperant_sans_activation_et_n_appelle_aucun_reseau(self):
        u = user("+22790000612", date_naissance=il_y_a_ans(30))
        d = self.apercu([u.id], "activation", "Bonjour")
        with mock.patch("requests.post") as post, override_settings(COMMUNICATIONS_SMS_ACTIVES=False):
            services.traiter_lot()
        post.assert_not_called()
        self.assertEqual(Campagne.objects.get(id=d["id"]).statut, "apercu")
