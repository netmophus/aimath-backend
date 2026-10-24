"""
Tests du premier catalogue de simulations mathématiques (étape 9.3) : plan complexe, suites récurrentes, géométrie du
triangle. Aucun appel réel : la sélection est déterministe ; aucune IA n'intervient.
"""

import copy

from django.test import SimpleTestCase, override_settings

from .simulations.catalogue import CATALOGUE, ParametresInvalides, valider_simulation
from .simulations.selection import projeter_pour_professeur, simulations_pour_question
from .test_correction_exercice import _analyse

COMPLEXE = ("Soit $z = 3 + 2i$.", [("1", "Représenter $z$ dans le plan complexe."), ("2", "Déterminer son module."), ("3", "Représenter son conjugué.")])
SUITE = (
    "Soit $(u_n)$ la suite définie par $u_0 = 5$ et $u_{n+1} = \\frac{1}{2}u_n + 3$.",
    [("1", "Calculer $u_1$ et $u_2$."), ("2", "Étudier le comportement de la suite."), ("3", "Représenter graphiquement les premiers termes.")],
)
TRIANGLE = (
    "Dans un repère orthonormé, on considère $A(0 ; 0)$, $B(4 ; 0)$ et $C(0 ; 3)$.",
    [("1", "Placer les points $A$, $B$ et $C$."), ("2", "Construire le triangle $ABC$."), ("3", "Calculer $AB$, $AC$ et $BC$."), ("4", "Déterminer la nature du triangle $ABC$.")],
)


def _sims(cas, numero, resultat=""):
    enonce, questions = cas
    texte = dict(questions)[numero]
    return simulations_pour_question(_analyse(enonce, questions), "mathematiques", texte, numero, resultat)


def _une(cas, numero):
    sims = _sims(cas, numero)
    assert len(sims) == 1, (numero, sims)
    return sims[0]


@override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True)
class PlanComplexeTests(SimpleTestCase):
    def test_exercice_de_reference(self):
        point = _une(COMPLEXE, "1")
        self.assertEqual(point["modele"], "plan_complexe")
        self.assertEqual((point["parametres"]["a"], point["parametres"]["b"], point["parametres"]["presentation"]), (3, 2, "point"))
        module = _une(COMPLEXE, "2")["parametres"]
        self.assertEqual((module["presentation"], module["module"]), ("module", {"coef": 1, "rad": 13}))
        conj = _une(COMPLEXE, "3")["parametres"]
        self.assertEqual((conj["presentation"], conj["a"], conj["b"]), ("conjugue", 3, 2))  # le front trace M'(3 ; −2)
        self.assertEqual(_une(COMPLEXE, "2")["verification"]["methodes"], ["SymPy", "Calcul exact"])

    def test_module_avec_radical_simplifie(self):
        cas = ("Soit $z = 2 + 4i$.", [("1", "Calculer le module de $z$.")])
        self.assertEqual(_une(cas, "1")["parametres"]["module"], {"coef": 2, "rad": 5})

    def test_argument_exact_ou_en_radians(self):
        cas = ("Soit $z = 1 + i$.", [("1", "Déterminer un argument de $z$.")])
        arg = _une(cas, "1")["parametres"]["argument"]
        self.assertEqual(arg["exact"], "π/4")
        cas = ("Soit $z = 3 + 2i$.", [("1", "Déterminer un argument de $z$.")])
        arg = _une(cas, "1")["parametres"]["argument"]
        self.assertIsNone(arg["exact"])
        self.assertAlmostEqual(arg["radians"], 0.588003, places=5)

    def test_enonces_ambigus_ou_hors_cadre_sans_simulation(self):
        for enonce in ("Soit $z = 3 + 2i$ et $z = 1 + i$.", "Soit $z = 1,5 + 2i$.", "Soit $z = 100 + 2i$.", "Soit $z = 3$."):
            self.assertEqual(_sims((enonce, [("1", "Représenter $z$ dans le plan complexe.")]), "1"), [], enonce)

    def test_parametres_invalides_refuses(self):
        valide = _une(COMPLEXE, "2")
        for modif in (
            lambda p: p.update(a=60),
            lambda p: p.update(module={"coef": 1, "rad": 14}),
            lambda p: p.update(extra=1),
            lambda p: p.update(presentation="inconnue"),
            lambda p: p.update(nom="x; Delete(a)"),
            lambda p: p.pop("module"),
        ):
            faux = copy.deepcopy(valide)
            modif(faux["parametres"])
            with self.assertRaises(ParametresInvalides):
                valider_simulation(faux)

    def test_projection_pour_le_professeur_etape_9_4(self):
        for numero in "123":
            sim = _une(COMPLEXE, numero)
            self.assertEqual(projeter_pour_professeur(sim)["parametres"], sim["parametres"])  # chaque présentation ne porte que son contenu


@override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True)
class SuiteRecurrenteTests(SimpleTestCase):
    def test_exercice_de_reference(self):
        termes = _une(SUITE, "1")["parametres"]
        self.assertEqual(termes["presentation"], "termes")
        self.assertEqual(termes["termes"][:3], ["5", "11/2", "23/4"])
        self.assertEqual(termes["limite"], "6")
        self.assertEqual((termes["a"], termes["b"], termes["n0"], termes["demande"]), ("1/2", "3", 0, 2))
        self.assertIsNone(_une(SUITE, "2")["parametres"]["demande"])  # étude du comportement : pas de calcul demandé
        self.assertIsNone(_une(SUITE, "3")["parametres"]["demande"])  # représentation graphique
        self.assertLessEqual(len(termes["termes"]), 10)
        self.assertEqual(_une(SUITE, "2")["parametres"]["presentation"], "escalier")
        self.assertEqual(_une(SUITE, "3")["parametres"]["presentation"], "termes")

    def test_forme_unicode(self):
        cas = ("Soit la suite (u_n) définie par u₀ = 5 et uₙ₊₁ = 0,5 uₙ + 3.", [("1", "Calculer u₁ et u₂.")])
        p = _une(cas, "1")["parametres"]
        self.assertEqual(p["termes"][:3], ["5", "11/2", "23/4"])

    def test_pas_de_limite_annoncee_si_la_suite_diverge(self):
        cas = ("Soit $(u_n)$ définie par $u_0 = 1$ et $u_{n+1} = 2u_n + 1$.", [("1", "Calculer les premiers termes de la suite.")])
        p = _une(cas, "1")["parametres"]
        self.assertIsNone(p["limite"])
        self.assertEqual(p["termes"][:4], ["1", "3", "7", "15"])

    def test_recurrence_non_affine_ou_ambigue_sans_simulation(self):
        for enonce in (
            "Soit $(u_n)$ définie par $u_0 = 1$ et $u_{n+1} = u_n^2 + 1$.",
            "Soit $(u_n)$ définie par $u_0 = 1$ et $u_{n+1} = 2u_n + 1$ et $u_{n+1} = 3u_n$.",
            "Soit $(u_n)$ définie par $u_{n+1} = 2u_n + 1$.",
        ):
            self.assertEqual(_sims((enonce, [("1", "Calculer les premiers termes de la suite.")]), "1"), [], enonce)

    def test_parametres_falsifies_refuses(self):
        valide = _une(SUITE, "2")
        for modif in (
            lambda p: p["termes"].__setitem__(1, "6"),
            lambda p: p.update(limite="7"),
            lambda p: p.update(termes=p["termes"] + ["1"] * 20),
            lambda p: p.update(a="1/0"),
            lambda p: p.update(extra=True),
        ):
            faux = copy.deepcopy(valide)
            modif(faux["parametres"])
            with self.assertRaises(ParametresInvalides):
                valider_simulation(faux)

    def test_projection_pour_le_professeur_etape_9_4(self):
        reduite = projeter_pour_professeur(_une(SUITE, "1"))["parametres"]
        self.assertEqual(reduite["termes"], ["5", "11/2", "23/4"])  # seulement les termes demandés
        self.assertNotIn("limite", reduite)
        self.assertEqual(reduite["demande"], 2)
        escalier = projeter_pour_professeur(_une(SUITE, "2"))["parametres"]
        self.assertEqual((escalier["limite"], len(escalier["termes"])), ("6", 10))  # l'escalier est la réponse de sa question
        graphique = projeter_pour_professeur(_une(SUITE, "3"))["parametres"]
        self.assertNotIn("limite", graphique)  # jamais la limite dans une présentation « termes »
        self.assertEqual(len(graphique["termes"]), 10)


@override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True)
class GeometrieTriangleTests(SimpleTestCase):
    def test_exercice_de_reference(self):
        points = _une(TRIANGLE, "1")["parametres"]
        self.assertEqual(points["presentation"], "points")
        self.assertEqual([(q["nom"], q["x"], q["y"]) for q in points["points"]], [("A", 0, 0), ("B", 4, 0), ("C", 0, 3)])
        self.assertEqual(_une(TRIANGLE, "2")["parametres"]["presentation"], "triangle")
        d = _une(TRIANGLE, "3")["parametres"]
        self.assertEqual(d["presentation"], "distances")
        self.assertEqual(d["longueurs"], {"AB": {"coef": 4, "rad": 1}, "AC": {"coef": 3, "rad": 1}, "BC": {"coef": 5, "rad": 1}})
        n = _une(TRIANGLE, "4")["parametres"]
        self.assertEqual((n["presentation"], n["nature"]), ("nature", {"type": "rectangle", "sommet_droit": "A"}))

    def test_longueur_irrationnelle(self):
        cas = ("Dans un repère orthonormé, on considère $A(0 ; 0)$ et $B(2 ; 4)$.", [("1", "Calculer la distance $AB$.")])
        self.assertEqual(_une(cas, "1")["parametres"]["longueurs"]["AB"], {"coef": 2, "rad": 5})

    def test_cas_ambigus_ou_hors_cadre_sans_simulation(self):
        q = [("1", "Construire le triangle $ABC$.")]
        for enonce in (
            "On considère $A(0 ; 0)$, $B(4 ; 0)$ et $C(0 ; 3)$.",  # repère non précisé orthonormé
            "Dans un repère orthonormé, on considère $A(0 ; 0)$, $B(2 ; 2)$ et $C(4 ; 4)$.",  # alignés
            "Dans un repère orthonormé, on considère $A(0 ; 0)$, $B(1,5 ; 0)$ et $C(0 ; 3)$.",  # non entier
            "Dans un repère non orthonormé, on considère $A(0 ; 0)$, $B(4 ; 0)$ et $C(0 ; 3)$.",
        ):
            self.assertEqual(_sims((enonce, q), "1"), [], enonce)

    def test_parametres_falsifies_refuses(self):
        valide = _une(TRIANGLE, "4")
        for modif in (
            lambda p: p["longueurs"]["BC"].update(coef=6),
            lambda p: p["nature"].update(type="equilateral"),
            lambda p: p["points"][0].update(x=99),
            lambda p: p["points"].pop(),
            lambda p: p.update(extra=1),
        ):
            faux = copy.deepcopy(valide)
            modif(faux["parametres"])
            with self.assertRaises(ParametresInvalides):
                valider_simulation(faux)

    def test_le_modele_vectoriel_garde_ses_exercices(self):
        cas = ("Dans un repère orthonormé, on considère les points A(1 ; 2) et B(4 ; 3).", [("1", "Représenter le vecteur AB.")])
        sims = _sims(cas, "1")
        self.assertEqual([s["modele"] for s in sims], ["vecteur_deux_points"])

    def test_projection_pour_le_professeur_etape_9_4(self):
        for numero in "123":
            sim = _une(TRIANGLE, numero)
            self.assertEqual(projeter_pour_professeur(sim)["parametres"], sim["parametres"])
        nature = projeter_pour_professeur(_une(TRIANGLE, "4"))["parametres"]
        self.assertEqual(sorted(nature), ["nature", "points", "presentation"])  # sans les longueurs


class ReglagesTests(SimpleTestCase):
    @override_settings(SIMULATIONS_ACTIVES=False)
    def test_desactivees(self):
        from .simulations.selection import avec_simulations

        correction = {"questions": [{"numero": "1", "resultat": ""}]}
        self.assertEqual(avec_simulations(correction, _analyse(*COMPLEXE), "Mathématiques"), correction)

    @override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=False)
    def test_aucune_simulation_en_production(self):
        from .simulations.selection import avec_simulations

        correction = {"questions": [{"numero": "1", "resultat": ""}]}
        self.assertEqual(avec_simulations(correction, _analyse(*TRIANGLE), "Mathématiques"), correction)

    @override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True)
    def test_matiere_non_mathematique_sans_simulation(self):
        enonce, questions = COMPLEXE
        self.assertEqual(simulations_pour_question(_analyse(enonce, questions), "physique", questions[0][1], "1", ""), [])
