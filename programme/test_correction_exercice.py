"""
Tests de la correction complète (étape 6). AUCUN appel réel : Anthropic
(`resolution._appeler_anthropic`) et Wolfram Alpha (`wolfram._requete_http`)
sont simulés ; SymPy, lui, tourne pour de vrai (c'est le contrôle indépendant).
"""

import copy
import inspect
import re
import logging
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from comptes.models import User

from .correction import expressions, resolution, service, verification, wolfram
from .correction.expressions import ExpressionInvalide, analyser
from .correction.verification import verifier_avec_sympy
from .ia.exceptions import IAConfigurationInvalide, IAErreurFournisseur, IAQuotaDepasse, IATimeout
from .models import Cycle, Matiere, Niveau, Programme, Serie

URL = "/api/eleve/correction/"
CACHE_TEST = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "correction-tests"}}


# --------------------------------------------------------------------------
#  Énoncés confirmés (tels que renvoyés par la lecture, étape 5)
# --------------------------------------------------------------------------

def _analyse(enonce, questions, formules=(), **extra):
    base = {
        "lisible": True,
        "matiere": {"valeur": "mathematiques", "confiance": "haute"},
        "niveau": {"valeur": "Terminale C", "confiance": "moyenne"},
        "enonce": enonce,
        "donnees": [],
        "formules": list(formules),
        "questions": [{"numero": n, "texte": t, "incertain": False} for n, t in questions],
        "figures": [], "tableaux": [], "parties_incertaines": [], "remarques": [],
        "concordance_programme": "concorde",
    }
    base.update(extra)
    return base


ANALYSE_EX1 = _analyse("Résoudre $x^2 - 5x + 6 = 0$.", [("1", "Résoudre $x^2 - 5x + 6 = 0$.")])
ANALYSE_EX2 = _analyse(
    "Étudier $f(x) = x^3 - 3x$ : dérivée, variations et extrema.",
    [("1", "Calculer la dérivée de $f$."), ("2", "Étudier les variations de $f$."), ("3", "Déterminer les extrema de $f$.")],
)


def _etape(titre, explication="Explication.", calcul=""):
    return {"titre": titre, "explication": explication, "calcul": calcul}


AFF_EX1 = {
    "type": "equation", "description": "Solutions de $x^2-5x+6=0$", "variable": "x",
    "gauche": "x^2-5x+6", "droite": "0", "solutions": ["2", "3"],
}
CORRECTION_EX1 = {
    "donnees": [{"libelle": "Équation", "valeur": "x^2 - 5x + 6 = 0"}],
    "formules": ["$x^2-5x+6=(x-2)(x-3)$"],
    "questions": [{
        "numero": "1", "enonce": "Résoudre l'équation.",
        "etapes": [
            _etape("Factoriser", "On cherche deux nombres de somme 5 et de produit 6.", "$$x^2-5x+6=(x-2)(x-3)$$"),
            _etape("Produit nul", "Un produit est nul si l'un des facteurs l'est.", "$$x=2 \\text{ ou } x=3$$"),
        ],
        "resultat": "$S=\\{2;3\\}$",
        "verifications": [
            {"type": "egalite", "description": "Factorisation", "gauche": "x^2-5x+6", "droite": "(x-2)(x-3)"},
            dict(AFF_EX1),
        ],
        "incertitudes": [],
    }],
    "conclusion": "Les solutions sont 2 et 3.",
    "incertitudes_generales": [],
}
CORRECTION_EX2 = {
    "donnees": [{"libelle": "Fonction", "valeur": "f(x) = x^3 - 3x"}],
    "formules": ["$(x^n)'=nx^{n-1}$"],
    "questions": [
        {
            "numero": "1", "enonce": "Dérivée.", "etapes": [_etape("Dériver", "Formule de dérivation.", "$$f'(x)=3x^2-3$$")],
            "resultat": "$f'(x)=3x^2-3=3(x-1)(x+1)$",
            "verifications": [
                {"type": "derivee", "description": "Dérivée de f", "fonction": "x^3-3x", "variable": "x", "derivee": "3x^2-3"},
                {"type": "egalite", "description": "Factorisation de f'", "gauche": "3x^2-3", "droite": "3(x-1)(x+1)"},
            ],
            "incertitudes": [],
        },
        {
            "numero": "2", "enonce": "Variations.", "etapes": [_etape("Signe de f'", "f' s'annule en -1 et 1.", "")],
            "resultat": "f croît sur $]-\\infty;-1]$, décroît sur $[-1;1]$, croît sur $[1;+\\infty[$.",
            "verifications": [{
                "type": "variations", "description": "Sens de variation", "fonction": "x^3-3x", "variable": "x",
                "intervalles": [
                    {"borne_inf": "-oo", "borne_sup": "-1", "sens": "croissante"},
                    {"borne_inf": "-1", "borne_sup": "1", "sens": "décroissante"},
                    {"borne_inf": "1", "borne_sup": "+oo", "sens": "croissante"},
                ],
            }],
            "incertitudes": [],
        },
        {
            "numero": "3", "enonce": "Extrema.", "etapes": [_etape("Valeurs", "On calcule f(-1) et f(1).", "$$f(-1)=2,\\ f(1)=-2$$")],
            "resultat": "Maximum local 2 en -1 ; minimum local -2 en 1.",
            "verifications": [
                {"type": "substitution", "description": "f(-1)", "expression": "x^3-3x", "variable": "x", "valeur": "-1", "resultat": "2"},
                {"type": "extrema", "description": "Extrema locaux", "fonction": "x^3-3x", "variable": "x", "extrema": [
                    {"x": "-1", "y": "2", "nature": "maximum local"}, {"x": "1", "y": "-2", "nature": "minimum local"},
                ]},
            ],
            "incertitudes": [],
        },
    ],
    "conclusion": "f admet un maximum local 2 en -1 et un minimum local -2 en 1.",
    "incertitudes_generales": [],
}

USAGE = {"tokens_entree": 2100, "tokens_sortie": 1400}


def _wolfram_simule(requete: str) -> dict:
    """Réponses réalistes de l'API Full Results (format observé lors des essais réels)."""
    def pods(*lots):
        return {"success": True, "error": False, "pods": [{"id": i, "title": i, "subpods": [{"plaintext": t} for t in ts]} for i, ts in lots]}

    if requete.startswith("solve x^2 - 5*x + 6 = 0"):
        return pods(("Input", ["solve x^2 - 5 x + 6 = 0 over the reals"]), ("ResultOverTheReals", ["x = 2", "x = 3"]))
    if requete.startswith("derivative of x^3 - 3*x"):
        return pods(("Input", ["d/dx(x^3 - 3 x) = 3 (x^2 - 1)"]), ("ExpandedForm", ["3 x^2 - 3"]))
    if requete.startswith("solve d/dx(x^3 - 3*x) = 0"):
        return pods(("Input", ["solve 3 x^2 - 3 = 0"]), ("Result", ["x = ±1"]))
    return {"success": False, "error": False, "pods": []}


def _fichier(ia=None, wolf=None):
    """Applique les deux simulations ; renvoie les mocks."""
    return (
        mock.patch.object(resolution, "_appeler_anthropic", return_value=(ia, dict(USAGE))),
        mock.patch.object(wolfram, "_requete_http", side_effect=wolf or _wolfram_simule),
    )


# --------------------------------------------------------------------------
#  Analyseur d'expressions (sécurité)
# --------------------------------------------------------------------------

class ExpressionsTests(SimpleTestCase):
    def test_notations_courantes(self):
        import sympy as sp
        x = sp.Symbol("x", real=True)
        self.assertEqual(sp.expand(analyser("x^2 - 5x + 6")), x**2 - 5 * x + 6)
        self.assertEqual(sp.expand(analyser("(x-2)(x-3)")), x**2 - 5 * x + 6)
        self.assertEqual(analyser("x²"), x**2)
        self.assertEqual(analyser("3x^2−3"), 3 * x**2 - 3)
        self.assertEqual(analyser("2,5"), sp.Rational(5, 2))
        self.assertEqual(analyser("sqrt(4)"), 2)
        self.assertEqual(analyser("-x^2"), -(x**2))
        self.assertEqual(analyser("2^-1"), sp.Rational(1, 2))
        self.assertEqual(analyser("(3 + sqrt(5))/2"), (3 + sp.sqrt(5)) / 2)
        self.assertEqual(analyser("+oo"), sp.oo)

    def test_code_et_expressions_hostiles_refuses(self):
        hostiles = [
            "__import__('os').system('calc')", "open('secret.txt').read()", "x.__class__", "lambda: 1",
            "x; import os", "exec('1')", "eval('1')", "os.system", "x[0]", "x if 1 else 2", "{1:2}", "`ls`",
            "9^9^9^9", "x^100000", "", "   ", "foo(x)", "x" * 400, "(" * 100 + "1" + ")" * 100,
        ]
        for texte in hostiles:
            with self.subTest(texte=texte[:30]):
                with self.assertRaises(ExpressionInvalide):
                    analyser(texte)

    def test_aucun_eval_dans_les_modules_de_verification(self):
        for module in (expressions, verification, wolfram, service, resolution):
            source = inspect.getsource(module)
            for interdit in ("eval(", "exec(", "sympify(", "parse_expr(", "subprocess", "os.system", "__import__"):
                self.assertNotIn(interdit, source, f"{module.__name__}: {interdit}")
            self.assertIsNone(re.search(r"(?<![.\w])compile\(", source), f"{module.__name__}: compile(")

    def test_l_analyseur_n_evalue_jamais_de_python(self):
        with mock.patch("builtins.eval", side_effect=AssertionError("eval appelé")), \
             mock.patch("builtins.exec", side_effect=AssertionError("exec appelé")):
            self.assertEqual(analyser("2+3"), 5)


# --------------------------------------------------------------------------
#  Contrôles SymPy
# --------------------------------------------------------------------------

class SymPyTests(SimpleTestCase):
    def test_equation_exercice_1(self):
        v = verifier_avec_sympy(AFF_EX1)
        self.assertEqual(v.statut, "ok")
        self.assertEqual(sorted(v.trouve), ["2", "3"])

    def test_equation_fausse_est_une_contradiction_avec_la_valeur_correcte(self):
        v = verifier_avec_sympy({**AFF_EX1, "solutions": ["2", "4"]})
        self.assertEqual(v.statut, "contradiction")
        self.assertIn("2, 3", v.detail)

    def test_solution_manquante_ou_en_trop(self):
        self.assertEqual(verifier_avec_sympy({**AFF_EX1, "solutions": ["2"]}).statut, "contradiction")
        self.assertEqual(verifier_avec_sympy({**AFF_EX1, "solutions": ["2", "3", "5"]}).statut, "contradiction")

    def test_aucune_solution_reelle(self):
        base = {"type": "equation", "variable": "x", "gauche": "x^2+1", "droite": "0"}
        self.assertEqual(verifier_avec_sympy({**base, "solutions": ["aucune"]}).statut, "ok")
        self.assertEqual(verifier_avec_sympy({**base, "solutions": ["1"]}).statut, "contradiction")

    def test_solutions_irrationnelles_exactes(self):
        v = verifier_avec_sympy({"type": "equation", "variable": "x", "gauche": "x^2-3x+1", "droite": "0",
                                 "solutions": ["(3+sqrt(5))/2", "(3-sqrt(5))/2"]})
        self.assertEqual(v.statut, "ok")

    def test_derivee(self):
        base = {"type": "derivee", "fonction": "x^3-3x", "variable": "x"}
        self.assertEqual(verifier_avec_sympy({**base, "derivee": "3x^2-3"}).statut, "ok")
        self.assertEqual(verifier_avec_sympy({**base, "derivee": "3(x-1)(x+1)"}).statut, "ok")
        faux = verifier_avec_sympy({**base, "derivee": "3x^2+3"})
        self.assertEqual(faux.statut, "contradiction")
        self.assertIn("3*x^2 - 3", faux.detail)

    def test_egalite_factorisation_et_erreur(self):
        self.assertEqual(verifier_avec_sympy({"type": "egalite", "gauche": "x^2-5x+6", "droite": "(x-2)(x-3)"}).statut, "ok")
        self.assertEqual(verifier_avec_sympy({"type": "egalite", "gauche": "x^2-5x+6", "droite": "(x-2)(x+3)"}).statut, "contradiction")
        self.assertEqual(verifier_avec_sympy({"type": "egalite", "gauche": "sin(x)^2+cos(x)^2", "droite": "1"}).statut, "ok")

    def test_substitution(self):
        base = {"type": "substitution", "expression": "x^3-3x", "variable": "x", "valeur": "-1"}
        self.assertEqual(verifier_avec_sympy({**base, "resultat": "2"}).statut, "ok")
        self.assertEqual(verifier_avec_sympy({**base, "resultat": "-2"}).statut, "contradiction")

    def test_extrema_exercice_2(self):
        base = {"type": "extrema", "fonction": "x^3-3x", "variable": "x"}
        bons = [{"x": "-1", "y": "2", "nature": "maximum local"}, {"x": "1", "y": "-2", "nature": "minimum local"}]
        self.assertEqual(verifier_avec_sympy({**base, "extrema": bons}).statut, "ok")
        # Nature inversée, valeur fausse, extremum oublié : trois contradictions distinctes.
        inverse = [{"x": "-1", "y": "2", "nature": "minimum local"}, bons[1]]
        self.assertEqual(verifier_avec_sympy({**base, "extrema": inverse}).statut, "contradiction")
        faux_y = [{"x": "-1", "y": "3", "nature": "maximum local"}, bons[1]]
        self.assertEqual(verifier_avec_sympy({**base, "extrema": faux_y}).statut, "contradiction")
        self.assertEqual(verifier_avec_sympy({**base, "extrema": bons[:1]}).statut, "contradiction")

    def test_point_d_inflexion_n_est_pas_un_extremum(self):
        v = verifier_avec_sympy({"type": "extrema", "fonction": "x^3", "variable": "x",
                                 "extrema": [{"x": "0", "y": "0", "nature": "minimum local"}]})
        self.assertEqual(v.statut, "contradiction")
        self.assertEqual(verifier_avec_sympy({"type": "extrema", "fonction": "x^3", "variable": "x", "extrema": []}).statut, "ok")

    def test_variations(self):
        base = {"type": "variations", "fonction": "x^3-3x", "variable": "x"}
        bons = [
            {"borne_inf": "-oo", "borne_sup": "-1", "sens": "croissante"},
            {"borne_inf": "-1", "borne_sup": "1", "sens": "décroissante"},
            {"borne_inf": "1", "borne_sup": "+oo", "sens": "croissante"},
        ]
        self.assertEqual(verifier_avec_sympy({**base, "intervalles": bons}).statut, "ok")
        inverses = [{**bons[0], "sens": "décroissante"}] + bons[1:]
        self.assertEqual(verifier_avec_sympy({**base, "intervalles": inverses}).statut, "contradiction")
        melange = [{"borne_inf": "-oo", "borne_sup": "+oo", "sens": "croissante"}]
        self.assertEqual(verifier_avec_sympy({**base, "intervalles": melange}).statut, "contradiction")

    def test_non_verifiable_donne_indisponible_jamais_ok(self):
        self.assertEqual(verifier_avec_sympy({"type": "limite", "fonction": "x"}).statut, "indisponible")
        self.assertEqual(verifier_avec_sympy({**AFF_EX1, "gauche": "f(x)@2"}).statut, "indisponible")
        self.assertEqual(verifier_avec_sympy({**AFF_EX1, "gauche": "__import__('os')"}).statut, "indisponible")
        self.assertEqual(verifier_avec_sympy({"type": "equation", "variable": "x", "gauche": "sin(x)", "droite": "1/2",
                                              "solutions": ["pi/6"]}).statut, "indisponible")  # ensemble infini


# --------------------------------------------------------------------------
#  Wolfram Alpha (réponses simulées)
# --------------------------------------------------------------------------

@override_settings(WOLFRAM_APP_ID="app-id-factice", WOLFRAM_TIMEOUT_SECONDES=5)
class WolframTests(SimpleTestCase):
    def verifier(self, aff, simulation=_wolfram_simule):
        with mock.patch.object(wolfram, "_requete_http", side_effect=simulation) as appel:
            verdict, interroge = wolfram.verifier_avec_wolfram(aff)
        return verdict, interroge, appel

    def test_equation_confirmee(self):
        v, interroge, appel = self.verifier(AFF_EX1)
        self.assertEqual((v.statut, interroge), ("ok", True))
        appel.assert_called_once_with("solve x^2 - 5*x + 6 = 0 for x over the reals")

    def test_equation_contredite(self):
        v, _, _ = self.verifier({**AFF_EX1, "solutions": ["2", "4"]})
        self.assertEqual(v.statut, "contradiction")
        self.assertIn("2, 3", v.detail)

    def test_derivee_confirmee_et_contredite(self):
        base = {"type": "derivee", "fonction": "x^3-3x", "variable": "x"}
        self.assertEqual(self.verifier({**base, "derivee": "3x^2-3"})[0].statut, "ok")
        self.assertEqual(self.verifier({**base, "derivee": "3x^2+3"})[0].statut, "contradiction")

    def test_extrema_points_critiques_avec_plus_ou_moins(self):
        base = {"type": "extrema", "fonction": "x^3-3x", "variable": "x"}
        bons = [{"x": "-1", "y": "2", "nature": "maximum local"}, {"x": "1", "y": "-2", "nature": "minimum local"}]
        self.assertEqual(self.verifier({**base, "extrema": bons})[0].statut, "ok")
        faux = [{"x": "2", "y": "2", "nature": "maximum local"}]
        self.assertEqual(self.verifier({**base, "extrema": faux})[0].statut, "contradiction")

    def test_types_non_pris_en_charge_ne_declenchent_aucune_requete(self):
        for aff in ({"type": "egalite", "gauche": "x", "droite": "x"}, {"type": "substitution"}, {"type": "variations"}):
            v, interroge, appel = self.verifier(aff)
            self.assertEqual((v.statut, interroge), ("indisponible", False))
            appel.assert_not_called()

    def test_panne_et_reponses_inexploitables_sont_indisponibles(self):
        def panne(_):
            raise wolfram.WolframIndisponible("Wolfram Alpha injoignable (URLError).")
        self.assertEqual(self.verifier(AFF_EX1, panne)[0].statut, "indisponible")
        self.assertEqual(self.verifier(AFF_EX1, lambda _: {"success": False, "pods": []})[0].statut, "indisponible")
        bizarre = lambda _: {"success": True, "pods": [{"id": "Result", "subpods": [{"plaintext": "x = __import__('os')"}]}]}  # noqa: E731
        self.assertEqual(self.verifier(AFF_EX1, bizarre)[0].statut, "indisponible")

    @override_settings(WOLFRAM_APP_ID="")
    def test_sans_app_id_aucune_requete(self):
        v, interroge, appel = self.verifier(AFF_EX1)
        self.assertEqual((v.statut, interroge), ("indisponible", False))
        appel.assert_not_called()

    def test_requete_http_ne_divulgue_pas_l_app_id(self):
        import urllib.error
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("https://x/?appid=app-id-factice")):
            with self.assertRaises(wolfram.WolframIndisponible) as ctx:
                wolfram._requete_http("solve x=1")
        self.assertNotIn("app-id-factice", str(ctx.exception))

    def test_requete_http_utilise_l_app_id_du_reglage_en_https(self):
        reponse = mock.MagicMock()
        reponse.__enter__.return_value = reponse
        reponse.read.return_value = b'{"queryresult": {"success": true, "error": false, "pods": []}}'
        with mock.patch("urllib.request.urlopen", return_value=reponse) as appel:
            wolfram._requete_http("solve x=1")
        adresse = appel.call_args.args[0]
        self.assertTrue(adresse.startswith("https://api.wolframalpha.com/v2/query?"))
        self.assertIn("appid=app-id-factice", adresse)


# --------------------------------------------------------------------------
#  Endpoint : bout en bout, avec les API externes simulées
# --------------------------------------------------------------------------

@override_settings(
    CACHES=CACHE_TEST, DEBUG=True, IA_CORRECTION_ACTIVE=True, IA_CORRECTION_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice",
)
class CorrectionExerciceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie_c = Serie.objects.create(niveau=tle, nom="C")
        serie_d = Serie.objects.create(niveau=tle, nom="D")
        maths, physique = Matiere.objects.create(nom="Mathématiques"), Matiere.objects.create(nom="Physique")
        cls.maths_c = Programme.objects.create(matiere=maths, niveau=tle, serie=serie_c)
        cls.physique_c = Programme.objects.create(matiere=physique, niveau=tle, serie=serie_c)
        cls.maths_d = Programme.objects.create(matiere=maths, niveau=tle, serie=serie_d)
        cls.eleve = User.objects.create_user(
            "+22790000021", password="Motdepasse-2026", prenom="E", nom="L",
            role=User.Role.ELEVE, statut=User.Statut.ACTIF, niveau=tle, serie=serie_c,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)
        # Garde-fou de l'étape 5 : la lecture de documents ne doit JAMAIS être rappelée ici.
        lecture = mock.patch("programme.lecture_exercice._envoyer_a_anthropic", side_effect=AssertionError("lecture rappelée"))
        lecture.start()
        self.addCleanup(lecture.stop)

    def demander(self, analyse=ANALYSE_EX1, programme=None, ia=CORRECTION_EX1, wolf=None, client=None):
        corps = {"programme": (programme or self.maths_c).id, "analyse": copy.deepcopy(analyse)}
        p_ia, p_wolf = _fichier(copy.deepcopy(ia), wolf)
        with p_ia as mia, p_wolf as mwolf:
            reponse = (client or self.client).post(URL, corps, format="json")
        self.mia, self.mwolf = mia, mwolf
        return reponse

    # --- Exercice 1 -------------------------------------------------------

    def test_exercice_1_correction_verifiee_par_sympy_et_wolfram(self):
        reponse = self.demander()
        self.assertEqual(reponse.status_code, 200, reponse.content)
        c = reponse.json()["correction"]
        self.assertEqual(c["statut"], "calculs_verifies")
        self.assertEqual(c["resume_verification"], {"controles": 2, "verifies": 2, "contradictions": 0, "non_verifies": 0, "requetes_wolfram": 1})
        question = c["questions"][0]
        self.assertEqual(question["statut"], "verifiee")
        equation = [x for x in question["controles"] if x["type"] == "equation"][0]
        self.assertEqual([m["nom"] for m in equation["methodes"]], ["SymPy", "Wolfram Alpha"])
        self.assertEqual({m["statut"] for m in equation["methodes"]}, {"ok"})
        factorisation = [x for x in question["controles"] if x["type"] == "egalite"][0]
        self.assertEqual([m["nom"] for m in factorisation["methodes"]], ["SymPy"])  # Wolfram non concerné
        self.assertEqual(len(question["etapes"]), 2)
        self.assertEqual(question["resultat"], "$S=\\{2;3\\}$")
        self.mia.assert_called_once()

    def test_la_correction_ne_dit_jamais_demonstration_verifiee(self):
        c = self.demander().json()["correction"]
        texte = str(c).lower()
        self.assertNotIn("démonstration vérifiée", texte)
        self.assertNotIn("entièrement vérifié", texte)
        self.assertIn("raisonnement", c["avertissements"][0])  # portée toujours rappelée

    # --- Exercice 2 -------------------------------------------------------

    def test_exercice_2_derivee_variations_extrema(self):
        reponse = self.demander(ANALYSE_EX2, ia=CORRECTION_EX2)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        c = reponse.json()["correction"]
        self.assertEqual(c["statut"], "calculs_verifies")
        self.assertEqual([q["statut"] for q in c["questions"]], ["verifiee"] * 3)
        r = c["resume_verification"]
        self.assertEqual((r["controles"], r["verifies"], r["contradictions"], r["non_verifies"]), (5, 5, 0, 0))
        self.assertEqual(r["requetes_wolfram"], 2)  # dérivée + points critiques
        wolfram_utilise = {m["statut"] for q in c["questions"] for ctrl in q["controles"] for m in ctrl["methodes"] if m["nom"] == "Wolfram Alpha"}
        self.assertEqual(wolfram_utilise, {"ok"})
        variations = [x for x in c["questions"][1]["controles"]][0]
        self.assertEqual([m["nom"] for m in variations["methodes"]], ["SymPy"])  # variations : SymPy seul

    # --- Contradictions ---------------------------------------------------

    def test_ia_contredite_par_sympy_et_wolfram_est_signalee_et_non_validee(self):
        faux = copy.deepcopy(CORRECTION_EX1)
        faux["questions"][0]["verifications"][1]["solutions"] = ["2", "4"]
        faux["questions"][0]["resultat"] = "$S=\\{2;4\\}$"
        c = self.demander(ia=faux).json()["correction"]
        self.assertEqual(c["statut"], "contradiction")
        self.assertNotEqual(c["statut"], "calculs_verifies")
        self.assertEqual(c["questions"][0]["statut"], "contradiction")
        equation = [x for x in c["questions"][0]["controles"] if x["type"] == "equation"][0]
        self.assertEqual(equation["statut"], "contradiction")
        details = " ".join(m["detail"] for m in equation["methodes"])
        self.assertIn("2, 3", details)  # la valeur correcte est montrée
        self.assertEqual({m["statut"] for m in equation["methodes"]}, {"contradiction"})
        self.assertTrue(any("contredit" in a for a in c["avertissements"]))
        self.assertEqual(c["resume_verification"]["contradictions"], 1)
        self.assertIn("Contradiction", c["libelle_statut"])

    def test_wolfram_contredit_alors_que_sympy_confirme_le_desaccord_est_signale(self):
        def wolfram_faux(requete):
            if requete.startswith("solve x^2"):
                return {"success": True, "error": False, "pods": [{"id": "Result", "subpods": [{"plaintext": "x = 2"}, {"plaintext": "x = 4"}]}]}
            return _wolfram_simule(requete)
        c = self.demander(wolf=wolfram_faux).json()["correction"]
        self.assertEqual(c["statut"], "contradiction")
        equation = [x for x in c["questions"][0]["controles"] if x["type"] == "equation"][0]
        self.assertTrue(equation["desaccord_methodes"])
        self.assertEqual({m["nom"]: m["statut"] for m in equation["methodes"]}, {"SymPy": "ok", "Wolfram Alpha": "contradiction"})

    def test_erreur_de_derivee_dans_l_exercice_2(self):
        faux = copy.deepcopy(CORRECTION_EX2)
        faux["questions"][0]["verifications"][0]["derivee"] = "3x^2+3"
        c = self.demander(ANALYSE_EX2, ia=faux).json()["correction"]
        self.assertEqual(c["statut"], "contradiction")
        self.assertEqual([q["statut"] for q in c["questions"]], ["contradiction", "verifiee", "verifiee"])

    # --- Vérification partielle / non vérifiée ------------------------------

    def test_wolfram_en_panne_sympy_suffit_mais_l_indisponibilite_est_visible(self):
        def panne(_):
            raise wolfram.WolframIndisponible("Wolfram Alpha injoignable (URLError).")
        c = self.demander(wolf=panne).json()["correction"]
        equation = [x for x in c["questions"][0]["controles"] if x["type"] == "equation"][0]
        self.assertEqual(equation["statut"], "verifie")
        self.assertEqual({m["nom"]: m["statut"] for m in equation["methodes"]}, {"SymPy": "ok", "Wolfram Alpha": "indisponible"})

    def test_calcul_non_interpretable_reste_non_verifie(self):
        partielle = copy.deepcopy(CORRECTION_EX1)
        partielle["questions"][0]["verifications"].append(
            {"type": "equation", "description": "x", "variable": "x", "gauche": "f(x)@1", "droite": "0", "solutions": ["1"]}
        )
        c = self.demander(ia=partielle).json()["correction"]
        self.assertEqual(c["statut"], "partiellement_verifiee")
        self.assertEqual(c["questions"][0]["statut"], "partiellement_verifiee")
        self.assertEqual(c["resume_verification"]["non_verifies"], 1)

    def test_question_sans_aucune_affirmation_est_non_verifiee(self):
        sans = copy.deepcopy(CORRECTION_EX1)
        sans["questions"][0]["verifications"] = []
        c = self.demander(ia=sans).json()["correction"]
        self.assertEqual(c["statut"], "non_verifiee")
        self.assertEqual(c["questions"][0]["statut"], "non_verifiee")
        self.assertTrue(any("aucun calcul n'a pu être contrôlé" in a for a in c["avertissements"]))

    def test_incertitude_de_l_ia_empeche_le_statut_calculs_verifies(self):
        doute = copy.deepcopy(CORRECTION_EX1)
        doute["questions"][0]["incertitudes"] = ["La consigne ne précise pas l'ensemble de résolution."]
        c = self.demander(ia=doute).json()["correction"]
        self.assertEqual(c["statut"], "partiellement_verifiee")
        self.assertEqual(c["questions"][0]["incertitudes"], ["La consigne ne précise pas l'ensemble de résolution."])

    def test_question_de_l_enonce_non_traitee_est_signalee(self):
        c = self.demander(ANALYSE_EX2, ia=CORRECTION_EX1_AVEC_NUMERO("1")).json()["correction"]
        self.assertEqual(c["statut"], "partiellement_verifiee")
        self.assertTrue(any("non traitées" in a and "2, 3" in a for a in c["avertissements"]))

    def test_reponse_ia_mal_formee_est_assainie(self):
        abime = {"questions": [{"numero": 1, "etapes": "oups", "verifications": [{"type": "inconnu"}, "x", {"type": "equation"}]}, "pas un dict"],
                 "donnees": "n", "formules": None}
        reponse = self.demander(ia=abime)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        c = reponse.json()["correction"]
        self.assertEqual(c["statut"], "non_verifiee")
        self.assertEqual(c["questions"][0]["controles"][0]["statut"], "non_verifie")

    # --- Refus : on ne résout pas n'importe quoi ----------------------------

    def test_exercice_illisible_n_appelle_aucune_api(self):
        r = self.demander(_analyse("", [], lisible=False))
        self.assertEqual(r.status_code, 400)
        self.assertIn("pas été lu correctement", r.json()["detail"])
        self.mia.assert_not_called(); self.mwolf.assert_not_called()

    def test_partie_incertaine_ou_question_incertaine_refusee(self):
        for analyse in (
            _analyse("x", [("1", "y")], parties_incertaines=[{"page": 1, "extrait": None, "probleme": "tache"}]),
            {**ANALYSE_EX1, "questions": [{"numero": "1", "texte": "?", "incertain": True}]},
        ):
            r = self.demander(analyse)
            self.assertEqual(r.status_code, 400)
            self.assertIn("incertains", r.json()["detail"])
            self.mia.assert_not_called()

    def test_figure_indispensable_non_interpretee_refusee(self):
        analyse = _analyse("Voir la figure.", [("1", "Lire la courbe.")], figures=[{"description": "Courbe coupée", "page": 1, "exploitable": False}])
        r = self.demander(analyse)
        self.assertEqual(r.status_code, 400)
        self.assertIn("figure", r.json()["detail"])
        self.mia.assert_not_called()

    def test_figure_interpretee_est_acceptee(self):
        analyse = _analyse("Voir la courbe.", [("1", "Résoudre $x^2-5x+6=0$.")], figures=[{"description": "Parabole", "page": 1, "exploitable": True}])
        self.assertEqual(self.demander(analyse).status_code, 200)

    def test_matiere_detectee_differente_refusee(self):
        analyse = {**ANALYSE_EX1, "matiere": {"valeur": "physique", "confiance": "haute"}}
        self.assertEqual(self.demander(analyse).status_code, 400)
        self.mia.assert_not_called()

    def test_programme_hors_mathematiques_refuse(self):
        r = self.demander(programme=self.physique_c)
        self.assertEqual(r.status_code, 400)
        self.assertIn("mathématiques", r.json()["detail"])
        self.mia.assert_not_called()

    def test_enonce_vide_refuse(self):
        self.assertEqual(self.demander(_analyse("", [])).status_code, 400)

    # --- Accès et activation --------------------------------------------------

    def test_programme_d_une_autre_classe_404_sans_appel(self):
        r = self.demander(programme=self.maths_d)
        self.assertEqual(r.status_code, 404)
        self.mia.assert_not_called(); self.mwolf.assert_not_called()

    def test_non_authentifie_401(self):
        r = self.demander(client=APIClient())
        self.assertEqual(r.status_code, 401)
        self.mia.assert_not_called()

    @override_settings(IA_CORRECTION_ACTIVE=False)
    def test_desactivee_par_defaut_aucun_appel(self):
        r = self.demander()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["code"], "correction_desactivee")
        self.mia.assert_not_called(); self.mwolf.assert_not_called()

    @override_settings(DEBUG=False)
    def test_hors_developpement_aucun_appel_meme_si_active(self):
        self.assertEqual(self.demander().status_code, 503)
        self.mia.assert_not_called()

    @override_settings(DEBUG=False, IA_CORRECTION_DEV_SEULEMENT=False)
    def test_ouverture_explicite_hors_developpement(self):
        r = self.demander()
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("meta_dev", r.json())

    def test_les_reglages_par_defaut_sont_desactives(self):
        from .reglages_defaut import reglages_par_defaut
        reglages = reglages_par_defaut()  # indépendant du .env local
        self.assertIs(reglages.IA_CORRECTION_ACTIVE, False)
        self.assertIs(reglages.IA_CORRECTION_DEV_SEULEMENT, True)

    def test_programme_manquant_ou_corps_invalide(self):
        r = self.client.post(URL, {"analyse": ANALYSE_EX1}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(URL, {"programme": self.maths_c.id, "analyse": "texte"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(URL, {"programme": self.maths_c.id, "analyse": {"enonce": "x" * 70000}}, format="json")
        self.assertEqual(r.status_code, 400)

    # --- Coûts : cache, verrou, suivi -----------------------------------------

    def test_double_soumission_un_seul_appel_payant(self):
        premiere = self.demander().json()
        seconde = self.demander().json()
        self.assertIs(premiere["correction_depuis_cache"], False)
        self.assertIs(seconde["correction_depuis_cache"], True)
        self.assertEqual(premiere["correction"], seconde["correction"])
        self.mia.assert_not_called()   # le second tour n'a rien appelé
        self.mwolf.assert_not_called()

    def test_enonce_different_relance_une_correction(self):
        self.demander()
        self.demander(_analyse("Résoudre $x^2 - 7x + 12 = 0$.", [("1", "Résoudre.")]))
        self.mia.assert_called_once()

    def test_le_cache_est_propre_a_chaque_eleve(self):
        self.demander()
        autre = User.objects.create_user(
            "+22790000022", password="Motdepasse-2026", prenom="A", nom="B", role=User.Role.ELEVE,
            statut=User.Statut.ACTIF, niveau=self.eleve.niveau, serie=self.eleve.serie,
        )
        client = APIClient(); client.force_authenticate(autre)
        r = self.demander(client=client).json()
        self.assertIs(r["correction_depuis_cache"], False)

    def test_correction_deja_en_cours_409_sans_appel(self):
        analyse = service.normaliser_analyse(copy.deepcopy(ANALYSE_EX1), service.ContexteProgramme("Mathématiques", "Terminale C"))
        cache.add(f"correction:verrou:{service._empreinte(self.eleve.id, self.maths_c.id, analyse)}", 1, timeout=60)
        r = self.demander()
        self.assertEqual(r.status_code, 409)
        self.mia.assert_not_called()

    def test_echec_ia_relache_le_verrou_et_n_est_pas_mis_en_cache(self):
        with mock.patch.object(resolution, "_appeler_anthropic", side_effect=IATimeout("lent")):
            r = self.client.post(URL, {"programme": self.maths_c.id, "analyse": ANALYSE_EX1}, format="json")
        self.assertEqual(r.status_code, 504)
        r = self.demander()
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()["correction_depuis_cache"], False)

    def test_erreurs_fournisseur_messages_francais_sans_fuite(self):
        cas = ((IAConfigurationInvalide("cle-factice-pour-les-tests"), 503, "pas configurée"), (IAQuotaDepasse("429 sk-ant-x"), 503, "saturé"),
               (IATimeout("t"), 504, "trop de temps"), (IAErreurFournisseur("http 500"), 502, "a échoué"))
        for i, (erreur, code, extrait) in enumerate(cas):
            cache.clear()
            with mock.patch.object(resolution, "_appeler_anthropic", side_effect=erreur):
                r = self.client.post(URL, {"programme": self.maths_c.id, "analyse": ANALYSE_EX1}, format="json")
            self.assertEqual(r.status_code, code)
            self.assertIn(extrait, r.json()["detail"])
            self.assertNotIn("cle-factice", r.content.decode()); self.assertNotIn("sk-ant", r.content.decode())

    def test_suivi_des_tokens_en_dev_et_dans_les_journaux(self):
        with self.assertLogs("programme.correction.service", level=logging.INFO) as journaux:
            r = self.demander().json()
        self.assertEqual(r["meta_dev"], {"modele": "claude-sonnet-5", "tokens_entree": 2100, "tokens_sortie": 1400})
        self.assertTrue(any("tokens_entree=2100" in l and "tokens_sortie=1400" in l for l in journaux.output))
        self.assertFalse(any("app-id-factice" in l or "cle-factice" in l for l in journaux.output))
        self.assertNotIn("meta_dev", self.demander().json())  # servi du cache : rien de consommé

    def test_au_plus_15_requetes_wolfram_par_correction(self):
        lourde = copy.deepcopy(CORRECTION_EX1)
        lourde["questions"] = [dict(CORRECTION_EX1["questions"][0], numero=str(i)) for i in range(1, 4)]
        lourde["questions"][0]["verifications"] = [dict(AFF_EX1) for _ in range(8)]
        lourde["questions"][1]["verifications"] = [dict(AFF_EX1) for _ in range(8)]
        analyse = _analyse("e", [("1", "a"), ("2", "b"), ("3", "c")])
        c = self.demander(analyse, ia=lourde).json()["correction"]
        self.assertLessEqual(c["resume_verification"]["requetes_wolfram"], 15)
        self.assertEqual(self.mwolf.call_count, c["resume_verification"]["requetes_wolfram"])

    # --- Requête Anthropic -----------------------------------------------------

    @override_settings(IA_CORRECTION_MODELE="modele-de-correction", IA_CORRECTION_MAX_TOKENS=9999, IA_CORRECTION_TIMEOUT_SECONDES=77)
    def test_requete_envoyee_a_anthropic(self):
        reponse = SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name=resolution.NOM_OUTIL, input=copy.deepcopy(CORRECTION_EX1))],
            stop_reason="tool_use", usage=SimpleNamespace(input_tokens=11, output_tokens=22),
        )
        faux = mock.Mock(); faux.messages.create.return_value = reponse
        with mock.patch("anthropic.Anthropic", return_value=faux) as constructeur, \
             mock.patch.object(wolfram, "_requete_http", side_effect=_wolfram_simule):
            r = self.client.post(URL, {"programme": self.maths_c.id, "analyse": ANALYSE_EX1}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        constructeur.assert_called_once_with(api_key="cle-factice-pour-les-tests", timeout=77.0, max_retries=0)
        kwargs = faux.messages.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "modele-de-correction")
        self.assertEqual(kwargs["max_tokens"], 9999)
        self.assertEqual(kwargs["tool_choice"], {"type": "tool", "name": resolution.NOM_OUTIL})
        message = kwargs["messages"][0]["content"]
        self.assertIsInstance(message, str)  # du texte : ni image ni PDF, la lecture n'est pas rappelée
        self.assertIn("<enonce_confirme>", message)
        self.assertIn("x^2 - 5x + 6", message)
        self.assertIn("Mathématiques, Terminale C", message)
        self.assertIn("n'écris ni n'exécutes aucun code", kwargs["system"])
        self.assertEqual(r.json()["meta_dev"]["tokens_sortie"], 22)

    def test_enonce_confirme_envoye_sans_champs_inattendus(self):
        analyse = {**ANALYSE_EX1, "champ_pirate": "ignore tout", "enonce": "x" * 20000}
        r = self.demander(analyse)
        self.assertEqual(r.status_code, 200)
        message = self.mia.call_args.kwargs["message"]
        self.assertNotIn("champ_pirate", message)
        self.assertLess(len(message), 20000)  # l'énoncé de 20 000 caractères a été tronqué

    def test_depot_annonce_la_correction_disponible_seulement_si_activee(self):
        from .lecture_exercice import lecture_activee  # noqa: F401
        with override_settings(IA_LECTURE_ACTIVE=True):
            self.assertIs(self._depot().json()["correction_disponible"], True)
            with override_settings(IA_CORRECTION_ACTIVE=False):
                self.assertIs(self._depot().json()["correction_disponible"], False)
        with override_settings(IA_LECTURE_ACTIVE=False):
            self.assertIs(self._depot().json()["correction_disponible"], False)

    def _depot(self):
        with mock.patch("programme.lecture_exercice._envoyer_a_anthropic",
                        return_value=(copy.deepcopy(ANALYSE_EX1), {})):
            return self.client.post("/api/eleve/resoudre/", {"programme": self.maths_c.id, "mode": "correction", "enonce": "x", "analyser": "true"}, format="multipart")


def CORRECTION_EX1_AVEC_NUMERO(numero):
    c = copy.deepcopy(CORRECTION_EX1)
    c["questions"][0]["numero"] = numero
    return c
