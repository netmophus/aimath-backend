"""
Tests de l'étude de fonction (étape 8A) : tableau de variations et courbe calculés par SymPy.
Aucun appel réseau. On vérifie les NOMBRES (valeurs, signes, bornes) et le fait que ce qui est
envoyé au navigateur ne contient que des données contrôlées.
"""

import copy
import json
import re

import sympy as sp
from django.test import SimpleTestCase

from .correction import service
from .correction.etude_fonction import etude_pour_affirmations, etudier_fonction
from .correction.expressions import analyser
from .test_correction_exercice import CORRECTION_EX2

X = sp.Symbol("x", real=True)
EXPR_SURE = re.compile(r"^[0-9x+\-*/^(). ]+$")


class EtudeReferenceTests(SimpleTestCase):
    """f(x) = x³ − 3x : les résultats imposés par le cahier des charges."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.e = etudier_fonction("x^3 - 3x")

    def test_derivee_et_points_critiques(self):
        e = self.e
        self.assertEqual(e["statut"], "verifie")
        self.assertEqual(sp.sympify(e["derivee"]["texte"].replace("^", "**")) - (3 * sp.Symbol("x") ** 2 - 3), 0)
        self.assertEqual([p["x"] for p in e["points_critiques"]], [-1.0, 1.0])
        self.assertEqual(e["sans_extremum"], [])

    def test_extrema(self):
        e = self.e
        self.assertEqual([(x["x_latex"], x["y_latex"], x["nature"]) for x in e["extrema"]],
                         [("-1", "2", "maximum local"), ("1", "-2", "minimum local")])

    def test_variations(self):
        e = self.e
        self.assertEqual([(i["intervalle_latex"], i["sens"], i["signe"]) for i in e["intervalles"]], [
            ("]-\\infty ; -1]", "croissante", "+"),
            ("[-1 ; 1]", "décroissante", "-"),
            ("[1 ; +\\infty[", "croissante", "+"),
        ])

    def test_tableau_et_limites(self):
        t = self.e["tableau"]
        self.assertEqual(t["x"], ["-\\infty", "-1", "1", "+\\infty"])
        self.assertEqual(t["signes"], ["+", "-", "+"])
        self.assertEqual(t["f"], ["-\\infty", "2", "-2", "+\\infty"])
        self.assertEqual(self.e["limites"], {"moins_infini": "-\\infty", "plus_infini": "+\\infty"})

    def test_courbe_correspond_a_la_fonction(self):
        c = self.e["courbe"]
        self.assertRegex(c["expr"], EXPR_SURE)
        trace = analyser(c["expr"], ("x",))
        f = analyser("x^3 - 3x", ("x",))
        self.assertEqual(sp.simplify(trace - f), 0)
        for p in c["points"]:  # chaque point remarquable est SUR la courbe
            self.assertAlmostEqual(float(f.subs(f.free_symbols.pop(), p["x"])), p["y"], places=9)
        etiquettes = " | ".join(p["etiquette"] for p in c["points"])
        self.assertIn("Max. local (−1 ; 2)", etiquettes)
        self.assertIn("Min. local (1 ; −2)", etiquettes)
        self.assertNotIn("Zéro", etiquettes)  # les zéros sont listés à part : pas d'étiquettes qui se chevauchent
        self.assertEqual([z["x_latex"] for z in c["zeros"]], [r"- \sqrt{3}", "0", r"\sqrt{3}"])
        self.assertEqual(c["ordonnee_origine_latex"], "0")
        self.assertEqual(len(c["points"]), 5)  # 2 extrema + 3 zéros (l'origine en est un)
        # La fenêtre contient tous les points remarquables.
        for p in c["points"]:
            self.assertTrue(c["domaine_x"][0] < p["x"] < c["domaine_x"][1])
            self.assertTrue(c["domaine_y"][0] < p["y"] < c["domaine_y"][1])


class EtudeCasTests(SimpleTestCase):
    def assertTableauCoherent(self, e):
        t = e["tableau"]
        self.assertEqual(len(t["x"]), len(t["signes"]) + 1)
        self.assertEqual(len(t["f"]), len(t["x"]))
        self.assertEqual(t["x"][0], "-\\infty")
        self.assertEqual(t["x"][-1], "+\\infty")
        # Chaque colonne intermédiaire est un zéro de f' (même sans changement de signe, ex. x³ en 0) et inversement.
        self.assertEqual(t["zeros_derivee"], list(range(1, len(t["x"]) - 1)))
        self.assertEqual(len(t["x"]) - 2, len(e["points_critiques"]))
        # Signes réellement exacts : en chaque colonne entière, la dérivée a bien le signe annoncé de part et d'autre.
        f1 = analyser(e["derivee"]["texte"], ("x",))
        x = next(iter(f1.free_symbols), None)
        for i, colonne in enumerate(t["x"][1:-1], start=1):
            if not re.fullmatch(r"-?\d+", colonne):
                continue
            r = int(colonne)
            avant, apres = (f1.subs(x, sp.Rational(r) + d) for d in (sp.Rational(-1, 1000), sp.Rational(1, 1000)))
            self.assertEqual("+" if avant > 0 else "-", t["signes"][i - 1])
            self.assertEqual("+" if apres > 0 else "-", t["signes"][i])

    def test_constante(self):
        e = etudier_fonction("5")
        self.assertEqual(e["statut"], "verifie")
        self.assertTrue(e["constante"])
        self.assertEqual(e["tableau"], {"x": ["-\\infty", "+\\infty"], "signes": ["0"], "f": ["5", "5"], "zeros_derivee": []})
        self.assertEqual(e["intervalles"][0]["sens"], "constante")
        self.assertEqual(e["extrema"], [])
        self.assertEqual(e["limites"], {"moins_infini": "5", "plus_infini": "5"})

    def test_monotones(self):
        for texte, signe, f_tableau in (("2x+1", "+", ["-\\infty", "+\\infty"]), ("-x", "-", ["+\\infty", "-\\infty"]),
                                        ("x^3+x+1", "+", ["-\\infty", "+\\infty"])):
            with self.subTest(texte):
                e = etudier_fonction(texte)
                self.assertEqual(e["statut"], "verifie")
                self.assertEqual(e["tableau"]["signes"], [signe])
                self.assertEqual(e["tableau"]["f"], f_tableau)
                self.assertEqual(e["extrema"], [])
                self.assertTableauCoherent(e)

    def test_point_critique_sans_extremum_n_est_pas_un_extremum(self):
        e = etudier_fonction("x^3")
        self.assertEqual([p["x"] for p in e["points_critiques"]], [0.0])
        self.assertEqual(e["extrema"], [])
        self.assertEqual([p["x_latex"] for p in e["sans_extremum"]], ["0"])
        # f'(0) = 0 figure dans le tableau (colonne x = 0, f(0) = 0) mais f' reste positive de part et d'autre.
        self.assertEqual(e["tableau"], {"x": ["-\\infty", "0", "+\\infty"], "signes": ["+", "+"],
                                        "f": ["-\\infty", "0", "+\\infty"], "zeros_derivee": [1]})
        self.assertEqual([i["sens"] for i in e["intervalles"]], ["croissante"])  # variations inchangées : une seule flèche
        self.assertEqual(e["intervalles"][0]["intervalle_latex"], "]-\\infty ; +\\infty[")
        self.assertTableauCoherent(e)

    def test_resultat_serialisable_en_json(self):
        # Les types SymPy (Integer, Rational…) ne doivent jamais fuiter dans la réponse de l'API.
        for texte in ("x^3", "x^5", "x^4+x^3", "x^3-x", "5", "2x+1", "(x-1)^2*(x+2)"):
            with self.subTest(texte):
                json.dumps(etudier_fonction(texte))

    def test_zeros_de_la_derivee_avec_et_sans_changement_de_signe(self):
        e = etudier_fonction("x^3-3x^2")  # f' = 3x(x-2) : 0 et 2 sont des extrema
        self.assertEqual(e["tableau"]["zeros_derivee"], [1, 2])
        e = etudier_fonction("x^4+x^3")  # f' = x²(4x+3) : 0 (racine double) sans extremum, -3/4 minimum
        self.assertEqual(e["tableau"]["x"], ["-\\infty", "- \\frac{3}{4}", "0", "+\\infty"])
        self.assertEqual(e["tableau"]["signes"], ["-", "+", "+"])
        self.assertEqual(e["tableau"]["zeros_derivee"], [1, 2])
        self.assertEqual([x["x_latex"] for x in e["extrema"]], ["- \\frac{3}{4}"])
        self.assertEqual([x["x_latex"] for x in e["sans_extremum"]], ["0"])
        self.assertEqual([i["sens"] for i in e["intervalles"]], ["décroissante", "croissante"])
        self.assertTableauCoherent(e)
        e = etudier_fonction("x^5")  # f' = 5x⁴ : seul zéro en 0, sans changement de signe
        self.assertEqual(e["tableau"]["x"], ["-\\infty", "0", "+\\infty"])
        self.assertEqual(e["tableau"]["signes"], ["+", "+"])
        self.assertEqual(e["extrema"], [])

    def test_plusieurs_points_critiques(self):
        e = etudier_fonction("x^4-2x^2")
        self.assertEqual([(x["x_latex"], x["y_latex"], x["nature"]) for x in e["extrema"]],
                         [("-1", "-1", "minimum local"), ("0", "0", "maximum local"), ("1", "-1", "minimum local")])
        self.assertEqual(e["tableau"]["signes"], ["-", "+", "-", "+"])
        self.assertEqual(e["tableau"]["f"], ["+\\infty", "-1", "0", "-1", "+\\infty"])
        self.assertEqual(e["limites"], {"moins_infini": "+\\infty", "plus_infini": "+\\infty"})
        self.assertTableauCoherent(e)
        e = etudier_fonction("x^5-5x")
        self.assertEqual([(x["x_latex"], x["y_latex"]) for x in e["extrema"]], [("-1", "4"), ("1", "-4")])
        self.assertEqual(e["limites"], {"moins_infini": "-\\infty", "plus_infini": "+\\infty"})
        e = etudier_fonction("(x-1)^2*(x+2)")  # racine double de f : f touche l'axe en 1 sans le traverser
        self.assertEqual([(x["x_latex"], x["y_latex"], x["nature"]) for x in e["extrema"]],
                         [("-1", "4", "maximum local"), ("1", "0", "minimum local")])

    def test_points_critiques_irrationnels_exacts(self):
        e = etudier_fonction("x^3-x")  # f' = 3x²−1 : ±√3/3
        self.assertEqual(e["statut"], "verifie")
        self.assertEqual(len(e["extrema"]), 2)
        self.assertAlmostEqual(e["extrema"][0]["x"], -0.5773502691896258)
        self.assertAlmostEqual(e["extrema"][0]["y"], 0.3849001794597505)
        self.assertIn("sqrt", e["extrema"][0]["x_latex"])
        etiquettes = " ".join(p["etiquette"] for p in e["courbe"]["points"])
        self.assertIn("Max. local (≈ −0,577 ; ≈ 0,385)", etiquettes)  # valeur approchée signalée comme telle

    def test_coefficients_fractionnaires(self):
        e = etudier_fonction("1/2x^2 - x")
        self.assertEqual(e["extrema"][0]["y_latex"], "- \\frac{1}{2}")
        self.assertEqual(e["extrema"][0]["nature"], "minimum local")

    def test_toute_courbe_est_sure_et_fidele(self):
        for texte in ("x^3-3x", "x^4-2x^2", "x^3-3x^2+2", "1/2x^2-x", "5", "2x+1", "x^5-5x"):
            with self.subTest(texte):
                e = etudier_fonction(texte)
                self.assertRegex(e["courbe"]["expr"], EXPR_SURE)
                self.assertEqual(sp.simplify(analyser(e["courbe"]["expr"], ("x",)) - analyser(texte, ("x",))), 0)
                self.assertTrue(e["courbe"]["domaine_x"][0] < e["courbe"]["domaine_x"][1])
                self.assertTrue(e["courbe"]["domaine_y"][0] < e["courbe"]["domaine_y"][1])
                self.assertGreaterEqual(e["verification"]["controles_numeriques"], 1)
                if e["statut"] == "verifie":
                    self.assertTableauCoherent(e)

    def test_fonctions_non_prises_en_charge_ne_fournissent_ni_courbe_ni_tableau(self):
        for texte in ("1/x", "sqrt(x)", "sin(x)", "exp(x)", "ln(x)", "x^7", "x^4+x+1", "x^2+y", "abs(x)", "x^(1/2)",
                      "2^x", "(x^2+1)/(x-1)", "", "import os", "__import__('os').system('x')", "x^2 +", "3x^"):
            with self.subTest(texte):
                e = etudier_fonction(texte)
                self.assertEqual(e["statut"], "non_pris_en_charge", texte)
                self.assertTrue(e["raison"])
                for cle in ("courbe", "tableau", "extrema", "intervalles", "derivee", "fonction"):
                    self.assertNotIn(cle, e)

    def test_coefficients_irrationnels_refuses(self):
        self.assertEqual(etudier_fonction("sqrt(2)x^2")["statut"], "non_pris_en_charge")
        self.assertEqual(etudier_fonction("pi x^2 - x")["statut"], "non_pris_en_charge")

    def test_aucune_execution_de_texte_arbitraire(self):
        for texte in ("__import__('os').getcwd()", "x.__class__", "open('/etc/passwd')", "lambda: 1"):
            self.assertEqual(etudier_fonction(texte)["statut"], "non_pris_en_charge")


class EtudeDansLaCorrectionTests(SimpleTestCase):
    def _questions(self, brute):
        normalise = service.resolution.normaliser_correction(copy.deepcopy(brute))
        # Wolfram et SymPy du service : on ne teste ici que l'étude ; le contrôle est celui de SymPy.
        from unittest import mock
        from .correction.verification import INDISPONIBLE, VerdictMethode
        with mock.patch.object(service, "verifier_avec_wolfram", return_value=(VerdictMethode(INDISPONIBLE, "simulé"), False)):
            return service.verifier_correction(normalise)["questions"]

    def test_etude_attachee_aux_questions_de_variations_et_d_extrema(self):
        q1, q2, q3 = self._questions(CORRECTION_EX2)
        self.assertIsNone(q1["etude_fonction"])  # simple dérivée : pas de graphique
        self.assertEqual(q2["etude_fonction"]["statut"], "verifie")
        self.assertEqual(q2["etude_fonction"]["demande"], ["variations"])
        self.assertEqual(q3["etude_fonction"]["demande"], ["extrema"])
        self.assertFalse(q2["etude_fonction"]["contredit_par_la_correction"])
        self.assertEqual(q3["etude_fonction"]["tableau"]["f"], ["-\\infty", "2", "-2", "+\\infty"])

    def test_les_donnees_viennent_de_sympy_pas_de_la_correction_de_l_ia(self):
        fausse = copy.deepcopy(CORRECTION_EX2)
        fausse["questions"][2]["verifications"][1]["extrema"] = [{"x": "-1", "y": "5", "nature": "maximum local"}]  # l'IA se trompe
        fausse["questions"][1]["verifications"][0]["intervalles"][1]["sens"] = "croissante"
        q1, q2, q3 = self._questions(fausse)
        self.assertEqual(q3["etude_fonction"]["tableau"]["f"], ["-\\infty", "2", "-2", "+\\infty"])  # valeurs exactes, pas « 5 »
        self.assertEqual(q2["etude_fonction"]["tableau"]["signes"], ["+", "-", "+"])
        self.assertTrue(q3["etude_fonction"]["contredit_par_la_correction"])
        self.assertTrue(q2["etude_fonction"]["contredit_par_la_correction"])
        self.assertEqual((q3["statut"], q2["statut"]), ("contradiction", "contradiction"))

    def test_fonction_non_polynomiale_donne_une_explication_pas_un_tableau(self):
        brute = copy.deepcopy(CORRECTION_EX2)
        for q in brute["questions"]:
            for v in q["verifications"]:
                if v.get("fonction"):
                    v["fonction"] = "1/x"
        _, q2, q3 = self._questions(brute)
        for q in (q2, q3):
            self.assertEqual(q["etude_fonction"]["statut"], "non_pris_en_charge")
            self.assertNotIn("tableau", q["etude_fonction"])
            self.assertNotIn("courbe", q["etude_fonction"])

    def test_etude_pour_affirmations_ignore_les_autres_types(self):
        self.assertIsNone(etude_pour_affirmations([{"type": "derivee", "fonction": "x^2", "derivee": "2x"}]))
        self.assertIsNone(etude_pour_affirmations([]))
        self.assertIsNone(etude_pour_affirmations(None))
        self.assertTrue(json.dumps(etude_pour_affirmations([{"type": "extrema", "fonction": "x^2"}])))  # sérialisable
