from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from budget_ia import service as budget
from budget_ia.tests.outils import TARIFS_TEST, creer_eleve
from comptes.models import User

URL = "/api/admin/budget-ia/"


@override_settings(IA_TARIFS_USD=TARIFS_TEST, ANTHROPIC_API_KEY="cle-secrete-factice")
class RapportTests(TestCase):
    def setUp(self):
        self.eleve = creer_eleve()
        with budget.contexte(utilisateur_id=self.eleve.id, exercice_cle="ex"):
            op = budget.ouvrir(fonctionnalite="lecture", modele="m", tokens_entree=1000, tokens_sortie_max=1000)
        budget.terminer(op, {"tokens_entree": 800, "tokens_sortie": 200})

    def api_role(self, role):
        u = User.objects.create_user("+22790000077", password="Motdepasse-2026", prenom="A", nom="B", role=role, statut=User.Statut.ACTIF)
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_reserve_aux_administrateurs(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)
        self.assertEqual(self.api_role(User.Role.ELEVE).get(URL).status_code, 403)

    def test_contenu_du_rapport(self):
        r = self.api_role(User.Role.ADMIN).get(URL)
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual((d["appels_anthropic"], d["exercices_traites"], d["echecs"], d["en_cours"]), (1, 1, 0, 0))
        self.assertGreater(d["consomme_estime_fcfa"], 0)
        self.assertAlmostEqual(d["restant_fcfa"], 90000 - d["consomme_estime_fcfa"], places=2)
        self.assertEqual(d["par_fonctionnalite"][0]["cle"], "lecture")
        self.assertEqual(d["par_modele"][0]["cle"], "m")
        self.assertEqual(d["par_eleve"][0]["cle"], self.eleve.id)
        self.assertIn("Ne remplace pas la facture", d["avertissement"])
        self.assertEqual((d["budget_reference_fcfa"], d["seuil_operationnel_fcfa"], d["taux_date_reference"]), (100000.0, 90000.0, "2026-11-03"))

    def test_aucun_secret_ni_contenu(self):
        corps = self.api_role(User.Role.ADMIN).get(URL).content.decode()
        self.assertNotIn("cle-secrete-factice", corps)
        self.assertNotIn("ANTHROPIC", corps)

    def test_mois_invalide(self):
        self.assertEqual(self.api_role(User.Role.ADMIN).get(URL + "?mois=abc").status_code, 400)
