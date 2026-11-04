"""Tarif, plafond et lien : validation, droits, calcul sur le nombre réel de segments, prise en compte immédiate.
Les valeurs ne sont jamais codées en dur dans le module (elles vivent en base)."""
import io
import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient

from comptes.models import User
from communications import services
from communications.models import Campagne, ParametresCommunication
from communications.tests.test_worker_demande import ACTIF, BASE, Base, user


class ValidationEtDroits(Base):
    def patch(self, client, data):
        return client.patch(BASE + "parametres/", data, format="json")

    def test_tarif_strictement_positif(self):
        for mauvais in (0, "0", "0.00", -1, "abc"):
            self.assertEqual(self.patch(self.api, {"cout_segment_fcfa": mauvais}).status_code, 400, mauvais)
        r = self.patch(self.api, {"cout_segment_fcfa": "15"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Decimal(str(r.json()["cout_segment_fcfa"])), Decimal("15"))
        self.assertEqual(ParametresCommunication.objects.get(pk=1).cout_segment_fcfa, Decimal("15.00"))

    def test_plafond_superieur_ou_egal_a_zero(self):
        self.assertEqual(self.patch(self.api, {"plafond_mensuel_fcfa": -1}).status_code, 400)
        self.assertEqual(self.patch(self.api, {"plafond_mensuel_fcfa": "x"}).status_code, 400)
        self.assertEqual(self.patch(self.api, {"plafond_mensuel_fcfa": 15000}).status_code, 200)
        self.assertEqual(self.patch(self.api, {"plafond_mensuel_fcfa": 0}).status_code, 200)

    def test_un_plafond_nul_bloque_les_envois(self):
        d = self.api.post(BASE + "campagnes/apercu/", {
            "cle": "cle-plafond-zero", "type": "sms", "texte": "Bonjour", "mode": "ids", "ids": [self.eleves[0].id], "filtres": {}},
            format="json").json()
        self.patch(self.api, {"plafond_mensuel_fcfa": 0})
        with override_settings(**ACTIF):
            r = self.api.post(f"{BASE}campagnes/{d['id']}/confirmer/", {}, format="json")
            self.assertEqual((r.status_code, r.json()["code"]), (409, "plafond_absent"))
            self.assertEqual(services.garde_envoi(), "plafond_absent")

    def test_lien_whatsapp_valide(self):
        self.assertEqual(self.patch(self.api, {"lien_whatsapp": "http://exemple.com/x"}).status_code, 400)
        r = self.patch(self.api, {"lien_whatsapp": "https://chat.whatsapp.com/ABCDEFGHIJKL"})
        self.assertEqual(r.json()["lien_whatsapp"], "https://chat.whatsapp.com/ABCDEFGHIJKL")

    def test_seuls_les_administrateurs_modifient_ou_lisent_les_parametres(self):
        eleve = user("+22790000901")
        vendeur = User.objects.create_user("+22790000902", password="Motdepasse-2026", prenom="V", nom="W", role=User.Role.VENDEUR,
                                           statut=User.Statut.ACTIF)
        admin_en_attente = User.objects.create_user("+22790000903", password="Motdepasse-2026", prenom="A", nom="E",
                                                    role=User.Role.ADMIN, statut=User.Statut.EN_ATTENTE)
        anonyme = APIClient()
        for client, attendu in ((anonyme, 401),):
            self.assertEqual(self.patch(client, {"plafond_mensuel_fcfa": 1}).status_code, attendu)
            self.assertEqual(client.get(BASE + "parametres/").status_code, attendu)
        for compte in (eleve, vendeur, admin_en_attente):
            c = APIClient()
            c.force_authenticate(compte)
            self.assertEqual(self.patch(c, {"plafond_mensuel_fcfa": 1, "cout_segment_fcfa": 1}).status_code, 403, compte.role)
            self.assertEqual(c.get(BASE + "parametres/").status_code, 403, compte.role)
        self.assertEqual(ParametresCommunication.objects.get(pk=1).plafond_mensuel_fcfa, 1000)   # rien n'a changé


class CoutSelonLesSegmentsReels(Base):
    def apercu(self, cle, texte, nb=3):
        return self.api.post(BASE + "campagnes/apercu/", {
            "cle": cle, "type": "sms", "texte": texte, "mode": "ids", "ids": [e.id for e in self.eleves[:nb]], "filtres": {}},
            format="json").json()

    def test_le_cout_suit_le_nombre_reel_de_segments(self):
        self.api.patch(BASE + "parametres/", {"cout_segment_fcfa": "15", "plafond_mensuel_fcfa": 15000}, format="json")
        court = self.apercu("cle-cout-court", "Bonjour")                     # 1 segment x 3 destinataires
        long = self.apercu("cle-cout-long", "a" * 170)                       # 2 segments x 3 destinataires
        self.assertEqual((court["segments_total"], Decimal(str(court["cout_estime"]))), (3, Decimal("45")))
        self.assertEqual((long["segments_total"], Decimal(str(long["cout_estime"]))), (6, Decimal("90")))

    def test_un_changement_de_tarif_vaut_pour_les_nouveaux_apercus_seulement(self):
        self.api.patch(BASE + "parametres/", {"cout_segment_fcfa": "15"}, format="json")
        avant = self.apercu("cle-tarif-15", "Bonjour")
        self.api.patch(BASE + "parametres/", {"cout_segment_fcfa": "20"}, format="json")
        apres = self.apercu("cle-tarif-20", "Bonjour")
        self.assertEqual(Decimal(str(avant["cout_estime"])), Decimal("45"))
        self.assertEqual(Decimal(str(apres["cout_estime"])), Decimal("60"))
        self.assertEqual(Campagne.objects.get(id=avant["id"]).cout_segment, Decimal("15.00"))   # l'aperçu déjà fait garde son tarif

    def test_le_budget_lit_la_base_a_chaque_controle(self):
        self.lancer(2)
        ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=0)
        with override_settings(**ACTIF):
            self.assertEqual(services.garde_envoi(), "plafond_absent")
        ParametresCommunication.objects.filter(pk=1).update(plafond_mensuel_fcfa=15000, cout_segment_fcfa=Decimal("15"))
        with override_settings(**ACTIF):
            self.assertIsNone(services.garde_envoi())


class CommandeDeConfiguration(Base):
    def lancer_commande(self, *args):
        out = io.StringIO()
        call_command("configurer_communications", *args, stdout=out)
        return out.getvalue()

    def test_enregistre_tarif_et_plafond_en_base(self):
        sortie = self.lancer_commande("--tarif", "15", "--plafond", "15000")
        p = ParametresCommunication.objects.get(pk=1)
        self.assertEqual((p.cout_segment_fcfa, p.plafond_mensuel_fcfa), (Decimal("15.00"), 15000))
        self.assertIn("Tarif d'un segment : 15.00 FCFA", sortie)
        self.assertIn("Plafond mensuel : 15000 FCFA", sortie)

    def test_memes_regles_que_l_ecran(self):
        for args in (("--tarif", "0"), ("--tarif", "-5"), ("--plafond", "-1"), ("--tarif", "abc"), ("--lien", "http://x.y")):
            with self.assertRaises(CommandError, msg=args):
                self.lancer_commande(*args)
        p = ParametresCommunication.objects.get(pk=1)
        self.assertEqual((p.cout_segment_fcfa, p.plafond_mensuel_fcfa), (Decimal("10"), 1000))   # rien n'a été modifié

    def test_sans_argument_lecture_seule_et_sans_creation(self):
        ParametresCommunication.objects.all().delete()
        sortie = self.lancer_commande()
        self.assertEqual(ParametresCommunication.objects.count(), 0)
        self.assertIn("aucun envoi possible", sortie)

    def test_la_commande_n_active_aucun_envoi(self):
        self.lancer_commande("--tarif", "15", "--plafond", "15000")
        self.assertFalse(settings.COMMUNICATIONS_SMS_ACTIVES)

    def test_aucune_valeur_codee_en_dur_dans_le_module(self):
        racine = Path(settings.BASE_DIR) / "communications"
        motif = re.compile(r"\b15000\b|\b15 000\b|cout_segment_fcfa\s*=\s*(Decimal\()?[\"']?15\b")
        fautifs = [str(p.relative_to(racine)) for p in racine.rglob("*.py") if "tests" not in p.parts and motif.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(fautifs, [])
