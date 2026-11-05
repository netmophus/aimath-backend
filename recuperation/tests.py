"""Récupération de mot de passe par OTP + changement volontaire + invalidation des jetons.

Aucun SMS réel : `envoyer_sms_detail` (appelé par le worker) est remplacé par un double dans tous les tests ; le worker
est exécuté explicitement par les tests (`passage_envoi_otp`) pour rendre les assertions déterministes. Les numéros et mots de passe sont fictifs, générés pour les tests."""

import re
import threading
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from comptes.jetons import RefreshVersionne

from recuperation import envoi, services
from recuperation.models import BattementWorkerOtp, DemandeReinitialisation, EnvoiCodeSms, EvenementRecuperation

User = get_user_model()
NUM = "90111222"          # numéro national fictif
NUM2 = "90333444"
MDP = "AncienMdp-7391"
NOUVEAU = "NouveauMdp-5824"
URL_DEM = "/api/auth/mot-de-passe-oublie/demander/"
URL_VER = "/api/auth/mot-de-passe-oublie/verifier/"
URL_REI = "/api/auth/mot-de-passe-oublie/reinitialiser/"
# Valeur de test sans aucune valeur réelle : le vrai secret n'existe que dans l'environnement de production.
CLE_TEST = "cle-de-test-sans-valeur-reelle-0123456789"
SOUS_TEST = dict(OTP_SMS_ACTIFS=True, SMS_MOCK=True, OTP_CLE_SECRETE=CLE_TEST)


class Base(TransactionTestCase):
    """TransactionTestCase : les verrous et transactions des services s'exécutent réellement."""

    def setUp(self):
        self.envois = []
        self.appels = []

        def faux_fournisseur(tel, texte, *a, **k):
            self.appels.append(tel)
            self.envois.append((tel, texte))
            return self.resultat_fournisseur

        self.resultat_fournisseur = ("accepte", "test")
        patcher = mock.patch("recuperation.envoi.envoyer_sms_detail", side_effect=faux_fournisseur)
        patcher.start()
        self.addCleanup(patcher.stop)
        BattementWorkerOtp.objects.update_or_create(pk=1, defaults={"dernier_battement": timezone.now()})
        self.user = User.objects.create_user(f"+227{NUM}", MDP, statut="actif", role="eleve")
        self.c = APIClient()

    def code_envoye(self) -> str:
        return re.search(r"est (\d{6})\.", self.envois[-1][1]).group(1)

    def traiter(self):
        """Fait tourner le worker une fois (aucun SMS réel : le fournisseur est un double)."""
        with override_settings(**SOUS_TEST):
            return envoi.passage_envoi_otp()

    def demander(self, tel=NUM, **kw):
        """Demande de code, puis passage du worker (c'est lui qui envoie)."""
        r = self.c.post(URL_DEM, {"telephone": tel}, format="json", **kw)
        if r.status_code == 200:
            self.traiter()
        return r

    def verifier(self, code, tel=NUM, **kw):
        return self.c.post(URL_VER, {"telephone": tel, "code": code}, format="json", **kw)

    def reinit(self, autorisation, nouveau=NOUVEAU, confirmation=None, tel=NUM, **kw):
        return self.c.post(URL_REI, {"telephone": tel, "autorisation": autorisation, "nouveau_mot_de_passe": nouveau,
                                     "confirmation": nouveau if confirmation is None else confirmation}, format="json", **kw)

    def avancer(self, **delta):
        """Recule toutes les dates enregistrées : simule le passage du temps sans dormir."""
        d = timedelta(**delta)
        EvenementRecuperation.objects.update(cree_le=timezone.now() - d)
        DemandeReinitialisation.objects.update(cree_le=timezone.now() - d, expire_le=timezone.now() + timedelta(minutes=5) - d)
        EnvoiCodeSms.objects.update(cree_le=timezone.now() - d, disponible_le=timezone.now() - d,
                                    expire_le=timezone.now() + timedelta(minutes=5) - d)

    def parcours_complet(self):
        self.demander()
        code = self.code_envoye()
        return self.verifier(code).json()["autorisation"]


@override_settings(**SOUS_TEST)
class DemandeCodeTests(Base):
    def test_numero_existant_envoie_un_sms_et_reponse_neutre(self):
        r = self.demander()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["message"], "Si ce numéro est associé à un compte, un code sera envoyé.")
        self.assertEqual(len(self.envois), 1)
        self.assertRegex(self.envois[0][1], r"^FAHIMTA : votre code de vérification est \d{6}\. Valable 5 minutes\. Ne le partagez avec personne\.$")

    def test_numero_inexistant_meme_reponse_sans_sms(self):
        a = self.demander(NUM2)
        self.assertEqual(self.envois, [])
        self.demander()   # existant, autre numéro
        b = self.c.post(URL_DEM, {"telephone": "90555666"}, format="json")
        self.assertEqual(a.status_code, b.status_code)
        self.assertEqual(set(a.json()), set(b.json()))
        self.assertEqual(a.json()["message"], b.json()["message"])

    def test_compte_non_actif_ne_recoit_rien_et_reponse_identique(self):
        User.objects.create_user(f"+227{NUM2}", MDP, statut="suspendu")
        r = self.demander(NUM2)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.envois, [])

    def test_formats_invalides(self):
        for tel in ["123", "abcdefgh", "", "9011122233333"]:
            r = self.c.post(URL_DEM, {"telephone": tel}, format="json")
            self.assertEqual(r.status_code, 400, tel)
        self.assertEqual(self.envois, [])

    def test_formats_acceptes_avec_prefixe_et_espaces(self):
        self.assertEqual(self.demander("+227 90 11 12 22").status_code, 200)
        self.assertEqual(len(self.envois), 1)

    def test_code_jamais_stocke_en_base(self):
        self.demander()
        code = self.code_envoye()
        d = DemandeReinitialisation.objects.get()
        e = EnvoiCodeSms.objects.get()
        valeurs = [str(v) for v in list(d.__dict__.values()) + list(e.__dict__.values())]
        self.assertFalse(any(code in v for v in valeurs if len(v) < 40 and v.isdigit() or v == code))
        self.assertEqual(len(d.sel), 32)

    def test_code_absent_des_journaux_avec_le_vrai_service_en_mode_simule(self):
        """Fournisseur NON remplacé : c'est `envoyer_sms_detail` en mode simulé qui tourne ; il ne doit rien divulguer."""
        import logging

        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        code = services.code_pour(DemandeReinitialisation.objects.get())
        with mock.patch("recuperation.envoi.envoyer_sms_detail", side_effect=__import__("comptes.sms", fromlist=["x"]).envoyer_sms_detail):
            with self.assertLogs(level="DEBUG") as logs:
                logging.getLogger("amorce").debug("amorce")
                self.traiter()
        self.assertFalse(any(code in ligne for ligne in logs.output))
        self.assertTrue(any("accepte" in ligne for ligne in logs.output))

    def test_budget_epuise_bloque_sans_sms(self):
        with override_settings(OTP_PLAFOND_SMS_JOUR=1):
            self.assertEqual(self.demander().status_code, 200)
            self.avancer(seconds=120)
            r = self.demander()
            self.assertEqual(r.status_code, 503)
            self.assertEqual(len(self.envois), 1)

    def test_budget_mensuel_independant_du_plafond_communications(self):
        with override_settings(OTP_PLAFOND_SMS_MOIS=1, OTP_PLAFOND_SMS_JOUR=100):
            self.demander()
            self.avancer(seconds=120)
            self.assertEqual(self.demander().status_code, 503)

    def test_desactive_par_defaut_aucun_envoi(self):
        with override_settings(OTP_SMS_ACTIFS=False):
            r = self.demander()
            self.assertEqual(r.status_code, 503)
            self.assertEqual(self.envois, [])

    def test_fournisseur_en_panne_reponse_http_inchangee(self):
        self.resultat_fournisseur = ("non_envoye", "injoignable")
        r = self.demander()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["message"], "Si ce numéro est associé à un compte, un code sera envoyé.")

    def test_fournisseur_qui_leve_ne_casse_pas(self):
        with mock.patch("recuperation.envoi.envoyer_sms_detail", side_effect=RuntimeError("boom 123456")):
            r = self.demander()
        self.assertEqual(r.status_code, 200)


@override_settings(**SOUS_TEST)
class LimitesTests(Base):
    def test_delai_minimum_entre_deux_demandes(self):
        self.demander()
        r = self.demander()
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r)
        self.assertEqual(len(self.envois), 1)

    def test_limite_par_numero_par_heure(self):
        for _ in range(3):
            self.assertEqual(self.demander().status_code, 200)
            self.avancer(seconds=90)
        self.assertEqual(self.demander().status_code, 429)
        self.assertEqual(len(self.envois), 3)

    def test_limite_par_numero_identique_pour_numero_inexistant(self):
        for _ in range(3):
            self.assertEqual(self.demander(NUM2).status_code, 200)
            self.avancer(seconds=90)
        self.assertEqual(self.demander(NUM2).status_code, 429)   # même comportement : pas de fuite d'existence

    def test_limite_par_ip(self):
        with override_settings(OTP_MAX_DEMANDES_PAR_IP_HEURE=2):
            for i in range(2):
                self.assertEqual(self.c.post(URL_DEM, {"telephone": f"9000000{i}"}, format="json", REMOTE_ADDR="10.1.1.1").status_code, 200)
            r = self.c.post(URL_DEM, {"telephone": "90000099"}, format="json", REMOTE_ADDR="10.1.1.1")
            self.assertEqual(r.status_code, 429)
            ok = self.c.post(URL_DEM, {"telephone": "90000098"}, format="json", REMOTE_ADDR="10.2.2.2")
            self.assertEqual(ok.status_code, 200)

    def test_ip_prise_en_derniere_entree_xff(self):
        with override_settings(OTP_MAX_DEMANDES_PAR_IP_HEURE=1):
            self.c.post(URL_DEM, {"telephone": "90000011"}, format="json", HTTP_X_FORWARDED_FOR="6.6.6.6, 9.9.9.9")
            r = self.c.post(URL_DEM, {"telephone": "90000012"}, format="json", HTTP_X_FORWARDED_FOR="7.7.7.7, 9.9.9.9")
            self.assertEqual(r.status_code, 429)   # l'entrée forgée par le client n'évite pas la limite

    def test_limite_globale(self):
        with override_settings(OTP_MAX_DEMANDES_GLOBAL_HEURE=2):
            for i, ip in enumerate(["1.1.1.1", "2.2.2.2"]):
                self.c.post(URL_DEM, {"telephone": f"9000010{i}"}, format="json", REMOTE_ADDR=ip)
            r = self.c.post(URL_DEM, {"telephone": "90000109"}, format="json", REMOTE_ADDR="3.3.3.3")
            self.assertEqual(r.status_code, 429)

    def test_demandes_simultanees_une_seule_passe(self):
        if connection.vendor != "postgresql":
            self.skipTest("Verrou consultatif PostgreSQL requis pour ce test de concurrence")
        resultats = []

        def tirer():
            from django.db import connection as conn
            try:
                resultats.append(APIClient().post(URL_DEM, {"telephone": NUM}, format="json").status_code)   # sans worker
            finally:
                conn.close()

        fils = [threading.Thread(target=tirer) for _ in range(6)]
        [f.start() for f in fils]
        [f.join() for f in fils]
        self.assertEqual(sorted(resultats).count(200), 1)
        self.traiter()
        self.assertEqual(len(self.envois), 1)

    def test_demande_concurrente_sequentielle_sqlite_une_seule_passe(self):
        a, b = self.demander(), self.demander()
        self.assertEqual((a.status_code, b.status_code), (200, 429))


@override_settings(**SOUS_TEST)
class VerificationTests(Base):
    def test_bon_code_donne_autorisation_et_est_a_usage_unique(self):
        self.demander()
        code = self.code_envoye()
        r = self.verifier(code)
        self.assertEqual(r.status_code, 200)
        self.assertIn("autorisation", r.json())
        self.assertEqual(self.verifier(code).status_code, 400)   # rejeu refusé

    def test_mauvais_code(self):
        self.demander()
        mauvais = "000000" if self.code_envoye() != "000000" else "111111"
        r = self.verifier(mauvais)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["detail"], "Code invalide ou expiré.")

    def test_format_de_code_invalide(self):
        self.demander()
        for code in ["12345", "1234567", "abcdef", "12 456"]:
            self.assertEqual(self.verifier(code).status_code, 400, code)

    def test_code_expire(self):
        self.demander()
        code = self.code_envoye()
        DemandeReinitialisation.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.verifier(code).status_code, 400)

    def test_trop_de_tentatives_invalide_meme_le_bon_code(self):
        self.demander()
        bon = self.code_envoye()
        faux = "000000" if bon != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verifier(faux).status_code, 400)
        self.assertEqual(self.verifier(bon).status_code, 400)
        self.assertEqual(DemandeReinitialisation.objects.get().cloture_motif, "epuisee")

    def test_nouveau_code_remplace_l_ancien(self):
        self.demander()
        ancien = self.code_envoye()
        self.avancer(seconds=90)
        self.demander()
        nouveau = self.code_envoye()
        if ancien != nouveau:
            self.assertEqual(self.verifier(ancien).status_code, 400)
        self.assertEqual(self.verifier(nouveau).status_code, 200)

    def test_numero_inexistant_meme_erreur(self):
        r = self.verifier("123456", tel=NUM2)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["detail"], "Code invalide ou expiré.")

    def test_limite_echecs_par_ip(self):
        with override_settings(OTP_MAX_ECHECS_PAR_IP_HEURE=3):
            for _ in range(3):
                self.verifier("123456", tel=NUM2, REMOTE_ADDR="8.8.8.8")
            self.assertEqual(self.verifier("123456", tel=NUM2, REMOTE_ADDR="8.8.8.8").status_code, 429)

    def test_demander_un_nouveau_code_ne_remet_pas_les_tentatives_a_zero_pour_contourner(self):
        """Chaque nouveau code consomme le plafond horaire par numéro : on ne peut pas essayer à l'infini."""
        faux_total = 0
        for _ in range(3):
            self.assertEqual(self.demander().status_code, 200)
            bon = self.code_envoye()
            faux = "000000" if bon != "000000" else "111111"
            for _ in range(5):
                self.verifier(faux)
                faux_total += 1
            self.avancer(seconds=90)
        self.assertEqual(self.demander().status_code, 429)
        self.assertEqual(faux_total, 15)


@override_settings(**SOUS_TEST)
class ReinitialisationTests(Base):
    def test_succes_change_le_mot_de_passe_sans_connexion_automatique(self):
        aut = self.parcours_complet()
        r = self.reinit(aut)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"message": "Mot de passe modifié."})
        self.assertNotIn("access", r.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NOUVEAU))
        self.assertFalse(self.user.check_password(MDP))

    def test_autorisation_a_usage_unique(self):
        aut = self.parcours_complet()
        self.assertEqual(self.reinit(aut).status_code, 200)
        self.assertEqual(self.reinit(aut, nouveau="Autre-Mdp-4417").status_code, 400)

    def test_sans_autorisation_ou_inventee(self):
        self.parcours_complet()
        self.assertEqual(self.reinit("inventee").status_code, 400)
        self.assertEqual(self.c.post(URL_REI, {"telephone": NUM, "nouveau_mot_de_passe": NOUVEAU, "confirmation": NOUVEAU}, format="json").status_code, 400)

    def test_autorisation_liee_au_numero(self):
        User.objects.create_user(f"+227{NUM2}", MDP, statut="actif")
        aut = self.parcours_complet()
        self.assertEqual(self.reinit(aut, tel=NUM2).status_code, 400)

    def test_code_non_verifie_ne_permet_pas_de_reinitialiser(self):
        self.demander()
        self.assertEqual(self.reinit(self.code_envoye()).status_code, 400)

    def test_autorisation_expiree(self):
        aut = self.parcours_complet()
        DemandeReinitialisation.objects.update(autorisation_expire_le=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.reinit(aut).status_code, 400)

    def test_autorisation_remplacee_par_une_nouvelle_demande(self):
        aut = self.parcours_complet()
        self.avancer(seconds=90)
        self.demander()
        self.assertEqual(self.reinit(aut).status_code, 400)

    def test_trop_d_autorisations_fausses_ferment_la_demande(self):
        aut = self.parcours_complet()
        for _ in range(5):
            self.reinit("fausse")
        self.assertEqual(self.reinit(aut).status_code, 400)

    def test_confirmation_differente(self):
        aut = self.parcours_complet()
        r = self.reinit(aut, confirmation="Different-1234")
        self.assertEqual(r.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(MDP))
        self.assertEqual(self.reinit(aut).status_code, 200)   # l'autorisation n'est pas brûlée par une faute de saisie

    def test_mot_de_passe_faible_refuse_avec_validateurs_django(self):
        aut = self.parcours_complet()
        for faible in ["12345678", "court", "motdepasse"]:
            r = self.reinit(aut, nouveau=faible)
            self.assertEqual(r.status_code, 400, faible)
            self.assertTrue(r.json()["details"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(MDP))

    def test_reinitialisation_leve_doit_changer_mdp(self):
        self.user.doit_changer_mdp = True
        self.user.save()
        self.assertEqual(self.reinit(self.parcours_complet()).status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.doit_changer_mdp)

    def test_anciens_jetons_invalides_apres_reinitialisation(self):
        refresh = RefreshVersionne.for_user(self.user)
        access = str(refresh.access_token)
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 200)
        self.assertEqual(self.reinit(self.parcours_complet()).status_code, 200)
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 401)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": str(refresh)}, format="json").status_code, 401)

    def test_nouveau_mot_de_passe_permet_la_connexion_et_l_ancien_non(self):
        self.reinit(self.parcours_complet())
        self.assertEqual(APIClient().post("/api/auth/login/", {"telephone": f"+227{NUM}", "password": NOUVEAU}, format="json").status_code, 200)
        self.assertNotEqual(APIClient().post("/api/auth/login/", {"telephone": f"+227{NUM}", "password": MDP}, format="json").status_code, 200)

    def test_autres_utilisateurs_non_affectes(self):
        autre = User.objects.create_user(f"+227{NUM2}", MDP, statut="actif")
        jeton = str(RefreshVersionne.for_user(autre).access_token)
        self.reinit(self.parcours_complet())
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {jeton}").status_code, 200)


@override_settings(**SOUS_TEST)
class ChangementVolontaireTests(Base):
    URL = "/api/auth/modifier-mot-de-passe/"

    def connecte(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshVersionne.for_user(self.user).access_token}")
        return c

    def corps(self, **kw):
        base = {"mot_de_passe_actuel": MDP, "nouveau_mot_de_passe": NOUVEAU, "confirmation": NOUVEAU}
        base.update(kw)
        return base

    def test_non_authentifie(self):
        self.assertEqual(APIClient().post(self.URL, self.corps(), format="json").status_code, 401)

    def test_succes_renvoie_de_nouveaux_jetons_valides(self):
        c = self.connecte()
        ancien = c._credentials["HTTP_AUTHORIZATION"]
        r = c.post(self.URL, self.corps(), format="json")
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NOUVEAU))
        neuf = APIClient()
        neuf.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
        self.assertEqual(neuf.get("/api/auth/me/").status_code, 200)
        vieux = APIClient()
        vieux.credentials(HTTP_AUTHORIZATION=ancien)
        self.assertEqual(vieux.get("/api/auth/me/").status_code, 401)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": r.json()["refresh"]}, format="json").status_code, 200)

    def test_mauvais_mot_de_passe_actuel(self):
        r = self.connecte().post(self.URL, self.corps(mot_de_passe_actuel="Faux-Mdp-0000"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("mot_de_passe_actuel", r.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(MDP))

    def test_champ_actuel_obligatoire(self):
        corps = self.corps()
        del corps["mot_de_passe_actuel"]
        self.assertEqual(self.connecte().post(self.URL, corps, format="json").status_code, 400)

    def test_verrouillage_apres_5_erreurs(self):
        c = self.connecte()
        for _ in range(5):
            self.assertEqual(c.post(self.URL, self.corps(mot_de_passe_actuel="Faux-Mdp-0000"), format="json").status_code, 400)
        r = c.post(self.URL, self.corps(), format="json")   # même le bon mot de passe est refusé pendant le verrouillage
        self.assertEqual(r.status_code, 429)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(MDP))

    def test_confirmation_differente_et_identique_a_l_actuel_et_faible(self):
        c = self.connecte()
        self.assertEqual(c.post(self.URL, self.corps(confirmation="Autre-1234-xx"), format="json").status_code, 400)
        self.assertEqual(c.post(self.URL, self.corps(nouveau_mot_de_passe=MDP, confirmation=MDP), format="json").status_code, 400)
        self.assertEqual(c.post(self.URL, self.corps(nouveau_mot_de_passe="12345678", confirmation="12345678"), format="json").status_code, 400)

    def test_compte_suspendu_refuse(self):
        c = self.connecte()
        self.user.statut = "suspendu"
        self.user.save()
        self.assertEqual(c.post(self.URL, self.corps(), format="json").status_code, 403)

    def test_ne_peut_pas_activer_doit_changer_mdp_ni_changer_un_autre_compte(self):
        autre = User.objects.create_user(f"+227{NUM2}", MDP, statut="actif")
        self.connecte().post(self.URL, {**self.corps(), "doit_changer_mdp": True, "id": autre.pk, "telephone": autre.telephone}, format="json")
        self.user.refresh_from_db(); autre.refresh_from_db()
        self.assertFalse(self.user.doit_changer_mdp)
        self.assertTrue(autre.check_password(MDP))


@override_settings(**SOUS_TEST)
class ChangementForceTests(Base):
    URL = "/api/auth/changer-mot-de-passe/"

    def auth(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshVersionne.for_user(self.user).access_token}")
        return c

    def test_refuse_si_aucun_changement_force(self):
        r = self.auth().post(self.URL, {"nouveau_mot_de_passe": NOUVEAU}, format="json")
        self.assertEqual(r.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(MDP))

    def test_force_fonctionne_et_renvoie_des_jetons(self):
        self.user.doit_changer_mdp = True
        self.user.save()
        r = self.auth().post(self.URL, {"nouveau_mot_de_passe": NOUVEAU}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.json())
        self.user.refresh_from_db()
        self.assertFalse(self.user.doit_changer_mdp)
        self.assertTrue(self.user.check_password(NOUVEAU))

    def test_non_authentifie(self):
        self.assertEqual(APIClient().post(self.URL, {"nouveau_mot_de_passe": NOUVEAU}, format="json").status_code, 401)


class JetonsHeritesTests(Base):
    def test_jeton_ancien_reste_valide_tant_que_le_mot_de_passe_n_a_pas_change(self):
        """Colonne vide = aucun utilisateur déconnecté au déploiement."""
        User.objects.filter(pk=self.user.pk).update(version_mot_de_passe=0)
        jeton = str(RefreshToken.for_user(self.user).access_token)   # jeton hérité : sans version
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {jeton}").status_code, 200)

    def test_reinitialisation_par_admin_invalide_les_jetons(self):
        jeton = str(RefreshVersionne.for_user(self.user).access_token)
        self.user.set_password("Admin-Reset-9912")
        self.user.save(update_fields=["password"])
        self.assertEqual(APIClient().get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {jeton}").status_code, 401)


def _en_tete(access):
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


@override_settings(**SOUS_TEST)
class JetonsMemeSecondeTests(Base):
    """L'`iat` n'a qu'une résolution d'une seconde : l'invalidation repose sur un compteur de version, pas sur l'horloge."""

    def changer(self, mdp):
        self.user.refresh_from_db()
        self.user.set_password(mdp)
        self.user.save(update_fields=["password"])

    def test_ancien_jeton_refuse_meme_emis_dans_la_meme_seconde_que_le_changement(self):
        ancien = RefreshVersionne.for_user(self.user)
        acces_ancien = str(ancien.access_token)
        self.changer("Autre-Mdp-1111")   # aucune attente : même seconde
        nouveau = RefreshVersionne.for_user(self.user)
        acces_nouveau = str(nouveau.access_token)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(acces_ancien)).status_code, 401)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(acces_nouveau)).status_code, 200)

    def test_resultat_independant_de_l_horodatage(self):
        """Même un jeton ancien dont l'iat est postérieur au changement est refusé : seule la version compte."""
        ancien = RefreshVersionne.for_user(self.user)
        acces = ancien.access_token
        self.changer("Autre-Mdp-1111")
        acces["iat"] = int(timezone.now().timestamp()) + 3600
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(str(acces))).status_code, 401)
        nouveau = RefreshVersionne.for_user(self.user).access_token
        nouveau["iat"] = 1   # et un jeton neuf dont l'iat est très ancien reste accepté
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(str(nouveau))).status_code, 200)

    def test_rafraichissement_de_l_ancien_jeton_refuse_meme_seconde(self):
        ancien = RefreshVersionne.for_user(self.user)
        self.changer("Autre-Mdp-1111")
        r = APIClient().post("/api/auth/refresh/", {"refresh": str(ancien)}, format="json")
        self.assertEqual(r.status_code, 401)

    def test_rafraichissement_du_nouveau_jeton_accepte_et_l_acces_obtenu_fonctionne(self):
        self.changer("Autre-Mdp-1111")
        nouveau = RefreshVersionne.for_user(self.user)
        r = APIClient().post("/api/auth/refresh/", {"refresh": str(nouveau)}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(r.json()["access"])).status_code, 200)

    def test_acces_issu_d_un_rafraichissement_herite_de_la_version(self):
        refresh = RefreshVersionne.for_user(self.user)
        acces = str(APIClient().post("/api/auth/refresh/", {"refresh": str(refresh)}, format="json").json()["access"])
        self.changer("Autre-Mdp-1111")
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(acces)).status_code, 401)

    def test_deux_changements_successifs_invalident_chaque_generation(self):
        premier = RefreshVersionne.for_user(self.user)
        self.changer("Autre-Mdp-1111")
        deuxieme = RefreshVersionne.for_user(self.user)
        self.changer("Encore-Mdp-2222")
        for jeton in (premier, deuxieme):
            self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": str(jeton)}, format="json").status_code, 401)
            self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(str(jeton.access_token))).status_code, 401)

    def test_version_falsifiee_refusee(self):
        jeton = RefreshVersionne.for_user(self.user)
        jeton["pv"] = 999
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": str(jeton)}, format="json").status_code, 401)
        jeton["pv"] = "abc"
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(str(jeton.access_token))).status_code, 401)

    def test_jeton_herite_sans_version_valide_puis_refuse_apres_changement(self):
        User.objects.filter(pk=self.user.pk).update(version_mot_de_passe=0)
        self.user.refresh_from_db()
        herite = RefreshToken.for_user(self.user)   # émis avant le déploiement : pas de revendication
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": str(herite)}, format="json").status_code, 200)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(str(herite.access_token))).status_code, 200)
        self.changer("Autre-Mdp-1111")
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": str(herite)}, format="json").status_code, 401)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(str(herite.access_token))).status_code, 401)

    def test_jeton_de_connexion_porte_la_version(self):
        r = APIClient().post("/api/auth/login/", {"telephone": f"+227{NUM}", "password": MDP}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(r.json()["access"])).status_code, 200)
        self.changer("Autre-Mdp-1111")
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(r.json()["access"])).status_code, 401)

    def test_changement_volontaire_meme_seconde_garde_l_appareil_courant_connecte(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshVersionne.for_user(self.user).access_token}")
        autre_appareil = str(RefreshVersionne.for_user(self.user).access_token)
        r = c.post("/api/auth/modifier-mot-de-passe/",
                   {"mot_de_passe_actuel": MDP, "nouveau_mot_de_passe": NOUVEAU, "confirmation": NOUVEAU}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(r.json()["access"])).status_code, 200)
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(autre_appareil)).status_code, 401)
        self.assertEqual(APIClient().post("/api/auth/refresh/", {"refresh": r.json()["refresh"]}, format="json").status_code, 200)

    def test_version_augmente_a_chaque_set_password_y_compris_update_fields(self):
        v0 = User.objects.get(pk=self.user.pk).version_mot_de_passe
        self.changer("Autre-Mdp-1111")
        self.assertEqual(User.objects.get(pk=self.user.pk).version_mot_de_passe, v0 + 1)

    def test_les_autres_utilisateurs_gardent_leurs_jetons(self):
        autre = User.objects.create_user(f"+227{NUM2}", MDP, statut="actif")
        jeton = str(RefreshVersionne.for_user(autre).access_token)
        self.changer("Autre-Mdp-1111")
        self.assertEqual(APIClient().get("/api/auth/me/", **_en_tete(jeton)).status_code, 200)


@override_settings(**SOUS_TEST)
class BudgetSegmentsTests(Base):
    def test_le_sms_standard_reserve_un_segment(self):
        self.demander()
        self.assertEqual(EnvoiCodeSms.objects.get().segments, 1)

    def test_budget_compte_les_segments_d_un_texte_long(self):
        with mock.patch("recuperation.services.texte_sms", return_value="x" * 200):   # GSM-7 : 2 segments
            with override_settings(OTP_PLAFOND_SMS_JOUR=3, OTP_PLAFOND_SMS_MOIS=100):
                self.assertEqual(self.demander().status_code, 200)
                self.assertEqual(EnvoiCodeSms.objects.get().segments, 2)
                self.avancer(seconds=120)
                self.assertEqual(self.demander().status_code, 503)   # 2 + 2 > 3
                self.assertEqual(len(self.envois), 1)

    def test_budget_compte_un_texte_unicode_en_segments_unicode(self):
        with mock.patch("recuperation.services.texte_sms", return_value="ê" * 100):   # hors GSM-7 : 2 segments
            self.demander()
        self.assertEqual(EnvoiCodeSms.objects.get().segments, 2)

    def test_budget_mensuel_en_segments(self):
        with mock.patch("recuperation.services.texte_sms", return_value="x" * 200):
            with override_settings(OTP_PLAFOND_SMS_JOUR=100, OTP_PLAFOND_SMS_MOIS=3):
                self.demander()
                self.avancer(seconds=120)
                self.assertEqual(self.demander().status_code, 503)

    def test_plafond_de_lancement_200_segments_par_mois_configurable(self):
        import pathlib
        source = (pathlib.Path(__file__).resolve().parent.parent / "config" / "settings.py").read_text(encoding="utf-8")
        self.assertRegex(source, r"OTP_PLAFOND_SMS_MOIS\s*=\s*config\('OTP_PLAFOND_SMS_MOIS',\s*default=200")
        self.assertNotRegex(source, r"OTP_[A-Z_]*(TARIF|FCFA|PRIX|COUT)")   # aucun tarif commercial en dur

    def test_numero_sans_compte_ne_consomme_aucun_segment(self):
        self.demander(NUM2)
        self.assertEqual(EnvoiCodeSms.objects.count(), 0)

    @override_settings(OTP_ATTENTE_MAX_SECONDES=3600)   # le retard simulé par avancer() n'est pas ce que ce test vérifie
    def test_envoi_perime_ou_remplace_est_rendu_au_budget(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")   # en attente, pas encore envoyé
        self.avancer(seconds=90)
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")   # remplace le premier avant tout envoi
        self.assertEqual(EnvoiCodeSms.objects.filter(etat="expire").count(), 1)
        self.assertEqual(services.segments_consommes(timezone.now() - timedelta(days=1)), 1)

    def test_echec_incertain_ou_accepte_consomment_le_budget(self):
        for resultat in [("accepte", "ok"), ("refuse", "http_400"), ("incertain", "x")]:
            EnvoiCodeSms.objects.all().delete()
            DemandeReinitialisation.objects.all().delete()
            EvenementRecuperation.objects.all().delete()
            self.resultat_fournisseur = resultat
            self.demander()
            self.assertEqual(services.segments_consommes(timezone.now() - timedelta(days=1)), 1, resultat)

    def test_echecs_repetes_ne_depassent_jamais_le_plafond_de_segments(self):
        self.resultat_fournisseur = ("refuse", "http_400")
        with override_settings(OTP_PLAFOND_SMS_JOUR=2, OTP_MAX_DEMANDES_PAR_NUMERO_HEURE=10):
            codes = []
            for _ in range(6):
                codes.append(self.demander().status_code)
                self.avancer(seconds=90)
        self.assertEqual(codes.count(200), 2)
        self.assertEqual(EnvoiCodeSms.objects.count(), 2)
        self.assertEqual(len(self.appels), 2)


@override_settings(**SOUS_TEST)
class FileEnvoiTests(Base):
    """Worker dédié : états, interruptions, doubles envois, résultats incertains."""

    def envoi(self):
        return EnvoiCodeSms.objects.get()

    def test_la_demande_programme_l_envoi_sans_rien_envoyer_ni_stocker(self):
        r = self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.envoi().etat, "en_attente")
        self.assertEqual(self.appels, [])   # la requête web n'envoie rien : c'est le worker
        e, d = self.envoi(), DemandeReinitialisation.objects.get()
        toutes = " ".join(str(v) for v in list(e.__dict__.values()) + list(d.__dict__.values()))
        self.assertNotIn("votre code", toutes)
        self.assertNotRegex(" ".join([e.detail, e.etat]), r"\d{6}")

    def test_envoi_accepte_avec_le_bon_code(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.assertEqual(self.traiter(), 1)
        e = self.envoi()
        self.assertEqual(e.etat, "accepte")
        self.assertEqual(len(self.envois), 1)
        self.assertEqual(self.envois[0][0], f"+227{NUM}")
        self.assertRegex(self.envois[0][1], r"^FAHIMTA : votre code de vérification est \d{6}\. Valable 5 minutes\.")
        self.assertEqual(self.verifier(self.code_envoye()).status_code, 200)   # le code reçu est bien le code attendu

    def test_pas_de_double_envoi_en_repassant_le_worker(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.traiter(); self.traiter(); self.traiter()
        self.assertEqual(len(self.appels), 1)

    def test_deux_workers_simultanes_un_seul_envoi(self):
        if connection.vendor != "postgresql":
            self.skipTest("SKIP LOCKED requiert PostgreSQL")
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        barriere = threading.Barrier(4)

        def worker():
            from django.db import connection as conn
            try:
                barriere.wait()
                with override_settings(**SOUS_TEST):
                    envoi.traiter_un()
            finally:
                conn.close()

        fils = [threading.Thread(target=worker) for _ in range(4)]
        [f.start() for f in fils]
        [f.join() for f in fils]
        self.assertEqual(len(self.appels), 1)
        self.assertEqual(self.envoi().etat, "accepte")

    def test_refus_definitif_pas_de_nouvel_essai(self):
        self.resultat_fournisseur = ("refuse", "http_400")
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.traiter(); self.traiter()
        self.assertEqual(self.envoi().etat, "echec")
        self.assertEqual(len(self.appels), 1)

    def test_rien_n_a_pu_partir_deux_essais_au_plus_puis_echec(self):
        self.resultat_fournisseur = ("non_envoye", "injoignable")
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.traiter()
        e = self.envoi()
        self.assertEqual((e.etat, e.tentatives), ("en_attente", 1))
        self.assertGreater(e.disponible_le, timezone.now())
        self.traiter()   # pas encore dû : aucun nouvel appel
        self.assertEqual(len(self.appels), 1)
        EnvoiCodeSms.objects.update(disponible_le=timezone.now() - timedelta(seconds=1))
        self.traiter()
        self.assertEqual((self.envoi().etat, self.envoi().tentatives), ("echec", 2))
        EnvoiCodeSms.objects.update(disponible_le=timezone.now() - timedelta(seconds=1))
        self.traiter()
        self.assertEqual(len(self.appels), 2)   # jamais plus que le maximum

    def test_resultat_incertain_jamais_renvoye(self):
        self.resultat_fournisseur = ("incertain", "reponse_inconnue")
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.traiter()
        EnvoiCodeSms.objects.update(disponible_le=timezone.now() - timedelta(minutes=1))
        self.traiter(); self.traiter()
        self.assertEqual(self.envoi().etat, "incertain")
        self.assertEqual(len(self.appels), 1)

    def test_exception_du_fournisseur_devient_incertain_sans_fuite(self):
        import logging
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        code = services.code_pour(DemandeReinitialisation.objects.get())
        with mock.patch("recuperation.envoi.envoyer_sms_detail", side_effect=RuntimeError(f"boom {code}")):
            with self.assertLogs(level="DEBUG") as logs:
                logging.getLogger("amorce").debug("amorce")
                self.traiter(); self.traiter()
        self.assertEqual(self.envoi().etat, "incertain")
        self.assertEqual(self.envoi().detail, "exception")
        self.assertFalse(any(code in ligne for ligne in logs.output))

    def test_worker_interrompu_ligne_en_cours_devient_incertaine_sans_renvoi(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        EnvoiCodeSms.objects.update(etat="en_cours", tentatives=1,
                                    debut_traitement_le=timezone.now() - timedelta(seconds=500))
        self.traiter(); self.traiter()
        self.assertEqual(self.envoi().etat, "incertain")
        self.assertEqual(self.envoi().detail, "interrompu")
        self.assertEqual(self.appels, [])

    def test_ligne_en_cours_recente_n_est_pas_touchee(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        EnvoiCodeSms.objects.update(etat="en_cours", tentatives=1, debut_traitement_le=timezone.now())
        self.traiter()
        self.assertEqual(self.envoi().etat, "en_cours")
        self.assertEqual(self.appels, [])

    def test_une_conclusion_tardive_n_ecrase_pas_un_etat_deja_fige(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        e = self.envoi()
        EnvoiCodeSms.objects.update(etat="incertain")
        envoi._conclure(e, "accepte", "ok")
        self.assertEqual(self.envoi().etat, "incertain")

    def test_code_perime_expire_sans_envoi(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        EnvoiCodeSms.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
        self.traiter()
        self.assertEqual(self.envoi().etat, "expire")
        self.assertEqual(self.appels, [])

    def test_demande_cloturee_avant_envoi_pas_de_sms(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        DemandeReinitialisation.objects.update(cloturee_le=timezone.now(), cloture_motif="epuisee")
        self.traiter()
        self.assertEqual(self.envoi().etat, "expire")
        self.assertEqual(self.appels, [])

    @override_settings(OTP_ATTENTE_MAX_SECONDES=3600)   # le retard simulé par avancer() n'est pas ce que ce test vérifie
    def test_nouvelle_demande_expire_l_ancien_envoi_en_attente(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        self.avancer(seconds=90)
        self.demander()
        etats = sorted(EnvoiCodeSms.objects.values_list("etat", flat=True))
        self.assertEqual(etats, ["accepte", "expire"])
        self.assertEqual(len(self.appels), 1)   # seul le code valable est envoyé

    def test_service_desactive_le_worker_n_envoie_rien(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        with override_settings(OTP_SMS_ACTIFS=False):
            self.assertEqual(envoi.passage_envoi_otp(), 0)
        self.assertEqual(self.envoi().etat, "en_attente")
        self.assertEqual(self.appels, [])

    def test_secret_absent_ou_trop_court_service_indisponible_et_worker_inactif(self):
        for secret in ["", "court"]:
            with override_settings(OTP_CLE_SECRETE=secret):
                r = self.c.post(URL_DEM, {"telephone": NUM}, format="json")
                self.assertEqual(r.status_code, 503)
                self.assertEqual(envoi.passage_envoi_otp(), 0)
        self.assertEqual(EnvoiCodeSms.objects.count(), 0)

    def test_commande_une_fois_et_etat(self):
        from io import StringIO
        from django.core.management import call_command
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        sortie = StringIO()
        with override_settings(**SOUS_TEST):
            call_command("traiter_envoi_codes_otp", "--etat", stdout=sortie)
            self.assertIn("en_attente : 1", sortie.getvalue())
            self.assertEqual(len(self.appels), 0)   # --etat est en lecture seule
            call_command("traiter_envoi_codes_otp", "--une-fois", stdout=sortie)
        self.assertEqual(len(self.appels), 1)

    def test_boucle_permanente_traite_puis_s_arrete_proprement(self):
        from io import StringIO
        from django.core.management import call_command

        class FauxEvenement:
            def __init__(self):
                self.tours = 0

            def set(self):
                self.tours = 99

            def is_set(self):
                return self.tours >= 2

            def wait(self, secondes):
                self.tours += 1

        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        sortie = StringIO()
        with override_settings(**SOUS_TEST), mock.patch(
                "recuperation.management.commands.traiter_envoi_codes_otp.threading.Event", FauxEvenement):
            call_command("traiter_envoi_codes_otp", stdout=sortie)
        self.assertEqual(len(self.appels), 1)
        self.assertIn("arrêté proprement", sortie.getvalue())

    def test_worker_independant_des_autres_workers(self):
        import pathlib
        racine = pathlib.Path(__file__).resolve().parent
        for fichier in [racine / "envoi.py", racine / "management" / "commands" / "traiter_envoi_codes_otp.py"]:
            source = fichier.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"(?m)^\s*(from|import)\s+(communications|programme)")   # aucun import des autres workers
        procfile = (racine.parent / "Procfile").read_text(encoding="utf-8")
        lignes = [ligne for ligne in procfile.splitlines() if ligne.startswith("otp:")]
        self.assertEqual(lignes, ["otp: python manage.py traiter_envoi_codes_otp"])


@override_settings(**SOUS_TEST)
class IndisponibiliteTests(Base):
    def reponses(self):
        a = self.c.post(URL_DEM, {"telephone": NUM}, format="json")      # compte existant
        b = self.c.post(URL_DEM, {"telephone": "90555666"}, format="json")  # aucun compte
        return a, b

    def test_worker_silencieux_informe_l_eleve_sans_reveler_le_compte(self):
        BattementWorkerOtp.objects.update(dernier_battement=timezone.now() - timedelta(seconds=600))
        a, b = self.reponses()
        self.assertEqual((a.status_code, b.status_code), (503, 503))
        self.assertEqual(a.json(), b.json())
        self.assertIn("temporairement indisponible", a.json()["detail"])
        self.assertEqual(EvenementRecuperation.objects.count(), 0)   # aucune limite consommée
        self.assertEqual(EnvoiCodeSms.objects.count(), 0)

    def test_aucun_battement_jamais_recu(self):
        BattementWorkerOtp.objects.all().delete()
        self.assertEqual(self.c.post(URL_DEM, {"telephone": NUM}, format="json").status_code, 503)

    def test_le_worker_rend_le_service_disponible(self):
        BattementWorkerOtp.objects.update(dernier_battement=timezone.now() - timedelta(seconds=600))
        self.assertEqual(self.c.post(URL_DEM, {"telephone": NUM}, format="json").status_code, 503)
        self.traiter()   # un passage du worker donne un signe de vie
        self.assertEqual(self.c.post(URL_DEM, {"telephone": NUM}, format="json").status_code, 200)

    def test_file_en_retard_indisponible(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        EnvoiCodeSms.objects.update(cree_le=timezone.now() - timedelta(seconds=300))
        a, b = self.reponses()
        self.assertEqual((a.status_code, b.status_code), (503, 503))
        self.assertEqual(a.json(), b.json())

    def test_budget_epuise_meme_reponse_pour_tous_les_numeros(self):
        with override_settings(OTP_PLAFOND_SMS_MOIS=0):
            a, b = self.reponses()
        self.assertEqual((a.status_code, b.status_code), (503, 503))
        self.assertEqual(a.json(), b.json())

    def test_service_desactive_meme_reponse_pour_tous_les_numeros(self):
        with override_settings(OTP_SMS_ACTIFS=False):
            a, b = self.reponses()
        self.assertEqual(a.json(), b.json())


@override_settings(**SOUS_TEST)
class CodeReconstituableTests(Base):
    def test_code_deterministe_pour_une_demande_et_propre_a_chaque_sel(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        d = DemandeReinitialisation.objects.get()
        self.assertEqual(services.code_pour(d), services.code_pour(d))
        self.assertRegex(services.code_pour(d), r"^\d{6}$")
        autre = DemandeReinitialisation(pk=d.pk, utilisateur=d.utilisateur, sel="0" * 32, expire_le=d.expire_le)
        self.assertNotEqual(services.code_pour(d), services.code_pour(autre))   # (collision 1 sur 10^6, négligeable)

    def test_autre_secret_autre_code_donc_inutile_sans_le_secret(self):
        self.c.post(URL_DEM, {"telephone": NUM}, format="json")
        d = DemandeReinitialisation.objects.get()
        avant = services.code_pour(d)
        with override_settings(OTP_CLE_SECRETE="un-tout-autre-secret-de-test-0123456789ab"):
            self.assertNotEqual(services.code_pour(d), avant)

    def test_sel_unique_par_demande(self):
        self.demander()
        self.avancer(seconds=90)
        self.demander()
        sels = list(DemandeReinitialisation.objects.values_list("sel", flat=True))
        self.assertEqual(len(sels), 2)
        self.assertEqual(len(set(sels)), 2)

    def test_vrai_code_verifie_faux_code_refuse(self):
        self.demander()
        vrai = services.code_pour(DemandeReinitialisation.objects.get())
        faux = "000000" if vrai != "000000" else "111111"
        self.assertEqual(self.verifier(faux).status_code, 400)
        self.assertEqual(self.verifier(vrai).status_code, 200)

    def test_verification_sans_secret_en_production_indisponible(self):
        self.demander()
        vrai = services.code_pour(DemandeReinitialisation.objects.get())
        with override_settings(OTP_CLE_SECRETE=""):
            self.assertEqual(self.verifier(vrai).status_code, 503)


class ParametresParDefautTests(TransactionTestCase):
    def test_otp_desactive_par_defaut_dans_les_reglages(self):
        """Le défaut du code est faux ; seul un réglage d'environnement explicite peut l'activer."""
        import pathlib
        import re as _re

        source = (pathlib.Path(__file__).resolve().parent.parent / "config" / "settings.py").read_text(encoding="utf-8")
        self.assertRegex(source, _re.compile(r"OTP_SMS_ACTIFS\s*=\s*config\('OTP_SMS_ACTIFS',\s*default=False"))

    def test_sans_activation_aucune_demande_n_appelle_le_fournisseur(self):
        with override_settings(OTP_SMS_ACTIFS=False), mock.patch("recuperation.envoi.envoyer_sms_detail") as faux:
            User.objects.create_user("+22790777888", MDP, statut="actif")
            r = APIClient().post(URL_DEM, {"telephone": "90777888"}, format="json")
        self.assertEqual(r.status_code, 503)
        faux.assert_not_called()
