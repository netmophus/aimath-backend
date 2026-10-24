"""
Étape 9.4 : les simulations des nombres complexes, des suites et de la géométrie du triangle dans le Professeur
particulier, avec la divulgation progressive et la divulgation conditionnée à la PREUVE de l'étape 9.2.2.

On vérifie les corps JSON BRUTS renvoyés par l'API (pas seulement ce que l'interface afficherait) : ce qui ne doit pas être
vu n'est pas transmis, même caché dans un attribut ou un paramètre. Aucun appel IA ni réseau réel : plan et retours
scriptés (FauxProfesseur), Wolfram simulé ; l'IA simulée accepte TOUTE réponse « plausible » (le pire cas).
"""

import copy
import json
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from comptes.models import User

from .correction import wolfram
from .models import Cycle, Matiere, Niveau, Programme, Serie
from .professeur import ia, seance as module_seance
from .professeur.visualisation import preparer, publiques
from .simulations.catalogue import CATALOGUE
from .simulations.geometrie_triangle import controler as controler_triangle
from .simulations.plan_complexe import controler as controler_complexe
from .simulations.suite_recurrente import controler as controler_suite
from .test_correction_exercice import _analyse
from .test_professeur import BASE, CACHE_TEST, FauxProfesseur, _etape, _retour, _wolfram
from .test_professeur_simulations import _indices, _subst
from .test_simulations_93 import COMPLEXE, SUITE, TRIANGLE, _une

BS = chr(92)


def _plan(*etapes):
    return {"questions": [
        {"numero": str(i + 1), "enonce": consigne, "objectif": "Avancer pas à pas.", "etapes": [
            _etape(consigne, _indices(), "Voir la méthode du cours.", "Bravo, cette étape est réussie !", affirmation)]}
        for i, (consigne, affirmation) in enumerate(etapes)
    ]}


PLAN_COMPLEXE = _plan(
    ("Quelles sont les coordonnées du point M, image de z dans le plan complexe ?", None),
    ("Comment calcule-t-on le module de z avec sa partie réelle et sa partie imaginaire ?", None),
    ("Que devient la partie imaginaire pour le conjugué de z ?", None),
)
PLAN_SUITE = _plan(
    ("Calcule u1 et u2 à partir de u0 avec la relation de récurrence de la suite.", None),
    ("Que peut-on dire du comportement de la suite, se rapproche-t-elle d'une limite ?", None),
    ("Combien vaut x + 2 pour x = 1 quand on représente les premiers termes de la suite ?", _subst("x+2", "1", "3")),
)
PLAN_TRIANGLE = _plan(
    ("Place les points A, B et C dans le repère orthonormé.", None),
    ("Construis le triangle ABC en reliant les points A, B et C.", None),
    ("Calcule les longueurs des côtés du triangle ABC avec la formule de la distance.", None),
    ("Quelle est la nature du triangle ABC d'après ses longueurs ?", None),
)

# Pour chaque exercice : analyse, plan, réponses plausibles mais NON vérifiables (acceptées par l'IA simulée), réponses
# prouvées (contrôle indépendant ou SymPy), réponses fausses, présentation de chaque question, questions révélatrices et
# ce qui ne doit JAMAIS voyager avant que la simulation de la question concernée soit légitimement dévoilée.
CONFIG = {
    "complexe": {
        "analyse": _analyse(*COMPLEXE), "plan": PLAN_COMPLEXE, "modele": "plan_complexe",
        "plausibles": ["Le point M a pour abscisse la partie réelle de z et pour ordonnée sa partie imaginaire.",
                       "On prend la racine carrée de la somme des carrés des deux parties.",
                       "Le conjugué garde la même partie réelle mais change le signe de l'autre partie."],
        "prouvees": [None, "|z| = " + chr(8730) + "(3² + 2²) = " + chr(8730) + "13", "z̄ = 3 - 2i"],
        "fausses": {2: ["|z| = " + chr(8730) + "5"], 3: ["z̄ = 3 + 5i", "M'(3 ; 5)"]},
        "presentations": ["point", "module", "conjugue"],
        "revelatrices": {2, 3},
        "fausse_q1": "M(2 ; 3)",
        "secrets": {2: ['"module"', '"coef"', '"rad"'], 3: ['"conjugue"']},
    },
    "suite": {
        "analyse": _analyse(*SUITE), "plan": PLAN_SUITE, "modele": "suite_recurrente",
        "plausibles": ["On remplace n par 0 puis par 1 dans la relation de récurrence.",
                       "Les termes semblent se rapprocher d'une valeur, ce qui suggère une limite.",
                       None],  # question 3 : étape vérifiable par SymPy, une réponse seulement « plausible » n'y est pas acceptée
        "prouvees": ["u_1 = 11/2 et u_2 = 23/4", "La suite converge vers 6.", "3"],  # Q3 : SymPy (étape vérifiable)
        "fausses": {1: ["u_1 = 8 et u_2 = 23/4", "u₁ = 5,6"], 2: ["La suite converge vers 7.", "lim u_n = 5"]},
        "presentations": ["termes", "escalier", "termes"],
        "revelatrices": {1, 2, 3},
        "verifiees": {3},
        "fausse_q1": "u_1 = 8",
        "secrets": {2: ['"limite"', '"escalier"']},
    },
    "triangle": {
        "analyse": _analyse(*TRIANGLE), "plan": PLAN_TRIANGLE, "modele": "geometrie_triangle",
        "plausibles": ["Chaque point est repéré grâce à son abscisse et à son ordonnée.",
                       "Je relie les trois points par des segments.",
                       "On applique la racine de la somme des carrés des différences de coordonnées.",
                       "On compare le carré du plus grand côté avec la somme des deux autres carrés."],
        "prouvees": [None, None, "AB = 4, AC = 3 et BC = 5", "Le triangle ABC est rectangle en A"],
        "fausses": {3: ["AB = 5, AC = 3 et BC = 4", "BC = " + chr(8730) + "7"], 4: ["Le triangle ABC est isocèle", "Le triangle ABC est rectangle en B"]},
        "presentations": ["points", "triangle", "distances", "nature"],
        "revelatrices": {3, 4},
        "fausse_q1": "C(1 ; 3)",
        "secrets": {3: ['"longueurs"', '"demandes"', '"coef"', '"rad"'], 4: ['"nature"', '"sommet_droit"']},
    },
}


class _Mixin:
    CLE = ""
    DEMARRER = True

    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=tle, nom="C")
        cls.maths = Programme.objects.create(matiere=Matiere.objects.create(nom="Mathématiques"), niveau=tle, serie=serie)
        cls.eleve = User.objects.create_user("+22790000071", password="Motdepasse-2026", prenom="E", nom="L", role=User.Role.ELEVE,
                                             statut=User.Statut.ACTIF, niveau=tle, serie=serie)
        cls.autre = User.objects.create_user("+22790000072", password="Motdepasse-2026", prenom="E", nom="L", role=User.Role.ELEVE,
                                             statut=User.Statut.ACTIF, niveau=tle, serie=serie)

    def setUp(self):
        cache.clear()
        self.cfg = CONFIG[self.CLE]
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)
        self.prof = FauxProfesseur(plan_brut=copy.deepcopy(self.cfg["plan"]))
        self.prof.defaut = _retour("Cela me semble pertinent.", "aucune", "", "plausible")  # IA SIMULÉE : accepte tout
        for cible, nom, remplacement in ((ia, "appeler_outil", self.prof), (wolfram, "_requete_http", _wolfram)):
            patcher = mock.patch.object(cible, nom, side_effect=remplacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        for cible in ("programme.lecture_exercice._envoyer_a_anthropic", "programme.correction.resolution._appeler_anthropic"):
            patcher = mock.patch(cible, side_effect=AssertionError("appel IA inattendu"))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.bruts = []
        r = self.client.post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(self.cfg["analyse"])}, format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        self.noter(r)

    # --- utilitaires -----------------------------------------------------------------------------

    def noter(self, r):
        """Mémorise le corps brut et vérifie, À CHAQUE RÉPONSE, qu'aucun secret n'a voyagé avant son déblocage."""
        corps = r.content.decode()
        self.bruts.append(corps)
        if r.status_code in (200, 201):
            self.etat = r.json()["seance"]
            self.verifier_corps(corps, self.etat["simulations"])
        return r

    def verifier_corps(self, corps, simulations):
        compact = corps.replace(" ", "")
        devoilees = {int(s["question"]) for s in simulations}
        for question, secrets in self.cfg["secrets"].items():
            if question not in devoilees:
                for secret in secrets:
                    self.assertNotIn(secret, compact, f"« {secret} » transmis avant le déblocage de la question {question}")
        for secret in ('"preuve"', '"cles"', '"irrecevables"', '"attendu"', '"affirmation"', "simulations_completes"):
            self.assertNotIn(secret, compact, secret)

    def agir(self, action, corps=None, version=None):
        donnees = {"version": self.etat["version"] if version is None else version, **(corps or {})}
        return self.noter(self.client.post(f"{BASE}{self.etat['seance']}/{action}/", donnees, format="json"))

    def repondre(self, texte):
        return self.agir("reponse", {"texte": texte})

    def suivante(self):
        self.assertEqual(self.agir("suivante").status_code, 200)

    def statut(self):
        etat = cache.get(module_seance._cle(self.etat["seance"]))
        return etat["etapes"][f"{etat['q']}-0"]

    def questions_devoilees(self):
        return [int(s["question"]) for s in self.etat["simulations"]]

    def presentations(self):
        return [s["simulation"]["parametres"]["presentation"] for s in self.etat["simulations"]]

    def numero(self):
        return self.etat["progression"]["question"]

    def plausible(self):
        texte = self.cfg["plausibles"][self.numero() - 1]
        if texte is None:  # étape vérifiable par SymPy : une réponse « plausible » n'y est pas acceptée, on la prouve
            return self.prouver()
        self.assertEqual(self.repondre(texte).status_code, 200)
        self.assertTrue(self.etat["etape_terminee"], self.etat["messages"][-1])

    def prouver(self):
        texte = self.cfg["prouvees"][self.numero() - 1]
        if texte is None:  # question non révélatrice : une réponse plausible suffit
            return self.plausible()
        self.assertEqual(self.repondre(texte).status_code, 200)
        self.assertTrue(self.etat["etape_terminee"], self.etat["messages"][-1])
        self.assertEqual(self.statut()["statut"], "reussie")

    def retenues(self):
        """Questions révélatrices dont la simulation reste retenue quand l'élève n'a donné que des réponses plausibles."""
        return self.cfg["revelatrices"] - self.cfg.get("verifiees", set())

    def aller_a_la_question(self, numero, preuve=True):
        while self.numero() < numero:
            (self.prouver if preuve else self.plausible)()
            self.suivante()

    # --- 1. début de séance et sélection automatique --------------------------------------------------

    def test_debut_de_seance_sans_divulgation(self):
        self.assertEqual(self.etat["simulations"], [])
        for corps in self.bruts:
            self.assertNotIn(self.cfg["modele"], corps)

    def test_selection_automatique_cote_serveur_et_modele_reconnu(self):
        etat = cache.get(module_seance._cle(self.etat["seance"]))
        complet = etat["simulations"]
        self.assertEqual(sorted(complet), [str(i) for i in range(len(self.cfg["presentations"]))])
        for rang, presentation in enumerate(self.cfg["presentations"]):
            (sim,) = complet[str(rang)]
            self.assertEqual((sim["modele"], sim["parametres"]["presentation"]), (self.cfg["modele"], presentation))
        for corps in self.bruts:
            self.assertNotIn("simulations_completes", corps)

    # --- 2. progression avec preuves -----------------------------------------------------------------

    def test_la_progression_dévoile_les_simulations_une_a_une_apres_preuve(self):
        for question in range(1, len(self.cfg["presentations"]) + 1):
            self.assertEqual(self.numero(), question)
            self.assertNotIn(question, self.questions_devoilees())  # question en cours : pas de simulation
            self.prouver()
            self.assertEqual(self.questions_devoilees(), list(range(1, question + 1)))
            self.assertEqual(self.presentations(), self.cfg["presentations"][:question])
            self.suivante()
        self.assertTrue(self.etat["termine"])
        self.assertEqual(self.presentations(), self.cfg["presentations"])  # l'élève peut tout revoir sans recommencer

    def test_les_simulations_deja_debloquees_restent_consultables_apres_reprise(self):
        self.aller_a_la_question(2)
        r = self.client.post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(self.cfg["analyse"])}, format="json")
        self.noter(r)
        self.assertEqual(self.etat["progression"]["question"], 2)
        self.assertEqual(self.questions_devoilees(), [1])

    # --- 3. réponse plausible mais non vérifiée ---------------------------------------------------------

    def test_une_reponse_plausible_non_verifiee_ne_devoile_que_les_questions_non_revelatrices(self):
        for _ in self.cfg["presentations"]:
            self.plausible()
            attendues = [q for q in range(1, self.numero() + 1) if q not in self.retenues()]
            self.assertEqual(self.questions_devoilees(), attendues)
            if self.numero() in self.retenues():
                self.assertEqual(self.statut()["statut"], "reussie_non_verifiee")
                self.assertIn("ne s'ouvrira que lorsque ce résultat aura été vérifié", self.etat["messages"][-1]["texte"])
            self.suivante()
        self.assertTrue(self.etat["termine"])
        self.assertEqual(self.questions_devoilees(), [q for q in range(1, len(self.cfg["presentations"]) + 1) if q not in self.retenues()])

    # --- 4. réponse incorrecte --------------------------------------------------------------------------

    def test_une_reponse_contredite_par_le_controle_independant_ne_devoile_rien(self):
        for question, textes in self.cfg["fausses"].items():
            self.aller_a_la_question(question)
            for texte in textes:
                appels = self.prof.nb_tours
                avant = self.questions_devoilees()
                self.repondre(texte)
                self.assertFalse(self.etat["etape_terminee"], texte)  # l'avis de l'IA simulée est ignoré
                self.assertEqual(self.statut()["statut"], "en_cours", texte)
                self.assertEqual(self.prof.nb_tours, appels, texte)  # aucun appel IA : message neutre, sans fuite
                self.assertEqual(self.questions_devoilees(), avant)
                self.assertNotIn(question, self.questions_devoilees())

    # --- 5. indices progressifs -------------------------------------------------------------------------

    def test_les_indices_ne_devoilent_aucune_simulation(self):
        question = min(self.retenues())
        self.aller_a_la_question(question)
        avant = self.questions_devoilees()
        for _ in range(3):
            self.assertEqual(self.agir("indice").status_code, 200)
            self.assertEqual(self.questions_devoilees(), avant)
        self.assertEqual(self.agir("explication", {"type": "exemple"}).status_code, 200)
        self.assertEqual(self.questions_devoilees(), avant)
        self.assertFalse(self.etat["etape_terminee"])

    # --- 6. solution légitimement débloquée --------------------------------------------------------------

    def test_solution_refusee_tant_qu_elle_n_est_pas_debloquee(self):
        self.assertEqual(self.agir("solution").status_code, 400)
        self.assertEqual(self.etat["simulations"], [])

    def test_solution_legitimement_debloquee_autorise_la_simulation_revelatrice(self):
        question = min(self.retenues())
        self.aller_a_la_question(question)
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        self.repondre("Je ne suis pas sûr de la méthode à appliquer ici")
        self.agir("indice")
        self.repondre("Je cherche une autre méthode pour répondre")
        self.assertFalse(self.etat["actions"]["solution"])  # un seul indice
        self.agir("indice")
        self.assertTrue(self.etat["actions"]["solution"])
        self.assertNotIn(question, self.questions_devoilees())  # débloquer n'est pas consulter
        self.assertEqual(self.agir("solution").status_code, 200)
        self.assertEqual(self.statut()["preuve"], "solution")
        self.assertIn(question, self.questions_devoilees())

    # --- 7. requêtes forgées ------------------------------------------------------------------------------

    def test_un_client_ne_peut_pas_reclamer_ni_forcer_une_simulation(self):
        forcage = {"simulation": self.cfg["presentations"][-1], "presentation": self.cfg["presentations"][-1], "question": 3,
                   "debloquer": True, "modele": self.cfg["modele"], "simulations": [{"question": "2"}], "etape_terminee": True, "q": 2,
                   "preuve": "controle", "statut": "reussie"}
        r = self.client.post(f"{BASE}{self.etat['seance']}/reponse/", {"version": self.etat["version"], "texte": self.cfg["fausse_q1"], **forcage}, format="json")
        self.noter(r)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.noter(self.client.post(f"{BASE}{self.etat['seance']}/indice/", {"version": self.etat["version"], **forcage}, format="json")).status_code, 200)
        self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.noter(self.client.post(f"{BASE}{self.etat['seance']}/suivante/", {"version": self.etat["version"], **forcage}, format="json")).status_code, 400)
        for chemin in ("simulations/", "simulation/", "visualisation/", "geogebra/"):
            for methode in (self.client.get, self.client.post):
                self.assertEqual(methode(f"{BASE}{self.etat['seance']}/{chemin}").status_code, 404, chemin)
        r = self.client.get(f"{BASE}{self.etat['seance']}/?question=3&simulation=1&debloquer=1")
        self.assertEqual(r.json()["seance"]["simulations"], [])

    def test_version_perimee_et_autre_eleve(self):
        self.aller_a_la_question(2)
        ancienne = self.etat["version"] - 1
        r = self.agir("indice", version=ancienne)
        self.assertEqual(r.status_code, 409)
        for s in r.json().get("seance", {}).get("simulations", []):
            self.assertIn(int(s["question"]), self.questions_devoilees())  # même filtrage que l'état courant
        autre = APIClient()
        autre.force_authenticate(self.autre)
        for r in (autre.get(f"{BASE}{self.etat['seance']}/"), autre.post(f"{BASE}{self.etat['seance']}/indice/", {"version": 5}, format="json")):
            self.assertEqual(r.status_code, 404)
            self.assertNotIn(self.cfg["modele"], r.content.decode())
        self.assertEqual(APIClient().get(f"{BASE}{self.etat['seance']}/").status_code, 401)

    # --- 8. réglages -----------------------------------------------------------------------------------------

    def test_aucune_simulation_si_desactivees_ou_en_production(self):
        for reglages in ({"SIMULATIONS_ACTIVES": False}, {"DEBUG": False, "IA_PROF_DEV_SEULEMENT": False}):
            cache.clear()
            with override_settings(**reglages):
                r = self.client.post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(self.cfg["analyse"])}, format="json")
                self.noter(r)
                for _ in self.cfg["presentations"]:
                    self.plausible() if self.cfg["plausibles"][self.numero() - 1] else self.repondre("3")
                    self.assertEqual(self.etat["simulations"], [], reglages)
                    self.suivante()
                self.assertTrue(self.etat["termine"])
                self.assertNotIn(self.cfg["modele"], self.reponse_brute())

    def reponse_brute(self):
        return self.bruts[-1]

    def test_la_presence_des_simulations_ne_change_ni_les_verdicts_ni_la_progression(self):
        def parcours():
            cache.clear()
            self.noter(self.client.post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(self.cfg["analyse"])}, format="json"))
            vues = []
            for _ in self.cfg["presentations"]:
                self.plausible()
                vues.append(self.etat)
                self.suivante()
            # les messages peuvent différer par la note « la figure s'ouvrira… » : on compare leur nature, pas leur texte
            return [{**{k: v for k, v in e.items() if k not in ("simulations", "seance", "expire_a", "version", "messages")},
                     "messages": [(m["role"], m["type"], m["verification"]) for m in e["messages"]]} for e in vues]

        avec = parcours()
        with override_settings(SIMULATIONS_ACTIVES=False):
            sans = parcours()
        self.assertEqual(avec, sans)


_REGLAGES = dict(
    CACHES=CACHE_TEST, DEBUG=True, IA_PROF_ACTIVE=True, IA_PROF_DEV_SEULEMENT=True,
    SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice", IA_PROF_SEANCE_SECONDES=600,
)


@override_settings(**_REGLAGES)
class ProfesseurComplexeTests(_Mixin, TestCase):
    CLE = "complexe"


@override_settings(**_REGLAGES)
class ProfesseurSuiteTests(_Mixin, TestCase):
    CLE = "suite"

    def test_la_question_de_calcul_ne_recoit_que_les_termes_demandes_sans_limite(self):
        self.prouver()  # question 1 : u₁ et u₂ confirmés par le contrôle indépendant
        (sim,) = self.etat["simulations"]
        self.assertEqual(sim["simulation"]["parametres"], {
            "nom": "u", "n0": 0, "a": "1/2", "b": "3", "termes": ["5", "11/2", "23/4"], "demande": 2, "presentation": "termes",
        })

    def test_etape_verifiee_par_sympy_devoile_la_question_3(self):
        self.aller_a_la_question(3)
        self.assertEqual(self.repondre("3").status_code, 200)
        self.assertEqual(self.statut()["preuve"], "calcul")  # vérifiée de manière indépendante (SymPy)
        self.assertEqual(self.questions_devoilees(), [1, 2, 3])
        q3 = self.etat["simulations"][2]["simulation"]["parametres"]
        self.assertEqual((q3["presentation"], len(q3["termes"])), ("termes", 10))
        self.assertNotIn("limite", q3)  # la limite est la réponse de la question 2 : jamais dans une présentation « termes »
        self.assertNotIn("limite", self.etat["simulations"][0]["simulation"]["parametres"])
        self.assertEqual(self.etat["simulations"][1]["simulation"]["parametres"]["limite"], "6")  # question 2 prouvée : l'escalier la montre


@override_settings(**_REGLAGES)
class ProfesseurTriangleTests(_Mixin, TestCase):
    CLE = "triangle"

    def test_la_question_de_construction_ne_montre_ni_longueur_ni_nature(self):
        self.aller_a_la_question(2)
        self.prouver()
        parametres = self.etat["simulations"][1]["simulation"]["parametres"]
        self.assertEqual(sorted(parametres), ["points", "presentation"])
        self.assertEqual(parametres["presentation"], "triangle")

    def test_la_nature_ne_porte_pas_les_longueurs(self):
        self.aller_a_la_question(4)
        self.prouver()
        parametres = self.etat["simulations"][3]["simulation"]["parametres"]
        self.assertEqual(sorted(parametres), ["nature", "points", "presentation"])
        self.assertEqual(parametres["nature"], {"type": "rectangle", "sommet_droit": "A"})

    def test_les_longueurs_ne_devoilent_pas_la_nature(self):
        self.aller_a_la_question(3)
        self.prouver()
        parametres = self.etat["simulations"][2]["simulation"]["parametres"]
        self.assertEqual(parametres["presentation"], "distances")
        self.assertNotIn("nature", parametres)
        self.assertNotIn("sommet_droit", json.dumps(self.etat))


class ClassementEtControleTests(SimpleTestCase):
    """Garde-fous unitaires : classement révélateur / non révélateur et contrôle déterministe de chaque modèle."""

    def test_classement_des_presentations(self):
        for cas, attendu in ((COMPLEXE, [False, True, True]), (SUITE, [True, True, True]), (TRIANGLE, [False, False, True, True])):
            with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
                sims = [_une(cas, n) for n, _ in cas[1]]
            self.assertEqual([CATALOGUE[s["modele"]].revelatrice(s["parametres"]) for s in sims], attendu)

    def test_preparer_propose_les_nouveaux_modeles_au_professeur(self):
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
            for cas, modele in ((COMPLEXE, "plan_complexe"), (SUITE, "suite_recurrente"), (TRIANGLE, "geometrie_triangle")):
                plan = [{"numero": n} for n, _ in cas[1]]
                complet = preparer(_analyse(*cas), "Mathématiques", plan)
                self.assertEqual(sorted(complet), [str(i) for i in range(len(plan))])
                self.assertTrue(all(s["modele"] == modele for sims in complet.values() for s in sims))

    def test_publiques_retient_une_simulation_revelatrice_sans_preuve(self):
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
            for cas, revelatrices in ((COMPLEXE, {1, 2}), (SUITE, {0, 1, 2}), (TRIANGLE, {2, 3})):
                simulations = {str(i): [_une(cas, n)] for i, (n, _) in enumerate(cas[1])}
                for statut, attendu in (("reussie_non_verifiee", set(range(len(simulations))) - revelatrices), ("reussie", set(range(len(simulations)))), ("solution_vue", set(range(len(simulations))))):
                    etat = {
                        "plan": [{"numero": n} for n, _ in cas[1]],
                        "etapes": {f"{i}-0": {"statut": statut} for i in range(len(simulations))},
                        "simulations": simulations,
                    }
                    self.assertEqual({int(p["question"]) - 1 for p in publiques(etat)}, attendu, (cas[0][:20], statut))

    def test_controle_plan_complexe(self):
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
            point, module, conjugue = (_une(COMPLEXE, n)["parametres"] for n in "123")
        racine = chr(8730)
        for texte in (f"|z| = {racine}13", f"|z| = {racine}(3² + 2²) = {racine}13", f"|z| = {BS}sqrt{{13}}", f"|z| = sqrt(13)", f"{racine}(13)"):
            self.assertEqual(controler_complexe(module, texte), "confirme", texte)
        for texte in (f"|z| = {racine}5", f"|z| = 2{racine}13", f"{racine}(3² + 2²) = {racine}12"):
            self.assertEqual(controler_complexe(module, texte), "contredit", texte)
        for texte in ("on calcule la somme des carrés", f"{racine}(3² + 2²)", "|z| vaut environ 3,6", ""):
            self.assertIsNone(controler_complexe(module, texte), texte)
        for texte in ("z̄ = 3 - 2i", "z = 3 + 2i donc z̄ = 3 − 2i", "le conjugué est 3-2i", "M'(3 ; -2)", f"{BS}bar{{z}} = 3 - 2i"):
            self.assertEqual(controler_complexe(conjugue, texte), "confirme", texte)
        for texte in ("z̄ = 3 + 5i", "z̄ = -3 - 2i", "M'(3 ; 5)", "z = 3 + 2i et z̄ = 2 - 2i"):
            self.assertEqual(controler_complexe(conjugue, texte), "contredit", texte)
        for texte in ("z = 3 + 2i", "on change le signe de la partie imaginaire"):
            self.assertIsNone(controler_complexe(conjugue, texte), texte)
        self.assertIsNone(controler_complexe(point, "M(3 ; 2)"))  # représenter z : jamais de confirmation
        self.assertEqual(controler_complexe(point, "M(2 ; 3)"), "contredit")
        self.assertIsNone(controler_complexe({"presentation": "module"}, f"{racine}13"))

    def test_controle_suite(self):
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
            termes, escalier = (_une(SUITE, n)["parametres"] for n in "12")
        for texte in ("u_1 = 11/2 et u_2 = 23/4", "u₁ = 5,5 ; u₂ = 5,75", f"u_1 = {BS}frac{{11}}{{2}}, u_2 = {BS}frac{{23}}{{4}}",
                      "u_1 = 1/2 × 5 + 3 = 11/2 puis u_2 = 1/2 × 11/2 + 3 = 23/4"):
            self.assertEqual(controler_suite(termes, texte), "confirme", texte)
        for texte in ("u_1 = 6 et u_2 = 23/4", "u₁ = 5,6", "u_2 = 5", "u_1 = 11/2 et u_2 = 7"):
            self.assertEqual(controler_suite(termes, texte), "contredit", texte)
        for texte in ("u_1 = 11/2", "u_2 = 23/4", "u_{n+1} = 1/2 u_n + 3", "u_1 − u_0 = 1/2 donc la suite croît", "je calcule les termes"):
            self.assertIsNone(controler_suite(termes, texte), texte)
        for texte in ("La suite converge vers 6.", "lim u_n = 6", "Elle tend vers 6", f"La limite est {BS}frac{{6}}{{1}}", "L = 6"):
            self.assertEqual(controler_suite(escalier, texte), "confirme", texte)
        for texte in ("La suite converge vers 7.", "lim u_n = 5", "Elle tend vers 11/2"):
            self.assertEqual(controler_suite(escalier, texte), "contredit", texte)
        for texte in ("La suite est croissante", "Elle diverge", "u_1 = 8"):
            self.assertIsNone(controler_suite(escalier, texte), texte)

    def test_controle_triangle(self):
        with override_settings(SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True, DEBUG=True):
            points, triangle, distances, nature = (_une(TRIANGLE, n)["parametres"] for n in "1234")
        racine = chr(8730)
        for texte in ("AB = 4, AC = 3 et BC = 5", "AB = 4 cm ; AC = 3 cm ; BC = 5 cm", f"BC = {racine}25 = 5, AB = {racine}16, AC = 3", "BA = 4, CA = 3, CB = 5"):
            self.assertEqual(controler_triangle(distances, texte), "confirme", texte)
        for texte in ("AB = 5, AC = 3 et BC = 4", "AB = 4, AC = 3 et BC = 6", f"BC = {racine}7", "AB = 4 et BC = 5 et AC = 2"):
            self.assertEqual(controler_triangle(distances, texte), "contredit", texte)
        for texte in ("AB = 4", "AB² = 16", "on utilise la formule de la distance"):
            self.assertIsNone(controler_triangle(distances, texte), texte)
        for texte in ("Le triangle ABC est rectangle en A", "ABC est rectangle en A car AB² + AC² = BC²", "Triangle rectangle en A"):
            self.assertEqual(controler_triangle(nature, texte), "confirme", texte)
        for texte in ("Le triangle ABC est isocèle", "Le triangle ABC est rectangle en B", "Le triangle est équilatéral", "rectangle isocèle en A", "Le triangle ABC est quelconque"):
            self.assertEqual(controler_triangle(nature, texte), "contredit", texte)
        for texte in ("Le triangle ABC n'est pas rectangle", "Il est rectangle", "AB = 4, AC = 3 et BC = 5", "je regarde les longueurs"):
            self.assertIsNone(controler_triangle(nature, texte), texte)
        for parametres in (points, triangle):
            self.assertIsNone(controler_triangle(parametres, "A(0 ; 0), B(4 ; 0) et C(0 ; 3)"))
            self.assertEqual(controler_triangle(parametres, "C(1 ; 3)"), "contredit")
            self.assertIsNone(controler_triangle(parametres, "AB = 4"))
        self.assertIsNone(controler_triangle({"presentation": "nature"}, "rectangle en A"))
