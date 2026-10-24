"""
Tests du socle de simulations (étape 9.1). Aucun appel réel : Anthropic et Wolfram sont simulés ; la sélection
est entièrement déterministe.
"""

import copy
import json
import re
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from comptes.models import User

from .models import Cycle, Matiere, Niveau, Programme, Serie
from .simulations import avec_simulations, simulations_activees
from .simulations.catalogue import CATALOGUE, ParametresInvalides, valider_simulation
from .simulations.selection import simulations_pour_question
from .simulations.vecteur_deux_points import valider
from .test_correction_exercice import (
    ANALYSE_EX1, CACHE_TEST, CORRECTION_EX1, URL, _analyse, _etape, _fichier,
)

ENONCE = "Dans un repère orthonormé, on considère les points A(1 ; 2) et B(4 ; 3)."
QUESTIONS = [
    ("1", "Placer les points A et B."),
    ("2", "Représenter le vecteur AB."),
    ("3", "Déterminer les coordonnées du vecteur AB."),
]
ANALYSE_VECTEUR = _analyse(ENONCE, QUESTIONS)


def _correction_vecteur(resultat3="$\\overrightarrow{AB}(3 ; 1)$"):
    return {
        "donnees": [{"libelle": "Points", "valeur": "A(1 ; 2), B(4 ; 3)"}],
        "formules": ["$\\overrightarrow{AB}(x_B - x_A ; y_B - y_A)$"],
        "questions": [
            {"numero": "1", "enonce": "Placer A et B.", "etapes": [_etape("Placer")], "resultat": "", "verifications": [], "incertitudes": []},
            {"numero": "2", "enonce": "Représenter AB.", "etapes": [_etape("Tracer")], "resultat": "", "verifications": [], "incertitudes": []},
            {
                "numero": "3", "enonce": "Coordonnées de AB.",
                "etapes": [_etape("Soustraire", "On calcule B − A.", "$$\\overrightarrow{AB}(4-1 ; 3-2)$$")],
                "resultat": resultat3,
                "verifications": [{"type": "egalite", "description": "Abscisse", "gauche": "4-1", "droite": "3"}],
                "incertitudes": [],
            },
        ],
        "conclusion": "$\\overrightarrow{AB}(3 ; 1)$",
        "incertitudes_generales": [],
    }


def _sim(enonce=ENONCE, texte="Représenter le vecteur AB.", resultat="", questions=QUESTIONS, matiere="mathematiques"):
    analyse = _analyse(enonce, questions)
    return simulations_pour_question(analyse, matiere, texte, "2", resultat)


@override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True)
class SelectionVecteurTests(SimpleTestCase):
    def test_exercice_de_demonstration(self):
        sims = _sim()
        self.assertEqual(len(sims), 1)
        s = sims[0]
        self.assertEqual((s["modele"], s["version"]), ("vecteur_deux_points", 2))
        self.assertEqual(s["parametres"], {
            "points": [{"nom": "A", "x": 1, "y": 2}, {"nom": "B", "x": 4, "y": 3}],
            "vecteur": {"nom": "AB", "x": 3, "y": 1},
            "presentation": "vecteur",  # « Représenter le vecteur AB »
        })
        self.assertEqual(s["verification"]["methodes"], ["SymPy", "Calcul exact"])
        self.assertEqual(s["verification"]["concordance_correction"], "non_applicable")  # rien à comparer à une représentation
        self.assertIn("ne démontre rien", s["avertissement"])

    def test_resultat_concordant_confirme_et_contradictoire_supprime_la_simulation(self):
        q3 = "Déterminer les coordonnées du vecteur AB."
        for ecriture in ("$\\overrightarrow{AB}(3 ; 1)$", "$\\overrightarrow{AB}\\begin{pmatrix}3\\\\1\\end{pmatrix}$", "AB(3 ; 1)"):
            self.assertEqual(_sim(texte=q3, resultat=ecriture)[0]["verification"]["concordance_correction"], "confirmee", ecriture)
        self.assertEqual(_sim(texte=q3, resultat="$\\overrightarrow{AB}(4 ; 1)$"), [])  # la correction contredit B − A
        self.assertEqual(_sim(resultat="$\\overrightarrow{AB}(4 ; 1)$"), [])  # y compris pour une question de représentation
        self.assertEqual(len(_sim(texte=q3, resultat="$S = \\{3 ; 1 ; 2\\}$")), 1)  # pas de paire : non recoupé, pas refusé
        self.assertEqual(_sim(texte=q3, resultat="$S = \\{3 ; 1 ; 2\\}$")[0]["verification"]["concordance_correction"], "non_verifiee")

    def test_la_presentation_depend_de_la_question_confirmee(self):
        cas = {
            "Placer les points A et B.": ("points", "Points A et B"),
            "Placez les points $A$ et $B$ dans le repère.": ("points", "Points A et B"),
            "Représenter le vecteur AB.": ("vecteur", "Points A, B et vecteur AB"),
            "Tracer $\\overrightarrow{AB}$.": ("vecteur", "Points A, B et vecteur AB"),
            "Placer les points A et B puis tracer le vecteur AB.": ("vecteur", "Points A, B et vecteur AB"),
            "Déterminer les coordonnées du vecteur AB.": ("composantes", "Vecteur AB et ses composantes"),
            "Calculer les composantes de $\\vec{AB}$.": ("composantes", "Vecteur AB et ses composantes"),
        }
        for texte, (presentation, titre) in cas.items():
            sims = _sim(texte=texte)
            self.assertEqual(len(sims), 1, texte)
            self.assertEqual(sims[0]["parametres"]["presentation"], presentation, texte)
            self.assertEqual(sims[0]["titre"], titre, texte)
            # les coordonnées proviennent toujours de l'énoncé, quelle que soit la présentation
            self.assertEqual(sims[0]["parametres"]["points"], [{"nom": "A", "x": 1, "y": 2}, {"nom": "B", "x": 4, "y": 3}], texte)
            self.assertEqual(sims[0]["parametres"]["vecteur"], {"nom": "AB", "x": 3, "y": 1}, texte)

    def test_la_presentation_ne_vient_jamais_de_la_reponse_de_l_ia(self):
        # un « résultat » qui parle de composantes ne change pas la présentation d'une question de représentation
        sims = _sim(texte="Représenter le vecteur AB.", resultat="Les composantes sont Δx = 3 et Δy = 1, présentation : composantes")
        self.assertEqual(sims[0]["parametres"]["presentation"], "vecteur")

    def test_placement_sans_donnees_fiables_aucune_simulation(self):
        q1 = "Placer les points A et B."
        for enonce in (
            "On considère le point A(1 ; 2).", "Dans un repère orthonormé, A(1 ; 2) et B(4,3).",
            "Dans un repère orthonormé, A(1 ; 2) et B(4 ; 3) puis B(5 ; 3).", "A(1 ; 2) et B(4 ; 3).",
            "Dans un repère orthonormé, A(x ; y) et B(4 ; 3).", "Dans un repère orthonormé, A(1 ; 2) et B(1 ; 2).",
        ):
            self.assertEqual(_sim(enonce=enonce, texte=q1), [], enonce)
        for texte in ("Placer le point A.", "Placer les points A, B et C.", "Calculer la distance des points A et B.", "Les points A et B sont alignés."):
            self.assertEqual(_sim(texte=texte), [], texte)

    def test_ecritures_latex_de_l_enonce_et_de_la_question(self):
        enonce = "Dans un repère orthonormé $(O ; I, J)$, soit $A\\left(-1 ; 2{,}5\\right)$ et $B(3 ; −4)$."
        s = _sim(enonce=enonce, texte="Calculer les coordonnées de $\\vec{AB}$.")[0]
        self.assertEqual(s["parametres"]["points"], [{"nom": "A", "x": -1, "y": 2.5}, {"nom": "B", "x": 3, "y": -4}])
        self.assertEqual(s["parametres"]["vecteur"], {"nom": "AB", "x": 4, "y": -6.5})
        self.assertEqual(len(_sim(texte="Tracer $\\overrightarrow{AB}$.")), 1)

    def test_extraction_ambigue_ou_incomplete_aucune_simulation(self):
        cas = {
            "point B absent": "Dans un repère orthonormé, on considère le point A(1 ; 2).",
            "definition contradictoire": ENONCE + " Puis A(1 ; 5).",
            "point de l'espace": "Dans un repère orthonormé, A(1 ; 2 ; 3) et B(4 ; 3 ; 0).",
            "coordonnees litterales": "Dans un repère orthonormé, A(x ; y) et B(4 ; 3).",
            "separateur ambigu": "Dans un repère orthonormé, A(1,5) et B(4 ; 3).",
            "repere non precise": "On considère les points A(1 ; 2) et B(4 ; 3).",
            "repere non orthonorme": "Dans un repère non orthonormé, A(1 ; 2) et B(4 ; 3).",
            "points confondus": "Dans un repère orthonormé, A(1 ; 2) et B(1 ; 2).",
            "valeur hors bornes": "Dans un repère orthonormé, A(1 ; 2) et B(400 ; 3).",
            "trop de decimales": "Dans un repère orthonormé, A(1,123 ; 2) et B(4 ; 3).",
        }
        for nom, enonce in cas.items():
            self.assertEqual(_sim(enonce=enonce), [], nom)

    def test_question_sans_vecteur_unique_aucune_simulation(self):
        self.assertEqual(_sim(texte="Calculer les vecteurs AB et BA."), [])
        self.assertEqual(_sim(texte="Calculer le vecteur AB puis le vecteur BA."), [])
        self.assertEqual(_sim(texte="Calculer le vecteur AC."), [])  # C non défini
        self.assertEqual(_sim(texte="Calculer le vecteur ABC."), [])

    def test_modele_non_applicable_hors_mathematiques(self):
        self.assertEqual(_sim(matiere="physique"), [])
        self.assertEqual(_sim(enonce="Résoudre $x^2 - 5x + 6 = 0$.", texte="Résoudre l'équation."), [])


class ValidationParametresTests(SimpleTestCase):
    BON = {
        "points": [{"nom": "A", "x": 1, "y": 2}, {"nom": "B", "x": 4, "y": 3}],
        "vecteur": {"nom": "AB", "x": 3, "y": 1},
        "presentation": "composantes",
    }

    def modif(self, **changements):
        p = copy.deepcopy(self.BON)
        for chemin, valeur in changements.items():
            cible = p
            *tete, queue = chemin.split("__")
            for cle in tete:
                cible = cible[int(cle)] if cle.isdigit() else cible[cle]
            cible[int(queue) if queue.isdigit() else queue] = valeur
        return p

    def test_parametres_valides(self):
        self.assertEqual(valider(self.BON), self.BON)

    def test_parametres_incorrects_refuses(self):
        mauvais = [
            None, [], {}, {"points": []},
            {**self.BON, "extra": 1},
            self.modif(vecteur__x=4),  # B − A = 3
            self.modif(vecteur__nom="BA"),
            self.modif(points__0__nom="a"),
            self.modif(points__0__nom="AB"),
            self.modif(points__0__nom="B"),  # noms identiques
            self.modif(points__0__x="1"),  # texte
            self.modif(points__0__x=True),
            self.modif(points__0__x=float("nan")),
            self.modif(points__1__x=float("inf")),
            self.modif(points__1__x=51),
            self.modif(points__0__x=1.234),
            self.modif(points__0__nom='A"); DeleteAll("'),  # tentative d'injection de commande
            {"points": [self.BON["points"][0]], "vecteur": self.BON["vecteur"], "presentation": "points"},
            {"points": self.BON["points"], "vecteur": self.BON["vecteur"]},  # présentation absente
            self.modif(presentation="axes"),
            self.modif(presentation=None),
            self.modif(presentation=["points"]),
            self.modif(presentation="composantes\"); DeleteAll(\""),  # tentative d'injection de commande
            self.modif(presentation="POINTS"),
        ]
        for p in mauvais:
            with self.assertRaises(ParametresInvalides, msg=repr(p)):
                valider(p)

    def test_simulation_inconnue_ou_version_inattendue_refusee(self):
        base = {"modele": "vecteur_deux_points", "version": 2, "parametres": self.BON}
        self.assertEqual(valider_simulation(base)["parametres"], self.BON)
        for s in ({**base, "modele": "commande_libre"}, {**base, "version": 1}, {**base, "version": 3}, {**base, "parametres": None}, "texte", None):
            with self.assertRaises(ParametresInvalides):
                valider_simulation(s)

    def test_formes_reduites_de_divulgation_progressive(self):
        points = self.BON["points"]
        reduites = [
            {"points": points, "presentation": "points"},
            {"points": points, "vecteur": {"nom": "AB"}, "presentation": "vecteur"},
        ]
        for forme in reduites:
            self.assertEqual(valider(forme), forme)
        # et seulement elles : la présentation « composantes » exige les coordonnées, jamais de forme réduite
        refusees = [
            {"points": points, "presentation": "composantes"},
            {"points": points, "vecteur": {"nom": "AB"}, "presentation": "composantes"},
            {"points": points, "vecteur": {"nom": "BA"}, "presentation": "vecteur"},
            {"points": points, "vecteur": {"nom": "AB", "x": 3}, "presentation": "vecteur"},
            {"points": points, "vecteur": {"nom": "AB", "x": 3, "y": 2}, "presentation": "vecteur"},  # incohérent avec B − A
            {"points": points, "vecteur": None, "presentation": "points"},
            {"points": points, "vecteur": {}, "presentation": "points"},
            {"points": points, "presentation": "vecteur"},
            {"points": points, "vecteur": {"nom": "AB"}, "presentation": "points"},
            {"points": points, "vecteur": {"nom": "AB"}, "presentation": "points", "extra": 1},
            {"vecteur": {"nom": "AB"}, "presentation": "vecteur"},
        ]
        for forme in refusees:
            with self.assertRaises(ParametresInvalides, msg=repr(forme)):
                valider(forme)

    def test_projection_pour_le_professeur_retire_les_reponses(self):
        from .simulations.vecteur_deux_points import projeter
        complet = lambda pres: {**self.BON, "presentation": pres}  # noqa: E731
        self.assertEqual(projeter(complet("points")), {"points": self.BON["points"], "presentation": "points"})
        self.assertEqual(projeter(complet("vecteur")), {"points": self.BON["points"], "vecteur": {"nom": "AB"}, "presentation": "vecteur"})
        self.assertEqual(projeter(complet("composantes")), complet("composantes"))
        with self.assertRaises(ParametresInvalides):
            projeter({**self.BON, "presentation": "autre"})

    def test_catalogue_documente_chaque_modele(self):
        self.assertIn("vecteur_deux_points", CATALOGUE)
        for modele in CATALOGUE.values():
            self.assertTrue(modele.matieres and modele.notions and modele.parametres and modele.conditions)


class ReglagesTests(SimpleTestCase):
    def test_reglages(self):
        with override_settings(SIMULATIONS_ACTIVES=False, DEBUG=True):
            self.assertFalse(simulations_activees())
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=False):
            self.assertFalse(simulations_activees())  # production : jamais
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
            self.assertTrue(simulations_activees())

    def test_selection_ne_modifie_pas_la_correction_d_origine_et_survit_aux_erreurs(self):
        correction = {"questions": [{"numero": "2", "resultat": ""}], "statut": "x"}
        analyse = _analyse(ENONCE, QUESTIONS)
        with override_settings(SIMULATIONS_ACTIVES=True, DEBUG=True):
            sortie = avec_simulations(correction, analyse, "Mathématiques")
            self.assertEqual(len(sortie["questions"][0]["simulations"]), 1)
            self.assertNotIn("simulations", correction["questions"][0])
            with mock.patch("programme.simulations.selection.simulations_pour_question", side_effect=RuntimeError("boum")):
                self.assertIs(avec_simulations(correction, analyse, "Mathématiques"), correction)


@override_settings(
    CACHES=CACHE_TEST, DEBUG=True, IA_CORRECTION_ACTIVE=True, IA_CORRECTION_DEV_SEULEMENT=True,
    SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice",
)
class CorrectionAvecSimulationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=tle, nom="C")
        cls.maths = Programme.objects.create(matiere=Matiere.objects.create(nom="Mathématiques"), niveau=tle, serie=serie)
        cls.eleve = User.objects.create_user(
            "+22790000031", password="Motdepasse-2026", prenom="E", nom="L",
            role=User.Role.ELEVE, statut=User.Statut.ACTIF, niveau=tle, serie=serie,
        )

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)

    def demander(self, analyse=ANALYSE_VECTEUR, ia=None):
        corps = {"programme": self.maths.id, "analyse": copy.deepcopy(analyse)}
        p_ia, p_wolf = _fichier(copy.deepcopy(ia or _correction_vecteur()), None)
        with p_ia, p_wolf:
            return self.client.post(URL, corps, format="json")

    def test_exercice_vectoriel_complet(self):
        reponse = self.demander()
        self.assertEqual(reponse.status_code, 200, reponse.content)
        questions = reponse.json()["correction"]["questions"]
        self.assertEqual([len(q["simulations"]) for q in questions], [1, 1, 1])
        self.assertEqual([q["simulations"][0]["parametres"]["presentation"] for q in questions], ["points", "vecteur", "composantes"])
        for q in questions:  # mêmes coordonnées validées par Django pour les trois questions
            self.assertEqual(q["simulations"][0]["parametres"]["points"], [{"nom": "A", "x": 1, "y": 2}, {"nom": "B", "x": 4, "y": 3}])
        q3 = questions[2]
        self.assertEqual(q3["resultat"], "$\\overrightarrow{AB}(3 ; 1)$")  # la correction obtient (3 ; 1)
        s = q3["simulations"][0]
        self.assertEqual(s["parametres"]["vecteur"], {"nom": "AB", "x": 3, "y": 1})
        self.assertEqual(s["verification"]["concordance_correction"], "confirmee")
        self.assertIsNone(q3["etude_fonction"])  # etude_fonction conservé (absent ici)
        # aucune commande GeoGebra n'est publiée : uniquement des données
        self.assertFalse(re.search(r"evalCommand|Vector\(|Segment\(", json.dumps(s)))

    def test_correction_contradictoire_pas_de_simulation_sur_la_question_3(self):
        reponse = self.demander(ia=_correction_vecteur("$\\overrightarrow{AB}(5 ; 1)$"))
        self.assertEqual(reponse.status_code, 200)
        q = reponse.json()["correction"]["questions"]
        self.assertEqual(len(q[0]["simulations"]), 1)
        self.assertEqual(len(q[1]["simulations"]), 1)
        self.assertEqual(q[2]["simulations"], [])

    def test_exercice_existant_inchange_et_etude_fonction_conservee(self):
        reponse = self.demander(analyse=ANALYSE_EX1, ia=CORRECTION_EX1)
        self.assertEqual(reponse.status_code, 200, reponse.content)
        c = reponse.json()["correction"]
        self.assertEqual(c["statut"], "calculs_verifies")
        self.assertEqual(c["questions"][0]["simulations"], [])
        self.assertIn("etude_fonction", c["questions"][0])

    def test_simulations_absentes_en_production_et_si_desactivees(self):
        for reglages in ({"DEBUG": False, "IA_CORRECTION_DEV_SEULEMENT": False}, {"SIMULATIONS_ACTIVES": False}):
            cache.clear()
            with override_settings(**reglages):
                reponse = self.demander()
            self.assertEqual(reponse.status_code, 200, reponse.content)
            c = reponse.json()["correction"]
            self.assertTrue(all("simulations" not in q for q in c["questions"]), reglages)
            self.assertEqual(c["questions"][2]["resultat"], "$\\overrightarrow{AB}(3 ; 1)$")  # correction normale

    def test_le_cache_ne_garde_pas_les_simulations(self):
        self.demander()
        with override_settings(SIMULATIONS_ACTIVES=False):
            reponse = self.demander()
        self.assertTrue(reponse.json()["correction_depuis_cache"])
        self.assertTrue(all("simulations" not in q for q in reponse.json()["correction"]["questions"]))
