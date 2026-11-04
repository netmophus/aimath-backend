from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from comptes.models import User
from communications import fournisseurs, services
from communications.models import Campagne, MessageSms, ParametresCommunication, PreferenceCommunication
from communications.segments import compter

BASE = "/api/admin/communications/"
LIEN = "https://chat.whatsapp.com/ABCDEFGHIJKL"
ACTIF = dict(COMMUNICATIONS_SMS_ACTIVES=True, COMMUNICATIONS_FOURNISSEUR="simule")


def user(tel, role=User.Role.ELEVE, statut=User.Statut.ACTIF, prenom="Aicha", **extra):
    return User.objects.create_user(tel, password="Motdepasse-2026", prenom=prenom, nom="Test", role=role, statut=statut, **extra)


class Base(TestCase):
    def setUp(self):
        self.admin = user("+22790000001", User.Role.ADMIN, prenom="Admin")
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.cpt = 0
        p = ParametresCommunication.charger()
        p.plafond_mensuel_fcfa = 1000
        p.cout_segment_fcfa = Decimal("10")
        p.lien_whatsapp = LIEN
        p.save()

    def cle(self):
        self.cpt += 1
        return f"cle-test-{self.cpt:04d}"

    def apercu(self, ids=None, mode="ids", texte="Bonjour {prenom}, info.", type_="sms", filtres=None, cle=None):
        return self.api.post(BASE + "campagnes/apercu/", {
            "cle": cle or self.cle(), "type": type_, "texte": texte, "mode": mode, "ids": ids or [], "filtres": filtres or {},
        }, format="json")

    def confirmer(self, cid, **extra):
        return self.api.post(f"{BASE}campagnes/{cid}/confirmer/", extra, format="json")


class Segmentation(TestCase):
    def test_gsm7_et_unicode(self):
        self.assertEqual(compter("a" * 160)["segments"], 1)
        self.assertEqual(compter("a" * 161)["segments"], 2)
        self.assertEqual(compter("é" * 160)["segments"], 1)          # é est dans GSM-7
        self.assertTrue(compter("ê")["unicode"])                       # ê ne l'est pas
        self.assertEqual(compter("ê" * 71)["segments"], 2)
        self.assertEqual(compter("{" * 81)["segments"], 2)             # caractère étendu : compte double
        self.assertEqual(compter("")["segments"], 0)


class Permissions(Base):
    def test_refus_eleve_et_anonyme(self):
        eleve = user("+22790000002")
        c = APIClient()
        for chemin in ("parametres/", "campagnes/", "messages/", "modeles/", "statut-activation/"):
            self.assertEqual(c.get(BASE + chemin).status_code, 401)
        c.force_authenticate(eleve)
        for chemin in ("parametres/", "campagnes/", "messages/", "modeles/", "statut-activation/?ids=1"):
            self.assertEqual(c.get(BASE + chemin).status_code, 403, chemin)
        self.assertEqual(c.post(BASE + "campagnes/apercu/", {}, format="json").status_code, 403)
        self.assertEqual(c.post(f"{BASE}campagnes/1/confirmer/", {}, format="json").status_code, 403)
        self.assertEqual(c.patch(BASE + "parametres/", {"plafond_mensuel_fcfa": 9}, format="json").status_code, 403)

    def test_refus_vendeur_et_enseignant(self):
        for role in (User.Role.VENDEUR, User.Role.ENSEIGNANT):
            c = APIClient()
            c.force_authenticate(user(f"+2279100{role[:3].encode().hex()[:4]}"[:13], role))
            self.assertEqual(c.get(BASE + "campagnes/").status_code, 403)


class ApercuEtDestinataires(Base):
    def test_apercu_ne_cree_aucun_envoi(self):
        a, b = user("+22790000011"), user("+22790000012", prenom="Moussa")
        with mock.patch("requests.post") as post, mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            r = self.apercu([a.id, b.id])
        self.assertEqual(r.status_code, 201)
        d = r.json()
        self.assertEqual((d["nb_comptes"], d["nb_destinataires"], d["statut"]), (2, 2, "apercu"))
        self.assertEqual(d["texte"], "Bonjour {prenom}, info.")
        self.assertEqual(d["texte_exemple"], "Bonjour Aicha, info.")
        self.assertEqual(d["segments_total"], 2)
        self.assertEqual(Decimal(d["cout_estime"]), Decimal("20"))
        post.assert_not_called()
        env.assert_not_called()
        self.assertEqual(self.api.get(BASE + "campagnes/").json()["count"], 0)   # un aperçu n'est pas dans l'historique

    def test_exclusions_et_deduplication_par_numero_normalise(self):
        ok = user("+22790000021")
        user("+22790000022", statut=User.Statut.EN_ATTENTE)
        user("+22790000023", statut=User.Statut.REJETE)
        user("+22790000024", statut=User.Statut.SUSPENDU)
        mauvais = user("+22790000025")
        User.objects.filter(id=mauvais.id).update(telephone="+2279123")          # numéro invalide
        double = user("+22790000026")
        User.objects.filter(id=double.id).update(telephone="22790000021")         # même numéro que `ok`, autre écriture
        opp = user("+22790000027")
        PreferenceCommunication.objects.create(utilisateur=opp, opposition_facultatif=True)
        d = self.apercu(mode="tous").json()
        self.assertEqual(d["nb_comptes"], User.objects.count())
        ex = d["exclusions"]
        self.assertEqual(ex["statut_non_actif"], 3)
        self.assertEqual(ex["numero_invalide"], 1)
        self.assertEqual(ex["doublon"], 1)
        self.assertEqual(ex["opposition"], 1)
        # admin + ok sont retenus (le doublon l'est une seule fois)
        self.assertEqual(d["nb_destinataires"], 2)
        camp = Campagne.objects.get(id=d["id"])
        self.assertIn(ok.id, list(camp.messages.values_list("utilisateur_id", flat=True)))

    def test_filtres_et_identifiants_reels(self):
        e1, e2 = user("+22790000031"), user("+22790000032")
        ens = user("+22790000033", User.Role.ENSEIGNANT)
        d = self.apercu(mode="filtres", filtres={"role": "eleve", "statut": "actif"}).json()
        self.assertEqual(d["nb_destinataires"], 2)
        d = self.apercu(mode="filtres", filtres={"role": "enseignant"}).json()
        self.assertEqual(d["nb_destinataires"], 1)
        d = self.apercu(mode="filtres", filtres={"search": "+2279000003"}).json()
        self.assertEqual(d["nb_destinataires"], 3)
        d = self.apercu(ids=[e2.id, 999999]).json()     # un identifiant inconnu est ignoré
        self.assertEqual((d["nb_comptes"], d["nb_destinataires"]), (1, 1))
        self.assertTrue(Campagne.objects.get(id=d["id"]).messages.filter(utilisateur=e2).exists())
        self.assertNotIn(e1.id, [])

    def test_les_numeros_viennent_du_serveur_pas_du_navigateur(self):
        a = user("+22790000041")
        r = self.api.post(BASE + "campagnes/apercu/", {
            "cle": self.cle(), "type": "sms", "texte": "Bonjour", "mode": "ids", "ids": [a.id],
            "telephones": ["+22799999999"]}, format="json")
        self.assertEqual(r.status_code, 201)
        camp = Campagne.objects.get(id=r.json()["id"])
        self.assertEqual(list(camp.messages.values_list("telephone_masque", flat=True)), ["+227****041"])

    def test_confidentialite_telephones_masques(self):
        a = user("+22790000042")
        d = self.apercu([a.id]).json()
        self.confirmer_si_possible = None
        with override_settings(**ACTIF):
            self.confirmer(d["id"])
        liste = self.api.get(BASE + "messages/?campagne=%d" % d["id"]).json()["results"]
        self.assertEqual(liste[0]["telephone"], "+227****042")
        self.assertNotIn("90000042", str(liste))

    def test_validation_du_texte(self):
        a = user("+22790000051")
        for texte in ("", "x" * 481, "Salut {inconnue}", "Salut {", "Votre mot de passe : abc12345", "Jeton eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijk",
                      "Lien {lien}"):
            self.assertEqual(self.apercu([a.id], texte=texte).status_code, 400, texte)
        self.assertEqual(self.apercu([a.id], texte="Bonjour {prenom}").status_code, 201)

    def test_message_final_trop_long_refuse(self):
        a = user("+22790000052")
        self.assertEqual(self.apercu([a.id], texte="ê" * 450).status_code, 400)     # Unicode : plus de 6 segments


class Confirmation(Base):
    def test_confirmation_explicite_requise_rien_ne_part_sans(self):
        a = user("+22790000061")
        d = self.apercu([a.id]).json()
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            self.assertEqual(services.traiter_lot(), 0)       # l'aperçu seul n'est jamais traité
            env.assert_not_called()
        self.assertEqual(Campagne.objects.get(id=d["id"]).statut, "apercu")

    def test_interrupteur_global_par_defaut_desactive(self):
        a = user("+22790000062")
        d = self.apercu([a.id]).json()
        r = self.confirmer(d["id"])
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["code"], "envois_desactives")
        self.assertEqual(Campagne.objects.get(id=d["id"]).statut, "apercu")
        with override_settings(COMMUNICATIONS_SMS_ACTIVES=False), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            self.assertEqual(services.traiter_lot(), 0)
            env.assert_not_called()

    def test_idempotence_confirmation_et_apercu(self):
        a = user("+22790000063")
        cle = self.cle()
        d1 = self.apercu([a.id], cle=cle)
        d2 = self.apercu([a.id], cle=cle)
        self.assertEqual((d1.status_code, d2.status_code), (201, 200))
        self.assertEqual(d1.json()["id"], d2.json()["id"])
        self.assertEqual(Campagne.objects.count(), 1)
        cid = d1.json()["id"]
        with override_settings(**ACTIF):
            r1, r2 = self.confirmer(cid), self.confirmer(cid)
            self.assertFalse(r1.json()["deja_confirmee"])
            self.assertTrue(r2.json()["deja_confirmee"])
            services.traiter_lot()
            services.traiter_lot()
        m = MessageSms.objects.get(campagne_id=cid)
        self.assertEqual((m.statut, m.tentatives), ("accepte", 1))        # jamais envoyé deux fois

    def test_un_autre_admin_ne_confirme_pas_la_campagne(self):
        a = user("+22790000064")
        d = self.apercu([a.id]).json()
        autre = user("+22790000099", User.Role.ADMIN)
        c = APIClient(); c.force_authenticate(autre)
        with override_settings(**ACTIF):
            self.assertEqual(c.post(f"{BASE}campagnes/{d['id']}/confirmer/", {}, format="json").status_code, 404)

    def test_apercu_expire(self):
        a = user("+22790000065")
        d = self.apercu([a.id]).json()
        Campagne.objects.filter(id=d["id"]).update(cree_le=timezone.now() - timedelta(hours=3))
        with override_settings(**ACTIF):
            r = self.confirmer(d["id"])
        self.assertEqual((r.status_code, r.json()["code"]), (409, "apercu_expire"))

    def test_plafond_budgetaire_reverifie_a_la_confirmation(self):
        users = [user(f"+2279001{i:04d}") for i in range(6)]
        p = ParametresCommunication.charger()
        p.plafond_mensuel_fcfa = 50          # 5 SMS à 10 FCFA
        p.save()
        d1 = self.apercu([u.id for u in users[:3]]).json()     # 30
        d2 = self.apercu([u.id for u in users[3:]]).json()     # 30 : à eux deux 60 > 50
        with override_settings(**ACTIF):
            self.assertEqual(self.confirmer(d1["id"]).status_code, 200)
            r = self.confirmer(d2["id"])
        self.assertEqual((r.status_code, r.json()["code"]), (409, "plafond_depasse"))
        self.assertEqual(Campagne.objects.get(id=d2["id"]).statut, "apercu")

    def test_plafond_ou_tarif_absent_refuse(self):
        a = user("+22790000066")
        d = self.apercu([a.id]).json()
        with override_settings(**ACTIF):
            ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=0)
            self.assertEqual(self.confirmer(d["id"]).json()["code"], "plafond_absent")
            ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=500, cout_segment_fcfa=None)
            d2 = self.apercu([a.id]).json()
            self.assertIsNone(d2["cout_estime"])
            self.assertEqual(self.confirmer(d2["id"]).json()["code"], "tarif_absent")

    def test_aucun_destinataire(self):
        user("+22790000067", statut=User.Statut.EN_ATTENTE)
        d = self.apercu(mode="filtres", filtres={"statut": "en_attente"}).json()
        with override_settings(**ACTIF):
            self.assertEqual(self.confirmer(d["id"]).json()["code"], "aucun_destinataire")


class Envoi(Base):
    def lancer(self, ids, **kw):
        d = self.apercu(ids, **kw).json()
        with override_settings(**ACTIF):
            self.assertEqual(self.confirmer(d["id"], **({"attestation_consentement": True} if kw.get("type_") == "invitation_whatsapp" else {})).status_code, 200)
        return d["id"]

    def test_envoi_simule_par_lots_et_cloture(self):
        us = [user(f"+2279002{i:04d}") for i in range(5)]
        cid = self.lancer([u.id for u in us])
        with override_settings(**ACTIF, COMMUNICATIONS_LOT=2):
            self.assertEqual(services.traiter_lot(), 2)
            self.assertEqual(Campagne.objects.get(id=cid).statut, "en_cours")
            self.assertEqual(services.traiter_lot(), 2)
            self.assertEqual(services.traiter_lot(), 1)
        c = Campagne.objects.get(id=cid)
        self.assertEqual(c.statut, "terminee")
        self.assertEqual(c.messages.filter(statut="accepte").count(), 5)
        d = self.api.get(f"{BASE}campagnes/{cid}/").json()
        self.assertIsNone(d["livres"])                         # jamais de "livré" sans information du fournisseur
        self.assertNotIn("livre", d["messages"])

    def test_aucun_appel_reseau_avec_le_fournisseur_simule(self):
        a = user("+22790000071")
        with mock.patch("requests.post") as post:
            self.lancer([a.id])
            with override_settings(**ACTIF):
                services.traiter_lot()
        post.assert_not_called()

    def test_personnalisation_prenom_par_destinataire(self):
        a, b = user("+22790000072", prenom="Aicha"), user("+22790000073", prenom="Moussa")
        envoyes = []
        with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=lambda n, t: (envoyes.append((n, t)), ("accepte", "x"))[1]):
            self.lancer([a.id, b.id], texte="Salut {prenom}.")
            with override_settings(**ACTIF):
                services.traiter_lot()
        self.assertEqual(sorted(t for _, t in envoyes), ["Salut Aicha.", "Salut Moussa."])

    def test_erreur_fournisseur_echec_puis_reprise_controlee(self):
        a = user("+22790000074")
        cid = self.lancer([a.id])
        with override_settings(**ACTIF):
            with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", return_value=("refuse", "http_500")):
                services.traiter_lot()
            m = MessageSms.objects.get(campagne_id=cid)
            self.assertEqual((m.statut, m.dernier_code), ("echec", "http_500"))
            self.assertEqual(Campagne.objects.get(id=cid).statut, "terminee")
            r = self.api.post(f"{BASE}campagnes/{cid}/relancer-echecs/")
            self.assertEqual(r.status_code, 200)
            services.traiter_lot()
        m.refresh_from_db()
        self.assertEqual((m.statut, m.tentatives), ("accepte", 2))
        self.assertEqual(m.historique.count(), 2)

    def test_resultat_incertain_jamais_renvoye(self):
        a = user("+22790000075")
        cid = self.lancer([a.id])
        with override_settings(**ACTIF):
            with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", return_value=("incertain", "reponse_inconnue")):
                services.traiter_lot()
            self.assertEqual(MessageSms.objects.get(campagne_id=cid).statut, "incertain")
            self.assertEqual(self.api.post(f"{BASE}campagnes/{cid}/relancer-echecs/").status_code, 409)   # rien en échec
            with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
                services.traiter_lot()
                env.assert_not_called()

    def test_exception_du_fournisseur_donne_incertain(self):
        a = user("+22790000076")
        cid = self.lancer([a.id])
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=RuntimeError("boom")):
            services.traiter_lot()
        self.assertEqual(MessageSms.objects.get(campagne_id=cid).statut, "incertain")

    def test_reprise_apres_interruption_du_worker(self):
        a = user("+22790000077")
        cid = self.lancer([a.id])
        MessageSms.objects.filter(campagne_id=cid).update(statut="en_cours", tentatives=1, mis_a_jour_le=timezone.now() - timedelta(hours=1))
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            services.traiter_lot()
            env.assert_not_called()                      # pas de renvoi automatique d'un message dont l'issue est inconnue
        m = MessageSms.objects.get(campagne_id=cid)
        self.assertEqual((m.statut, m.dernier_code), ("incertain", "interrompu"))
        self.assertEqual(Campagne.objects.get(id=cid).statut, "terminee")

    def test_arret_de_campagne(self):
        us = [user(f"+2279003{i:04d}") for i in range(4)]
        cid = self.lancer([u.id for u in us])
        with override_settings(**ACTIF, COMMUNICATIONS_LOT=1):
            services.traiter_lot()
            r = self.api.post(f"{BASE}campagnes/{cid}/arreter/")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(services.traiter_lot(), 0)
        c = Campagne.objects.get(id=cid)
        self.assertEqual(c.statut, "arretee")
        self.assertEqual(c.messages.filter(statut="accepte").count(), 1)
        self.assertEqual(c.messages.filter(statut="annule").count(), 3)
        self.assertEqual(self.api.post(f"{BASE}campagnes/{cid}/arreter/").status_code, 409)

    def test_compte_suspendu_entre_apercu_et_envoi_est_ignore(self):
        a = user("+22790000078")
        cid = self.lancer([a.id])
        User.objects.filter(id=a.id).update(statut="suspendu")
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            services.traiter_lot()
            env.assert_not_called()
        self.assertEqual(MessageSms.objects.get(campagne_id=cid).statut, "ignore")

    def test_le_worker_ne_traite_que_les_campagnes_confirmees(self):
        a = user("+22790000079")
        self.apercu([a.id])
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            self.assertEqual(services.traiter_lot(), 0)
            env.assert_not_called()

    def test_commande_worker_une_fois(self):
        a = user("+22790000080")
        cid = self.lancer([a.id])
        with override_settings(**ACTIF, COMMUNICATIONS_DEBIT_PAR_MINUTE=100000):
            call_command("traiter_communications", "--une-fois")
        self.assertEqual(MessageSms.objects.get(campagne_id=cid).statut, "accepte")


class Fournisseurs(TestCase):
    @override_settings(SMS_MOCK=False, LAM_SMS_URL="https://exemple.invalide/api", LAM_ACCOUNTID="", LAM_PASSWORD="", LAM_DEFAULT_SENDER="")
    def test_lam_sans_configuration_n_envoie_rien(self):
        with mock.patch("requests.post") as post:
            self.assertEqual(fournisseurs.FournisseurLam().envoyer("22790000000", "x"), ("non_envoye", "config_incomplete"))
        post.assert_not_called()

    @override_settings(SMS_MOCK=False, LAM_SMS_URL="https://exemple.invalide/api", LAM_ACCOUNTID="a", LAM_PASSWORD="b", LAM_DEFAULT_SENDER="F")
    def test_lam_issues_distinguees(self):
        import requests
        cas = [
            (mock.Mock(ok=True, status_code=200), None, ("accepte", "http_ok")),
            (mock.Mock(ok=False, status_code=500), None, ("refuse", "http_500")),
            (None, requests.ConnectTimeout(), ("non_envoye", "injoignable")),
            (None, requests.ReadTimeout(), ("incertain", "reponse_inconnue")),
        ]
        for reponse, erreur, attendu in cas:
            with mock.patch("requests.post", return_value=reponse, side_effect=erreur):
                self.assertEqual(fournisseurs.FournisseurLam().envoyer("22790000000", "x"), attendu)

    @override_settings(COMMUNICATIONS_FOURNISSEUR="inconnu")
    def test_fournisseur_inconnu_retombe_sur_le_simule(self):
        self.assertEqual(fournisseurs.obtenir_fournisseur().nom, "simule")

    def test_defauts_securises(self):
        from django.conf import settings
        self.assertFalse(settings.COMMUNICATIONS_SMS_ACTIVES)
        self.assertEqual(settings.COMMUNICATIONS_FOURNISSEUR, "simule")


class ActivationSansSmsAutomatique(Base):
    def test_approuver_n_envoie_aucun_sms_et_ne_cree_aucune_campagne(self):
        en_attente = user("+22790000090", statut=User.Statut.EN_ATTENTE)
        with override_settings(**ACTIF), mock.patch("requests.post") as post, mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
            r = self.api.post(f"/api/admin/comptes/{en_attente.id}/approuver/")
            services.traiter_lot()
        self.assertEqual(r.status_code, 200)
        en_attente.refresh_from_db()
        self.assertEqual(en_attente.statut, "actif")
        post.assert_not_called()
        env.assert_not_called()
        self.assertEqual(Campagne.objects.count(), 0)
        self.assertEqual(MessageSms.objects.count(), 0)
        self.assertEqual(self.api.get(f"{BASE}statut-activation/?ids={en_attente.id}").json(), {str(en_attente.id): "non_envoye"})

    def test_notification_manuelle_apres_activation_et_indicateur(self):
        u = user("+22790000091")
        modele = next(m for m in services.MODELES if m["code"] == "activation")["texte"]
        ind = lambda: self.api.get(f"{BASE}statut-activation/?ids={u.id}").json()[str(u.id)]
        d = self.apercu([u.id], type_="activation", texte=modele).json()
        self.assertEqual(d["categorie"], "service")
        self.assertEqual(ind(), "non_envoye")                   # un aperçu n'est pas un envoi
        with override_settings(**ACTIF):
            self.confirmer(d["id"])
            self.assertEqual(ind(), "en_attente")
            services.traiter_lot()
        self.assertEqual(ind(), "envoye")
        # autre campagne en échec : l'indicateur reflète le dernier état
        d = self.apercu([u.id], type_="activation", texte=modele).json()
        with override_settings(**ACTIF), mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", return_value=("refuse", "http_500")):
            self.confirmer(d["id"])
            services.traiter_lot()
        self.assertEqual(ind(), "echec")

    def test_activation_un_seul_compte(self):
        a, b = user("+22790000092"), user("+22790000093")
        self.assertEqual(self.apercu([a.id, b.id], type_="activation", texte="Bonjour").status_code, 400)
        self.assertEqual(self.apercu(mode="tous", type_="activation", texte="Bonjour").status_code, 400)

    def test_notification_de_service_ignore_l_opposition_aux_messages_facultatifs(self):
        u = user("+22790000094")
        PreferenceCommunication.objects.create(utilisateur=u, opposition_facultatif=True)
        d = self.apercu([u.id], type_="activation", texte="Bonjour").json()
        self.assertEqual(d["nb_destinataires"], 1)
        d = self.apercu([u.id], type_="sms", texte="Promo").json()
        self.assertEqual((d["nb_destinataires"], d["exclusions"]["opposition"]), (0, 1))


class InvitationWhatsApp(Base):
    def majeur(self, tel, consent=True):
        u = user(tel, date_naissance=date.today().replace(year=date.today().year - 25))
        if consent:   # opt-in explicite de l'élève : sans lui, aucune invitation
            PreferenceCommunication.objects.create(utilisateur=u, invitations_whatsapp=True)
        return u

    def test_lien_configurable_valide_et_jamais_dans_le_texte_stocke(self):
        r = self.api.patch(BASE + "parametres/", {"lien_whatsapp": "http://exemple.com/x"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.patch(BASE + "parametres/", {"lien_whatsapp": "https://chat.whatsapp.com/NOUVEAUGROUPE"}, format="json")
        self.assertEqual(r.json()["lien_whatsapp"], "https://chat.whatsapp.com/NOUVEAUGROUPE")
        self.assertFalse(r.json()["envois_actifs"])

    def test_apercu_affiche_le_texte_exact_avec_le_lien(self):
        a = self.majeur("+22790000101")
        modele = next(m for m in services.MODELES if m["code"] == "invitation_whatsapp")["texte"]
        d = self.apercu([a.id], type_="invitation_whatsapp", texte=modele).json()
        self.assertIn(LIEN, d["texte_exemple"])
        self.assertIn("visible des autres membres", d["texte_exemple"])
        self.assertIn("{lien}", d["texte"])

    def test_lien_non_configure_refuse(self):
        ParametresCommunication.objects.filter(pk=1).update(lien_whatsapp="")
        a = self.majeur("+22790000102")
        r = self.apercu([a.id], type_="invitation_whatsapp", texte="Rejoignez {lien}")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "lien_absent"))

    def test_attestation_de_consentement_obligatoire(self):
        a = self.majeur("+22790000103")
        d = self.apercu([a.id], type_="invitation_whatsapp", texte="Rejoignez {lien}").json()
        with override_settings(**ACTIF):
            r = self.confirmer(d["id"])
            self.assertEqual((r.status_code, r.json()["code"]), (400, "attestation"))
            self.assertEqual(self.confirmer(d["id"], attestation_consentement=True).status_code, 200)

    def test_mineur_ou_age_inconnu_exclu_sauf_accord_parental_valide(self):
        naiss = date.today().replace(year=date.today().year - 14)
        inconnu = user("+22790000104")
        mineur = user("+22790000105", date_naissance=naiss)
        autorise = user("+22790000106", date_naissance=naiss)
        demande = user("+22790000110", date_naissance=naiss)
        for u in (inconnu, mineur, autorise, demande):
            PreferenceCommunication.objects.create(utilisateur=u, invitations_whatsapp=True)
        PreferenceCommunication.objects.filter(utilisateur=autorise).update(parental_statut="valide")
        PreferenceCommunication.objects.filter(utilisateur=demande).update(parental_statut="demande")
        adulte = self.majeur("+22790000107")
        d = self.apercu([inconnu.id, mineur.id, autorise.id, demande.id, adulte.id], type_="invitation_whatsapp", texte="Rejoignez {lien}").json()
        self.assertEqual(d["exclusions"]["consentement_parental_requis"], 3)
        ids = set(Campagne.objects.get(id=d["id"]).messages.values_list("utilisateur_id", flat=True))
        self.assertEqual(ids, {autorise.id, adulte.id})

    def test_absence_de_reponse_n_est_pas_un_consentement(self):
        sans_pref = self.majeur("+22790000111", consent=False)
        indecis = self.majeur("+22790000112", consent=False)
        PreferenceCommunication.objects.create(utilisateur=indecis)   # invitations_whatsapp = None
        refus = self.majeur("+22790000113", consent=False)
        PreferenceCommunication.objects.create(utilisateur=refus, invitations_whatsapp=False)
        ok = self.majeur("+22790000114")
        d = self.apercu([sans_pref.id, indecis.id, refus.id, ok.id], type_="invitation_whatsapp", texte="Rejoignez {lien}").json()
        self.assertEqual((d["nb_destinataires"], d["exclusions"]["consentement_requis"]), (1, 3))

    def test_retrait_du_consentement_apres_confirmation_empeche_l_envoi(self):
        a = self.majeur("+22790000115")
        d = self.apercu([a.id], type_="invitation_whatsapp", texte="Rejoignez {lien}").json()
        with override_settings(**ACTIF):
            self.confirmer(d["id"], attestation_consentement=True)
            PreferenceCommunication.objects.filter(utilisateur=a).update(invitations_whatsapp=False)
            with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer") as env:
                services.traiter_lot()
        env.assert_not_called()
        m = MessageSms.objects.get(campagne_id=d["id"])
        self.assertEqual((m.statut, m.dernier_code), ("ignore", "consentement_requis"))

    def test_opposition_facultative_exclut_aussi_les_invitations(self):
        a = self.majeur("+22790000116")
        PreferenceCommunication.objects.filter(utilisateur=a).update(opposition_facultatif=True)
        d = self.apercu([a.id], type_="invitation_whatsapp", texte="Rejoignez {lien}").json()
        self.assertEqual((d["nb_destinataires"], d["exclusions"]["opposition"]), (0, 1))

    def test_aucun_ajout_automatique_envoi_par_sms_uniquement(self):
        a = self.majeur("+22790000108")
        envoyes = []
        with mock.patch.object(fournisseurs.FournisseurSimule, "envoyer", side_effect=lambda n, t: (envoyes.append(t), ("accepte", "x"))[1]), \
                mock.patch("requests.post") as post:
            d = self.apercu([a.id], type_="invitation_whatsapp", texte="Rejoignez {lien}").json()
            with override_settings(**ACTIF):
                self.confirmer(d["id"], attestation_consentement=True)
                services.traiter_lot()
        self.assertEqual(envoyes, ["Rejoignez " + LIEN])
        post.assert_not_called()

    def test_preferences_modifiables_par_admin_seulement(self):
        u = user("+22790000109")
        r = self.api.patch(f"{BASE}utilisateurs/{u.id}/preferences/", {"opposition_facultatif": True}, format="json")
        self.assertTrue(r.json()["sms_facultatifs"] is False and r.json()["invitations_whatsapp"] is None)
        # l'administrateur ne peut pas consentir à la place de la personne
        self.api.patch(f"{BASE}utilisateurs/{u.id}/preferences/", {"invitations_whatsapp": True}, format="json")
        self.assertIsNone(PreferenceCommunication.objects.get(utilisateur=u).invitations_whatsapp)
        c = APIClient(); c.force_authenticate(u)
        self.assertEqual(c.patch(f"{BASE}utilisateurs/{u.id}/preferences/", {"opposition_facultatif": False}, format="json").status_code, 403)


class HistoriqueEtRecherche(Base):
    def test_historique_detail_et_recherche_par_utilisateur(self):
        a, b = user("+22790000111"), user("+22790000112")
        d = self.apercu([a.id, b.id]).json()
        with override_settings(**ACTIF):
            self.confirmer(d["id"])
            services.traiter_lot()
        liste = self.api.get(BASE + "campagnes/").json()
        self.assertEqual(liste["count"], 1)
        c = liste["results"][0]
        self.assertEqual((c["auteur"], c["messages"]["accepte"], c["nb_destinataires"]), ("Admin Test", 2, 2))
        msgs = self.api.get(f"{BASE}messages/?utilisateur={a.id}").json()
        self.assertEqual(msgs["count"], 1)
        self.assertEqual(msgs["results"][0]["utilisateur_id"], a.id)
        self.assertNotIn("texte", msgs["results"][0])             # aucun texte ni numéro complet dans l'historique

    def test_depense_du_mois_suit_les_messages_acceptes(self):
        a = user("+22790000113")
        d = self.apercu([a.id]).json()
        with override_settings(**ACTIF):
            self.confirmer(d["id"])
        self.assertEqual(self.api.get(BASE + "parametres/").json()["depense_mois_fcfa"], Decimal("10"))


class FiltreClasseListeComptes(Base):
    def test_liste_des_comptes_filtrable_par_niveau_et_serie(self):
        from programme.models import Cycle, Niveau, Serie
        cycle = Cycle.objects.create(nom="Lycée test", ordre=1)
        n1, n2 = Niveau.objects.create(cycle=cycle, nom="Seconde", ordre=1), Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=2)
        s = Serie.objects.create(niveau=n2, nom="D")
        a = user("+22790000121", niveau=n1)
        b = user("+22790000122", niveau=n2, serie=s)
        ids = lambda q: sorted(r["id"] for r in self.api.get("/api/admin/comptes/" + q).json()["results"])
        self.assertEqual(ids(f"?niveau={n1.id}"), [a.id])
        self.assertEqual(ids(f"?niveau={n2.id}&serie={s.id}"), [b.id])
        self.assertEqual(ids("?niveau=abc"), sorted(User.objects.values_list("id", flat=True)))   # valeur invalide ignorée
        d = self.apercu(mode="filtres", filtres={"niveau": n1.id}).json()
        self.assertEqual(d["nb_destinataires"], 1)
