"""
Simulations GeoGebra dans le Professeur particulier (étape 9.2) : divulgation progressive contrôlée par le serveur.

On vérifie les DONNÉES RÉELLEMENT RENVOYÉES par l'API (corps JSON bruts), pas seulement ce que l'interface affiche.
Aucun appel IA ni réseau réel : plan et retours scriptés (FauxProfesseur), Wolfram simulé.
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
from .professeur import ia
from .professeur.visualisation import publiques
from .simulations.selection import projeter_pour_professeur
from .test_correction_exercice import _analyse
from .test_professeur import BASE, CACHE_TEST, FauxProfesseur, _etape, _wolfram
from .test_simulations import ENONCE, QUESTIONS

ANALYSE_VECTEUR = _analyse(ENONCE, QUESTIONS)
ANALYSE_AMBIGUE = _analyse("Dans un repère orthonormé, on considère les points A(1,5) et B(4 ; 3).", QUESTIONS)
ANALYSE_AUTRE = _analyse("Résoudre $x^2 - 5x + 6 = 0$.", [("1", "Résoudre l'équation."), ("2", "Vérifier les solutions."), ("3", "Conclure.")])


def _subst(expression, valeur, resultat):
    return {"type": "substitution", "description": f"{expression} pour x = {valeur}", "expression": expression, "variable": "x", "valeur": valeur, "resultat": resultat}


def _indices():
    return ["Réfléchis à la définition.", "Regarde la figure du repère.", "Compare les deux points."]


# Plan « vecteur » : trois questions, une étape vérifiable chacune (réponses attendues : 3, 3 et 1).
PLAN_VECTEUR = {"questions": [
    {"numero": "1", "enonce": "Placer les points A et B.", "objectif": "Lire les coordonnées des points.", "etapes": [
        _etape("Quelle est l'ordonnée du point B ?", _indices(), "L'ordonnée de B est celle donnée dans l'énoncé.", "Bravo, B est bien placé !", _subst("x+1", "2", "3"))]},
    {"numero": "2", "enonce": "Représenter le vecteur AB.", "objectif": "Tracer la flèche de A vers B.", "etapes": [
        _etape("De A vers B, de combien avance-t-on horizontalement ?", _indices(), "On avance de la différence des abscisses.", "Bravo, la flèche est bien orientée !", _subst("x+2", "1", "3"))]},
    {"numero": "3", "enonce": "Déterminer les coordonnées du vecteur AB.", "objectif": "Calculer les deux composantes.", "etapes": [
        _etape("Quelle est la composante verticale de AB ?", _indices(), "On soustrait les ordonnées.", "Bravo, les composantes sont trouvées !", _subst("x-1", "2", "1"))]},
]}


@override_settings(
    CACHES=CACHE_TEST, DEBUG=True, IA_PROF_ACTIVE=True, IA_PROF_DEV_SEULEMENT=True,
    SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice", IA_PROF_SEANCE_SECONDES=600,
)
class ProfesseurSimulationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=tle, nom="C")
        cls.maths = Programme.objects.create(matiere=Matiere.objects.create(nom="Mathématiques"), niveau=tle, serie=serie)
        cls.tle, cls.serie = tle, serie
        cls.eleve = cls._eleve("+22790000051")
        cls.autre = cls._eleve("+22790000052")

    @classmethod
    def _eleve(cls, tel):
        return User.objects.create_user(tel, password="Motdepasse-2026", prenom="E", nom="L", role=User.Role.ELEVE,
                                        statut=User.Statut.ACTIF, niveau=cls.tle, serie=cls.serie)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)
        self.prof = FauxProfesseur(plan_brut=PLAN_VECTEUR)
        for cible, nom, remplacement in ((ia, "appeler_outil", self.prof), (wolfram, "_requete_http", _wolfram)):
            patcher = mock.patch.object(cible, nom, side_effect=remplacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        for cible in ("programme.lecture_exercice._envoyer_a_anthropic", "programme.correction.resolution._appeler_anthropic"):
            patcher = mock.patch(cible, side_effect=AssertionError("appel IA inattendu"))
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- utilitaires ---------------------------------------------------------

    def demarrer(self, analyse=ANALYSE_VECTEUR, client=None):
        return (client or self.client).post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(analyse)}, format="json")

    def ouvrir(self, analyse=ANALYSE_VECTEUR):
        r = self.demarrer(analyse)
        self.assertIn(r.status_code, (200, 201), r.content)
        self.reponse = r
        self.etat = r.json()["seance"]
        return self.etat

    def agir(self, action, corps=None, client=None, version=None):
        donnees = {"version": self.etat["version"] if version is None else version, **(corps or {})}
        r = (client or self.client).post(f"{BASE}{self.etat['seance']}/{action}/", donnees, format="json")
        if r.status_code == 200:
            self.etat = r.json()["seance"]
            self.reponse = r
        return r

    def repondre(self, texte, **extra):
        return self.agir("reponse", {"texte": texte, **extra})

    def reussir_et_continuer(self, bonne):
        self.assertEqual(self.repondre(bonne).status_code, 200)
        self.assertTrue(self.etat["etape_terminee"], self.etat["messages"][-1])

    def suivante(self):
        self.assertEqual(self.agir("suivante").status_code, 200)

    def presentations(self):
        return [s["simulation"]["parametres"]["presentation"] for s in self.etat["simulations"]]

    # --- 1. Progression des trois questions ------------------------------------

    def test_la_progression_debloque_les_simulations_une_a_une(self):
        etat = self.ouvrir()
        self.assertEqual(etat["simulations"], [])  # Question 1 en cours : aucune simulation (elle donnerait la réponse)

        self.reussir_et_continuer("3")  # question 1 réussie
        self.assertEqual(self.presentations(), ["points"])
        self.assertEqual(self.etat["simulations"][0]["question"], "1")

        self.suivante()  # question 2 en cours : on conserve la simulation de la question 1, sans celle de la 2
        self.assertEqual(self.etat["progression"]["question"], 2)
        self.assertEqual(self.presentations(), ["points"])

        self.reussir_et_continuer("3")  # question 2 réussie
        self.assertEqual(self.presentations(), ["points", "vecteur"])

        self.suivante()  # question 3 en cours
        self.assertEqual(self.presentations(), ["points", "vecteur"])

        self.reussir_et_continuer("1")  # question 3 réussie
        self.assertEqual(self.presentations(), ["points", "vecteur", "composantes"])

        self.suivante()  # exercice terminé : l'élève peut tout revoir
        self.assertTrue(self.etat["termine"])
        self.assertEqual(self.presentations(), ["points", "vecteur", "composantes"])
        self.assertEqual([s["question"] for s in self.etat["simulations"]], ["1", "2", "3"])

    def test_la_version_publique_ne_contient_que_ce_qui_est_dévoilable(self):
        self.ouvrir()
        self.reussir_et_continuer("3")
        q1 = self.etat["simulations"][0]["simulation"]
        self.assertEqual(q1["parametres"], {"points": [{"nom": "A", "x": 1, "y": 2}, {"nom": "B", "x": 4, "y": 3}], "presentation": "points"})
        self.assertNotIn("vecteur", q1["parametres"])  # pas de coordonnées du vecteur avant la question 3

        self.suivante()
        self.reussir_et_continuer("3")
        q2 = self.etat["simulations"][1]["simulation"]
        self.assertEqual(q2["parametres"]["vecteur"], {"nom": "AB"})  # le nom seulement : aucune coordonnée
        self.assertEqual(q2["parametres"]["presentation"], "vecteur")

        self.suivante()
        self.reussir_et_continuer("1")
        q3 = self.etat["simulations"][2]["simulation"]
        self.assertEqual(q3["parametres"]["vecteur"], {"nom": "AB", "x": 3, "y": 1})  # dévoilé : la question 3 est terminée
        self.assertEqual(q3["parametres"]["presentation"], "composantes")

    # --- 2. Non-divulgation, vérifiée sur les corps JSON bruts ----------------

    def test_aucune_fuite_dans_les_corps_bruts_avant_la_question_3(self):
        interdits_avant_q3 = ('"composantes"', '"x": 3', '"x":3', '"y": 1', '"y":1', "Δx", "Δy", "vecteur_deux_points_secret")
        etapes = []
        self.ouvrir(); etapes.append(self.reponse)  # démarrage
        etapes.append(self.client.get(f"{BASE}{self.etat['seance']}/"))  # lecture directe
        etapes.append(self.demarrer())  # reprise de la séance
        self.assertEqual(self.repondre("5").status_code, 200); etapes.append(self.reponse)  # réponse incorrecte
        self.assertEqual(self.agir("indice").status_code, 200); etapes.append(self.reponse)  # indice
        self.reussir_et_continuer("3"); etapes.append(self.reponse)  # question 1 réussie
        self.suivante(); etapes.append(self.reponse)
        self.reussir_et_continuer("3"); etapes.append(self.reponse)  # question 2 réussie
        self.suivante(); etapes.append(self.reponse)
        for r in etapes:
            corps = r.content.decode()
            for interdit in interdits_avant_q3:
                self.assertNotIn(interdit, corps, interdit)
            for simulation in r.json()["seance"]["simulations"]:
                vecteur = simulation["simulation"]["parametres"].get("vecteur")
                self.assertTrue(vecteur is None or set(vecteur) == {"nom"}, vecteur)
        self.assertNotIn("simulations_completes", json.dumps(etapes[-1].json()))  # l'état serveur n'est jamais exposé

    def test_aucune_simulation_pendant_la_question_1_meme_apres_erreurs_et_indices(self):
        self.ouvrir()
        self.assertEqual(self.repondre("5").status_code, 200)  # réponse incorrecte
        self.assertEqual(self.etat["simulations"], [])
        for _ in range(3):  # indices progressifs
            self.assertEqual(self.agir("indice").status_code, 200)
            self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.agir("explication", {"type": "exemple"}).status_code, 200)
        self.assertEqual(self.etat["simulations"], [])
        self.assertFalse(self.etat["etape_terminee"])

    # --- 3. Déblocage légitime d'une solution ----------------------------------

    def test_solution_refusee_tant_qu_elle_n_est_pas_debloquee_donc_pas_de_simulation(self):
        self.ouvrir()
        r = self.agir("solution")
        self.assertEqual(r.status_code, 400)  # règles de la séance inchangées
        self.assertEqual(self.etat["simulations"], [])
        self.assertNotIn("vecteur", r.content.decode().lower().replace("vecteur_deux_points", ""))  # le refus ne contient pas de simulation

    def test_solution_legitimement_debloquee_autorise_la_simulation(self):
        self.ouvrir()
        self.assertEqual(self.repondre("5").status_code, 200)
        self.assertEqual(self.agir("indice").status_code, 200)
        self.assertEqual(self.repondre("6").status_code, 200)
        self.assertEqual(self.agir("indice").status_code, 200)
        self.assertTrue(self.etat["etape"]["solution_disponible"])
        self.assertEqual(self.etat["simulations"], [])  # débloquer la solution n'est pas la consulter
        self.assertEqual(self.agir("solution").status_code, 200)
        self.assertEqual(self.presentations(), ["points"])  # étape close par la solution : simulation « points » autorisée

    # --- 4. Refus d'accès non autorisé ---------------------------------------------

    def test_un_client_ne_peut_pas_reclamer_ni_forcer_une_simulation(self):
        self.ouvrir()
        forcage = {"simulation": "composantes", "presentation": "composantes", "question": 3, "debloquer": True, "modele": "vecteur_deux_points",
                   "simulations": [{"question": "3"}], "etape_terminee": True, "q": 2}
        self.assertEqual(self.repondre("5", **forcage).status_code, 200)
        self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.agir("indice", forcage).status_code, 200)
        self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.agir("explication", {"type": "exemple", **forcage}).status_code, 200)
        self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.agir("suivante", forcage).status_code, 400)  # étape non terminée : refus inchangé
        self.assertEqual(self.etat["simulations"], [])
        # aucune route dédiée aux simulations
        for chemin in ("simulations/", "simulation/", "visualisation/", "geogebra/"):
            for methode in (self.client.get, self.client.post):
                self.assertEqual(methode(f"{BASE}{self.etat['seance']}/{chemin}").status_code, 404, chemin)
        # paramètre de requête GET : sans effet
        r = self.client.get(f"{BASE}{self.etat['seance']}/?question=3&simulation=composantes&debloquer=1")
        self.assertEqual(r.json()["seance"]["simulations"], [])

    def test_version_perimee_ou_autre_eleve_ne_donnent_aucune_simulation(self):
        self.ouvrir()
        ancienne = self.etat["version"]
        self.reussir_et_continuer("3")  # débloque la simulation « points » pour CET élève
        # version périmée : refus, et le corps éventuel ne contient que l'état public (même filtrage)
        r = self.agir("indice", version=ancienne)
        self.assertEqual(r.status_code, 409)
        for s in r.json().get("seance", {}).get("simulations", []):
            self.assertNotIn("composantes", json.dumps(s))
        # un autre élève ne voit ni la séance ni ses simulations
        autre = APIClient()
        autre.force_authenticate(self.autre)
        for r in (autre.get(f"{BASE}{self.etat['seance']}/"), autre.post(f"{BASE}{self.etat['seance']}/indice/", {"version": 5}, format="json")):
            self.assertEqual(r.status_code, 404)
            self.assertNotIn("vecteur_deux_points", r.content.decode())
        # non authentifié
        self.assertEqual(APIClient().get(f"{BASE}{self.etat['seance']}/").status_code, 401)

    # --- 5. Réglages : développement local uniquement -----------------------------------

    def test_aucune_simulation_si_desactivees_ou_en_production(self):
        for reglages in ({"SIMULATIONS_ACTIVES": False}, {"DEBUG": False, "IA_PROF_DEV_SEULEMENT": False}):
            cache.clear()
            with override_settings(**reglages):
                self.ouvrir()
                for bonne, derniere in (("3", False), ("3", False), ("1", True)):
                    self.reussir_et_continuer(bonne)
                    self.assertEqual(self.etat["simulations"], [], reglages)
                    self.suivante()
                self.assertTrue(self.etat["termine"])
                self.assertEqual(self.etat["simulations"], [], reglages)
                self.assertNotIn("vecteur_deux_points", self.reponse.content.decode())

    def test_les_simulations_sont_recontrolees_a_chaque_envoi(self):
        self.ouvrir()
        self.reussir_et_continuer("3")
        self.assertEqual(self.presentations(), ["points"])
        with override_settings(SIMULATIONS_ACTIVES=False):
            r = self.client.get(f"{BASE}{self.etat['seance']}/")
            self.assertEqual(r.json()["seance"]["simulations"], [])  # le réglage coupé s'applique tout de suite
        with override_settings(DEBUG=True, SIMULATIONS_DEV_SEULEMENT=True):
            self.assertEqual(len(self.client.get(f"{BASE}{self.etat['seance']}/").json()["seance"]["simulations"]), 1)

    # --- 6. GeoGebra ne valide jamais une réponse ---------------------------------------

    def test_la_presence_des_simulations_ne_change_ni_les_verdicts_ni_la_progression(self):
        def parcours():
            cache.clear()
            self.ouvrir()
            vues = []
            for texte in ("5", "3"):  # incorrecte puis correcte
                self.repondre(texte)
                vues.append(self.etat)
            self.suivante()
            self.repondre("3")
            vues.append(self.etat)
            return [{k: v for k, v in e.items() if k not in ("simulations", "seance", "expire_a")} for e in vues]

        avec = parcours()
        with override_settings(SIMULATIONS_ACTIVES=False):
            sans = parcours()
        self.assertEqual(avec, sans)

    # --- 7. Énoncés sans simulation applicable ----------------------------------------------

    def test_enonce_ambigu_aucune_simulation_et_la_seance_fonctionne(self):
        self.ouvrir(ANALYSE_AMBIGUE)
        self.reussir_et_continuer("3")
        self.assertEqual(self.etat["simulations"], [])
        self.suivante()
        self.reussir_et_continuer("3")
        self.assertEqual(self.etat["simulations"], [])

    def test_autre_exercice_aucune_simulation(self):
        self.prof.plan_brut = copy.deepcopy(PLAN_VECTEUR)
        self.ouvrir(ANALYSE_AUTRE)
        self.reussir_et_continuer("3")
        self.assertEqual(self.etat["simulations"], [])

    def test_exercices_existants_gardent_la_cle_et_aucune_simulation(self):
        self.prof = FauxProfesseur()  # plan par défaut (f(x) = x³ − 3x)
        with mock.patch.object(ia, "appeler_outil", side_effect=self.prof):
            from .test_correction_exercice import _analyse as analyse
            from .test_correction_exercice import ANALYSE_EX2
            etat = self.ouvrir(ANALYSE_EX2)
        self.assertEqual(etat["simulations"], [])


class ProjectionPubliqueTests(SimpleTestCase):
    """Garde-fous unitaires : `publiques` ne dépend que de l'état serveur et refuse tout ce qui est invalide."""

    def _etat(self, statuts):
        return {
            "plan": [{"numero": str(i + 1)} for i in range(len(statuts))],
            "etapes": {f"{i}-0": {"statut": s} for i, s in enumerate(statuts)},
            "simulations": {},
        }

    def test_question_non_terminee_jamais_publiee(self):
        from .simulations.selection import simulations_pour_question
        sims = simulations_pour_question(ANALYSE_VECTEUR, "mathematiques", "Déterminer les coordonnées du vecteur AB.", "3", "")
        etat = self._etat(["reussie", "en_cours", "en_cours"])
        etat["simulations"] = {"2": sims}
        with override_settings(SIMULATIONS_ACTIVES=True, DEBUG=True):
            self.assertEqual(publiques(etat), [])
            etat["etapes"]["2-0"]["statut"] = "solution_vue"
            self.assertEqual(len(publiques(etat)), 1)

    def test_simulation_invalide_jamais_envoyee(self):
        mauvaises = [
            {"modele": "inconnu", "version": 2, "titre": "x", "parametres": {}},
            {"modele": "vecteur_deux_points", "version": 1, "titre": "x", "parametres": {}},
            {"modele": "vecteur_deux_points", "version": 2, "titre": "x", "parametres": {"points": [], "presentation": "points"}},
            None, "texte", 3,
        ]
        for m in mauvaises:
            self.assertIsNone(projeter_pour_professeur(m), m)
