"""
Concordance réponse rédigée / résultat calculé (étape 9.1.1) : lecteur strict des coordonnées d'un vecteur, verdict
`verifiee` | `non_verifiee` | `contradiction`, et intégration à la correction complète (sans IA ni réseau réels).
"""

import copy
import time
from fractions import Fraction

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from comptes.models import User

from .correction import concordance
from .correction.coordonnees_vecteur import lire_coordonnees, valeur_exacte
from .models import Cycle, Matiere, Niveau, Programme, Serie
from .test_correction_exercice import CACHE_TEST, _analyse
from .test_simulations import ENONCE, QUESTIONS, _correction_vecteur

SOURCES = (ENONCE,)
Q3 = "Déterminer les coordonnées du vecteur AB."
ATTENDU = (Fraction(3), Fraction(1))


def _statut(resultat, texte=Q3, sources=SOURCES):
    verdict = concordance.concordance_question(sources, texte, resultat)
    return None if verdict is None else verdict["statut"]


class LectureCoordonneesTests(SimpleTestCase):
    def test_nombres_du_vocabulaire_ferme(self):
        self.assertEqual(valeur_exacte("3"), 3)
        self.assertEqual(valeur_exacte("-3"), -3)
        self.assertEqual(valeur_exacte("- 3"), -3)
        self.assertEqual(valeur_exacte("+2,5"), Fraction(5, 2))
        self.assertEqual(valeur_exacte("0.25"), Fraction(1, 4))
        self.assertEqual(valeur_exacte("\\frac{6}{2}"), 3)
        self.assertEqual(valeur_exacte("-\\frac{1}{2}"), Fraction(-1, 2))
        for faux in ("", "x", "3x", "1/0", "\\frac{1}{0}", "3 1", "sqrt(2)", "1e3", "__import__('os')"):
            self.assertIsNone(valeur_exacte(faux), faux)

    def test_ecritures_equivalentes_du_vecteur_ab_3_1(self):
        ecritures = [
            "AB = (3 ; 1)",
            "$\\overrightarrow{AB}(3 ; 1)$",
            "AB = (3, 1)",
            "AB(3 , 1)",
            "$\\vec{AB}\\begin{pmatrix}3\\\\1\\end{pmatrix}$",
            "$\\vec{AB}\\begin{pmatrix} 3 \\\\ 1 \\end{pmatrix}$",  # écriture réelle de l'IA (espaces autour du saut de ligne)
            "$\\vec{AB} = \\begin{pmatrix} 3 \\\\ 1 \\end{pmatrix}$",
            "$\\overrightarrow{AB} = \\begin{bmatrix}3\\\\1\\end{bmatrix}$",
            "$\\overrightarrow{AB}\\left(\\begin{array}{c}3\\\\1\\end{array}\\right)$",
            "$\\vec{AB}\\binom{3}{1}$",
            "$\\vec{AB}\\dbinom{3}{1}$",
            "Le vecteur $\\vec{AB}$ a pour coordonnées $(3 ; 1)$.",
            "$\\vec{AB}\\left(3\\,;\\,1\\right)$",
            "AB = (3.0 ; 1,0)",
            "AB = (\\frac{6}{2} ; 1)",
            "AB = (+3 ; +1)",
            "AB = (4-1 ; 3-2) = (3 ; 1)",  # calcul intermédiaire puis valeur
            "A(1 ; 2), B(4 ; 3) et AB(3 ; 1)",  # les coordonnées des POINTS ne sont pas lues comme celles du vecteur
        ]
        for texte in ecritures:
            lecture = lire_coordonnees(texte, "AB")
            self.assertEqual((lecture.statut, lecture.valeur), ("lue", ATTENDU), texte)

    def test_signe_ordre_et_nom_sont_respectes(self):
        self.assertEqual(lire_coordonnees("AB = (-3 ; 1)", "AB").valeur, (-3, 1))
        self.assertEqual(lire_coordonnees("AB = (−3 ; 1)", "AB").valeur, (-3, 1))  # vrai signe moins
        self.assertEqual(lire_coordonnees("AB = (1 ; 3)", "AB").valeur, (1, 3))
        self.assertEqual(lire_coordonnees("$\\vec{AB}\\begin{pmatrix} 1 \\\\ 3 \\end{pmatrix}$", "AB").valeur, (1, 3))
        self.assertEqual(lire_coordonnees("AB = (3 ; 1) et BA = (-3 ; -1)", "AB").valeur, (3, 1))
        self.assertEqual(lire_coordonnees("AB = (3 ; 1) et BA = (-3 ; -1)", "BA").valeur, (-3, -1))

    def test_ce_qui_n_est_pas_reconnu_sans_ambiguite_n_est_pas_lu(self):
        cas = {
            "virgule ambiguë": "AB = (3,1)",
            "incomplet": "AB = (3 ;)",
            "une seule composante": "AB = (3)",
            "trois composantes": "AB = (3 ; 1 ; 2)",
            "sans parenthèses": "AB = 3 ; 1",
            "nombres seuls": "On trouve 3 et 1.",
            "composantes nommées": "x = 3 et y = 1",
            "deux écritures différentes": "AB = (3 ; 1) ou AB = (1 ; 3)",
            "deux écritures sans nom": "(3 ; 1) puis (1 ; 3)",
            "autre vecteur": "BA = (3 ; 1)",
            "autre vecteur en toutes lettres": "Le vecteur BA a pour coordonnées (3 ; 1).",
            "latex mal formé": "$\\vec{AB}\\begin{pmatrix} 3 \\\\ \\end{pmatrix}$",
            "environnement non fermé": "$\\vec{AB}\\begin{pmatrix} 3 \\\\ 1",
            "environnements différents": "$\\vec{AB}\\begin{pmatrix} 3 \\\\ 1 \\end{bmatrix}$",
            "ligne de matrice": "$\\vec{AB}\\begin{pmatrix} 3 & 1 \\end{pmatrix}$",
            "fraction nulle": "AB = (\\frac{1}{0} ; 1)",
            "vide": "",
            "espaces": "   ",
        }
        for nom, texte in cas.items():
            lecture = lire_coordonnees(texte, "AB")
            self.assertNotEqual(lecture.statut, "lue", nom)
            self.assertIsNone(lecture.valeur, nom)
            self.assertTrue(lecture.raison, nom)

    def test_commandes_et_code_ne_sont_jamais_interpretes(self):
        dangereux = [
            "__import__('os').system('echo 3 1')",
            "eval('(3 ; 1)')",
            "AB = (3 ; 1); system(\"rm -rf /\")",
            "$$\\input{/etc/passwd} AB = (3 ; 1)$$",
            "\\write18{ls} AB = (3 ; 1)",
            "{{7*7}} AB = (3 ; 1)",
            "$(touch /tmp/x) AB = (3 ; 1)",
            "<script>alert(1)</script> AB = (3 ; 1)",
            "AB = (3 ; 1) `id`",
            "exec('AB=(3;1)')",
        ]
        for texte in dangereux:
            lecture = lire_coordonnees(texte, "AB")
            self.assertEqual(lecture.statut, "absente", texte)
            self.assertIsNone(lecture.valeur, texte)

    def test_texte_adversarial_borne_et_rapide(self):
        for texte in ("(" * 4000, "\\begin{pmatrix}" * 400, "(3 ; " * 800, "1" * 6000, "\\frac{" * 700, "A" * 6000):
            debut = time.perf_counter()
            lire_coordonnees(texte, "AB")
            self.assertLess(time.perf_counter() - debut, 1.0, texte[:20])
        self.assertEqual(lire_coordonnees(None, "AB").statut, "absente")  # type: ignore[arg-type]


class ConcordanceQuestionTests(SimpleTestCase):
    def test_concordance_verifiee_dans_toutes_les_notations(self):
        for ecriture in (
            "$\\vec{AB}\\begin{pmatrix} 3 \\\\ 1 \\end{pmatrix}$", "$\\overrightarrow{AB}(3 ; 1)$", "AB = (3, 1)", "AB(3 ; 1)",
        ):
            verdict = concordance.concordance_question(SOURCES, Q3, ecriture)
            self.assertEqual(verdict["statut"], "verifiee", ecriture)
            self.assertEqual((verdict["attendu"], verdict["annonce"]), ("(3 ; 1)", "(3 ; 1)"))
            self.assertEqual(verdict["methodes"], ["SymPy", "Calcul exact"])

    def test_reponses_fausses_interpretables_donnent_une_contradiction(self):
        cas = {
            "$\\vec{AB}\\begin{pmatrix} 1 \\\\ 3 \\end{pmatrix}$": "inversées",
            "AB = (1 ; 3)": "inversées",
            "AB = (-3 ; 1)": None,
            "AB = (−3 ; 1)": None,
            "AB = (3 ; -1)": None,
            "AB = (-3 ; -1)": "opposé",
            "AB = (4 ; 1)": None,
            "$\\overrightarrow{AB}(5 ; 1)$": None,
            "AB = (3, 2)": None,
        }
        for ecriture, indice in cas.items():
            verdict = concordance.concordance_question(SOURCES, Q3, ecriture)
            self.assertEqual(verdict["statut"], "contradiction", ecriture)
            self.assertEqual(verdict["attendu"], "(3 ; 1)")
            self.assertIn("incompatible", verdict["detail"])
            if indice:
                self.assertIn(indice, verdict["detail"], ecriture)

    def test_ambigu_incomplet_ou_mal_forme_reste_non_verifie(self):
        for ecriture in (
            "AB = (3,1)", "AB = (3 ;)", "AB = 3", "AB = (3 ; 1) ou (1 ; 3)", "BA = (-3 ; -1)",
            "$\\vec{AB}\\begin{pmatrix} 3 \\\\ \\end{pmatrix}$", "on trouve 3 et 1", "eval('(3 ; 1)')", "",
        ):
            verdict = concordance.concordance_question(SOURCES, Q3, ecriture)
            self.assertEqual(verdict["statut"], "non_verifiee", ecriture)
            self.assertIsNone(verdict["annonce"], ecriture)
            self.assertEqual(verdict["attendu"], "(3 ; 1)")  # le moteur sait ce qui est attendu, mais ne compare pas

    def test_nombres_presents_ne_suffisent_pas(self):
        # contiennent 3 et 1 mais ne donnent pas AB = (3 ; 1)
        for ecriture in ("Les nombres 3 et 1 apparaissent.", "x_B - x_A = 3 et y_B - y_A = 1", "(1 ; 3)", "AB = 3 + 1"):
            self.assertNotEqual(_statut(ecriture), "verifiee", ecriture)

    def test_questions_non_concernees(self):
        self.assertIsNone(_statut("Les points sont placés.", "Placer les points A et B."))
        self.assertIsNone(_statut("AB est représenté par une flèche.", "Représenter le vecteur AB."))
        self.assertIsNone(_statut("S = {2 ; 3}", "Résoudre l'équation $x^2 - 5x + 6 = 0$."))
        self.assertIsNone(_statut("(3 ; 1)", "Calculer les coordonnées des vecteurs AB et BA."))  # deux vecteurs
        self.assertIsNone(_statut("(3 ; 1)", ""))

    def test_donnees_de_l_enonce_insuffisantes_ou_ambigues_non_verifie(self):
        for enonce in ("On considère le point A(1 ; 2).", "A(1 ; 2) et B(4,3).", "A(1 ; 2) et B(4 ; 3) puis B(5 ; 3).", "A(x ; y) et B(4 ; 3)."):
            verdict = concordance.concordance_question((enonce,), Q3, "AB = (3 ; 1)")
            self.assertEqual(verdict["statut"], "non_verifiee", enonce)
            self.assertIsNone(verdict["attendu"], enonce)  # rien n'est calculé : rien n'est « vérifié »

    def test_autres_points_et_decimaux(self):
        sources = ("Dans un repère orthonormé, A(-1 ; 2,5) et B(3 ; -4).",)
        self.assertEqual(concordance.concordance_question(sources, Q3, "AB = (4 ; -6,5)")["statut"], "verifiee")
        self.assertEqual(concordance.concordance_question(sources, Q3, "AB = (4 ; 6,5)")["statut"], "contradiction")
        self.assertEqual(concordance.concordance_question(sources, "Calculer les composantes de $\\vec{BA}$.", "BA = (-4 ; 6,5)")["statut"], "verifiee")


@override_settings(
    CACHES=CACHE_TEST, DEBUG=True, IA_CORRECTION_ACTIVE=True, IA_CORRECTION_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice",
)
class ConcordanceDansLaCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=tle, nom="C")
        cls.maths = Programme.objects.create(matiere=Matiere.objects.create(nom="Mathématiques"), niveau=tle, serie=serie)
        cls.eleve = User.objects.create_user(
            "+22790000041", password="Motdepasse-2026", prenom="E", nom="L",
            role=User.Role.ELEVE, statut=User.Statut.ACTIF, niveau=tle, serie=serie,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)

    def corriger(self, resultat3, simulations=False):
        from unittest import mock
        from .test_correction_exercice import URL, _fichier
        corps = {"programme": self.maths.id, "analyse": copy.deepcopy(_analyse(ENONCE, QUESTIONS))}
        p_ia, p_wolf = _fichier(copy.deepcopy(_correction_vecteur(resultat3)), None)
        with p_ia, p_wolf, override_settings(SIMULATIONS_ACTIVES=simulations):
            reponse = self.client.post(URL, corps, format="json")
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return reponse.json()["correction"]

    def test_calcul_verifie_et_concordance_verifiee(self):
        c = self.corriger("$\\vec{AB}\\begin{pmatrix} 3 \\\\ 1 \\end{pmatrix}$")
        q3 = c["questions"][2]
        self.assertEqual(q3["controles"][0]["statut"], "verifie")  # calcul vérifié (SymPy)
        self.assertEqual(q3["concordance"]["statut"], "verifiee")  # réponse rédigée = résultat calculé
        self.assertEqual(q3["statut"], "verifiee")
        self.assertNotIn("concordance", c["questions"][0])  # « Placer » : question non concernée
        self.assertNotIn("concordance", c["questions"][1])  # « Représenter » : question non concernée

    def test_calcul_verifie_mais_reponse_redigee_contradictoire(self):
        for fausse in ("$\\overrightarrow{AB}(1 ; 3)$", "$\\vec{AB}\\begin{pmatrix}-3\\\\1\\end{pmatrix}$"):
            c = self.corriger(fausse)
            q3 = c["questions"][2]
            self.assertEqual(q3["controles"][0]["statut"], "verifie")  # l'opération intermédiaire est juste…
            self.assertEqual(q3["concordance"]["statut"], "contradiction")  # …mais la réponse finale ne l'est pas
            self.assertEqual(q3["statut"], "contradiction")
            self.assertEqual(c["statut"], "contradiction")
            self.assertTrue(any("ne concorde pas" in a for a in c["avertissements"]))

    def test_reponse_non_interpretable_ne_passe_pas_verifiee(self):
        c = self.corriger("On trouve les nombres 3 et 1.")
        q3 = c["questions"][2]
        self.assertEqual(q3["controles"][0]["statut"], "verifie")
        self.assertEqual(q3["concordance"]["statut"], "non_verifiee")
        self.assertEqual(q3["statut"], "partiellement_verifiee")  # rétrogradée : jamais « vérifiée »
        self.assertNotEqual(c["statut"], "calculs_verifies")

    def test_une_simulation_ne_change_pas_le_statut_de_concordance(self):
        with override_settings(SIMULATIONS_DEV_SEULEMENT=True):
            sans = self.corriger("On trouve les nombres 3 et 1.", simulations=False)["questions"][2]
            avec = self.corriger("On trouve les nombres 3 et 1.", simulations=True)["questions"][2]
        self.assertEqual(avec["simulations"][0]["parametres"]["vecteur"], {"nom": "AB", "x": 3, "y": 1})  # simulation correcte…
        self.assertEqual(sans["concordance"]["statut"], avec["concordance"]["statut"], "non_verifiee")  # …sans effet
        self.assertEqual(avec["concordance"]["statut"], "non_verifiee")
        self.assertEqual(avec["statut"], "partiellement_verifiee")

    def test_la_concordance_ne_depend_pas_des_simulations_ni_du_mode_developpement(self):
        with override_settings(DEBUG=False, IA_CORRECTION_DEV_SEULEMENT=False):
            c = self.corriger("$\\overrightarrow{AB}(3 ; 1)$")
        self.assertEqual(c["questions"][2]["concordance"]["statut"], "verifiee")
        self.assertNotIn("simulations", c["questions"][2])  # production : aucune simulation

    def test_une_erreur_interne_n_empeche_pas_la_correction(self):
        from unittest import mock
        with mock.patch("programme.correction.concordance.concordance_question", side_effect=RuntimeError("boum")):
            c = self.corriger("$\\overrightarrow{AB}(3 ; 1)$")
        self.assertNotIn("concordance", c["questions"][2])
        self.assertEqual(c["questions"][2]["statut"], "verifiee")
