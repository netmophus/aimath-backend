"""
Étape 9.2.2 : progression pédagogique sécurisée du Professeur particulier et divulgation conditionnée à la PREUVE.

Exercice de référence : A(1 ; 2), B(4 ; 3) — 1. Placer A et B ; 2. Représenter AB ; 3. Déterminer les coordonnées de AB.
Ici les étapes sont SANS calcul vérifiable par SymPy (questions graphiques / conceptuelles) : seul un avis d'IA SIMULÉ peut
les accepter. On vérifie sur les corps JSON bruts qu'un avis d'IA, même « plausible », ne suffit jamais à dévoiler un résultat.
Aucun appel IA ni réseau réel.
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
from .professeur import ia, recevabilite
from .simulations.vecteur_deux_points import controler as controler_vecteur
from .test_professeur import BASE, CACHE_TEST, FauxProfesseur, _retour, _wolfram
from .test_professeur_simulations import ANALYSE_VECTEUR, PLAN_VECTEUR


def _plan_sans_calcul():
    plan = copy.deepcopy(PLAN_VECTEUR)
    for question in plan["questions"]:
        for etape in question["etapes"]:
            etape["affirmation"] = None  # étape graphique / conceptuelle : rien à vérifier par SymPy
    return plan


def _plan_calcul_non_confirme():
    plan = copy.deepcopy(PLAN_VECTEUR)
    for question in plan["questions"]:
        for etape in question["etapes"]:  # affirmation FAUSSE : SymPy ne la confirme pas -> référence « contredite »/non vérifiée
            etape["affirmation"]["resultat"] = "99"
    return plan


PARAMETRES_COMPOSANTES = {
    "points": [{"nom": "A", "x": 1, "y": 2}, {"nom": "B", "x": 4, "y": 3}],
    "vecteur": {"nom": "AB", "x": 3, "y": 1},
    "presentation": "composantes",
}
PARAMETRES_POINTS = {"points": PARAMETRES_COMPOSANTES["points"], "presentation": "points"}
PARAMETRES_VECTEUR = {"points": PARAMETRES_COMPOSANTES["points"], "vecteur": {"nom": "AB"}, "presentation": "vecteur"}
BS = chr(92)


class ControleIndependantTests(SimpleTestCase):
    """Contrôle déterministe des coordonnées écrites par l'élève, recalculées depuis l'énoncé (jamais l'avis de l'IA)."""

    def test_composantes_confirme_les_ecritures_courantes(self):
        for texte in ("AB = (3 ; 1)", "AB(3;1)", "(3 ; 1)", "(3, 1)", "Les coordonnées sont (3 ; 1).", "x = 3 et y = 1", "Δx = 3, Δy = 1",
                      f"{BS}overrightarrow{{AB}}{BS}begin{{pmatrix}} 3 {BS}{BS} 1 {BS}end{{pmatrix}}", "A(1 ; 2), B(4 ; 3) donc AB(3 ; 1)"):
            self.assertEqual(controler_vecteur(PARAMETRES_COMPOSANTES, texte), "confirme", texte)

    def test_composantes_contredit_une_valeur_fausse(self):
        for texte in ("AB = (9 ; 9)", "(1 ; 3)", "(3 ; 2)", "Δx = 5", "x = 3 et y = 7", "AB(-3 ; -1)", "B(9 ; 9) donc AB(3 ; 1)"):
            self.assertEqual(controler_vecteur(PARAMETRES_COMPOSANTES, texte), "contredit", texte)

    def test_composantes_ne_confirme_pas_ce_qui_n_est_pas_un_resultat_complet(self):
        for texte in ("on soustrait les coordonnées", "Δx = 3", "x = 3", "le résultat vaut 3", "A(1 ; 2)", "M(7 ; 7)"):
            self.assertIsNone(controler_vecteur(PARAMETRES_COMPOSANTES, texte), texte)

    def test_points_et_vecteur_ne_confirment_jamais_mais_contredisent_l_enonce(self):
        for parametres in (PARAMETRES_POINTS, PARAMETRES_VECTEUR):
            self.assertIsNone(controler_vecteur(parametres, "A(1 ; 2) et B(4 ; 3)"))
            self.assertIsNone(controler_vecteur(parametres, "je place les deux points"))
            self.assertEqual(controler_vecteur(parametres, "B(9 ; 9)"), "contredit")
            self.assertEqual(controler_vecteur(parametres, "(7 ; 7)"), "contredit")

    def test_parametres_invalides_ou_illisibles_ne_controlent_rien(self):
        self.assertIsNone(controler_vecteur({"presentation": "composantes"}, "(3 ; 1)"))
        self.assertIsNone(controler_vecteur(PARAMETRES_COMPOSANTES, ""))


class RecevabiliteTests(SimpleTestCase):
    CONSIGNE = "De A vers B, de combien avance-t-on horizontalement ?"
    CONTEXTE = "Représenter le vecteur AB. Tracer la flèche de A vers B. " + CONSIGNE

    def motif(self, texte, deja=()):
        return recevabilite.evaluer(texte, self.CONSIGNE, self.CONTEXTE, list(deja))

    def test_reponses_courtes_mais_legitimes_sont_recevables(self):
        for texte in ("3", "-1", "(3 ; 1)", "AB", "A", "oui", "non", "Vrai", "x = 2", "3 et 1", "la flèche va de A vers B",
                      "on soustrait les abscisses", "Δx", "il avance de trois unités"):
            self.assertIsNone(self.motif(texte), texte)

    def test_reponses_irrecevables(self):
        cas = {"": recevabilite.VIDE, "   ": recevabilite.VIDE, "???": recevabilite.INUTILISABLE, "...!!": recevabilite.INUTILISABLE,
               "banane": recevabilite.HORS_SUJET, "n'importe quoi": recevabilite.HORS_SUJET, "azerty qsdfgh": recevabilite.HORS_SUJET,
               "je ne sais pas": recevabilite.NE_SAIT_PAS, "aucune idée": recevabilite.NE_SAIT_PAS,
               "De A vers B, de combien avance-t-on horizontalement": recevabilite.COPIE,
               "de combien avance-t-on horizontalement ?": recevabilite.COPIE}
        for texte, attendu in cas.items():
            self.assertEqual(self.motif(texte), attendu, texte)

    def test_repetition_meme_reformatee(self):
        deja = [recevabilite.cle("x = 3")]
        for texte in ("x = 3", "X=3", "x=  3 ", "$x = 3$"):
            self.assertEqual(self.motif(texte, deja), recevabilite.REPETITION, texte)
        self.assertIsNone(self.motif("x = 4", deja))

    def test_messages_d_aide(self):
        for motif in (recevabilite.VIDE, recevabilite.INUTILISABLE, recevabilite.COPIE, recevabilite.REPETITION,
                      recevabilite.HORS_SUJET, recevabilite.NE_SAIT_PAS):
            self.assertTrue(recevabilite.message(motif, 1))
        self.assertIn("indice", recevabilite.message(recevabilite.HORS_SUJET, 3))


@override_settings(
    CACHES=CACHE_TEST, DEBUG=True, IA_PROF_ACTIVE=True, IA_PROF_DEV_SEULEMENT=True,
    SIMULATIONS_ACTIVES=True, SIMULATIONS_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice", IA_PROF_SEANCE_SECONDES=600,
)
class ProgressionSecuriseeTests(TestCase):
    PLAN = staticmethod(_plan_sans_calcul)

    @classmethod
    def setUpTestData(cls):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=tle, nom="C")
        cls.maths = Programme.objects.create(matiere=Matiere.objects.create(nom="Mathématiques"), niveau=tle, serie=serie)
        cls.eleve = User.objects.create_user("+22790000061", password="Motdepasse-2026", prenom="E", nom="L", role=User.Role.ELEVE,
                                             statut=User.Statut.ACTIF, niveau=tle, serie=serie)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)
        self.prof = FauxProfesseur(plan_brut=self.PLAN())
        self.prof.defaut = _retour("Cela me semble pertinent.", "aucune", "", "plausible")  # IA SIMULÉE qui accepte tout
        for cible, nom, remplacement in ((ia, "appeler_outil", self.prof), (wolfram, "_requete_http", _wolfram)):
            patcher = mock.patch.object(cible, nom, side_effect=remplacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        for cible in ("programme.lecture_exercice._envoyer_a_anthropic", "programme.correction.resolution._appeler_anthropic"):
            patcher = mock.patch(cible, side_effect=AssertionError("appel IA inattendu"))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.bruts = []  # corps JSON bruts de chaque réponse reçue
        r = self.client.post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(ANALYSE_VECTEUR)}, format="json")
        self.assertIn(r.status_code, (200, 201), r.content)
        self.noter(r)

    def noter(self, r):
        self.bruts.append(r.content.decode())
        if r.status_code in (200, 201):
            self.etat = r.json()["seance"]
        return r

    def agir(self, action, corps=None, version=None):
        donnees = {"version": self.etat["version"] if version is None else version, **(corps or {})}
        return self.noter(self.client.post(f"{BASE}{self.etat['seance']}/{action}/", donnees, format="json"))

    def repondre(self, texte):
        return self.agir("reponse", {"texte": texte})

    def aller_a_la_question(self, numero):
        """Termine proprement les questions précédentes (réponses acceptées par l'avis d'IA simulé) puis avance."""
        reponses = {1: "Je lis les coordonnées de A et de B dans l'énoncé.", 2: "Je trace la flèche de A vers B."}
        while self.etat["progression"]["question"] < numero:
            self.assertEqual(self.repondre(reponses[self.etat["progression"]["question"]]).status_code, 200)
            self.assertTrue(self.etat["etape_terminee"])
            self.assertEqual(self.agir("suivante").status_code, 200)

    def statut(self, rang=None):
        # Lecture du cache de séance : l'état serveur est le seul endroit où vit le statut interne.
        from .professeur import seance as module
        etat = cache.get(module._cle(self.etat["seance"]))
        q = etat["q"] if rang is None else rang
        return etat["etapes"][f"{q}-0"]

    def presentations(self):
        return [s["simulation"]["parametres"]["presentation"] for s in self.etat["simulations"]]

    def corps_avant_resultat(self):
        return "\n".join(self.bruts)

    def assertAucuneFuite(self):
        corps = self.corps_avant_resultat()
        for interdit in ('"composantes"', '"x": 3', '"x":3', '"y": 1', '"y":1', "Δx", "Δy"):
            self.assertNotIn(interdit, corps, interdit)
        for secret in ('"preuve"', '"cles"', '"irrecevables"', '"attendu"', '"affirmation"'):
            self.assertNotIn(secret, corps, secret)

    # --- Réponse conceptuelle pertinente (catégorie C) -----------------------------------------

    def test_reponse_conceptuelle_pertinente_fait_progresser_sans_pretendre_qu_elle_est_verifiee(self):
        self.aller_a_la_question(2)
        r = self.repondre("La flèche part de A et se termine en B.")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.etat["etape_terminee"])
        self.assertEqual(self.statut()["statut"], "reussie_non_verifiee")
        self.assertEqual(self.etat["messages"][-1]["verification"], "non_verifiable")  # jamais affichée comme « vérifiée »
        # Simulations NON révélatrices (points de l'énoncé, tracé demandé) : envoyées, sans aucune coordonnée du vecteur.
        self.assertEqual(self.presentations(), ["points", "vecteur"])
        self.assertEqual(self.etat["simulations"][1]["simulation"]["parametres"]["vecteur"], {"nom": "AB"})
        self.assertAucuneFuite()

    # --- Réponse fausse jugée plausible (le cas du prompt) -------------------------------------

    def test_ab_9_9_jugee_plausible_par_l_ia_ne_devoile_rien(self):
        self.aller_a_la_question(3)
        appels = self.prof.nb_tours
        self.repondre("AB = (9 ; 9)")
        self.assertFalse(self.etat["etape_terminee"])  # contredite par le contrôle indépendant, l'avis de l'IA est ignoré
        self.assertEqual(self.statut()["statut"], "en_cours")
        self.assertEqual(self.prof.nb_tours, appels)  # aucun appel IA : message neutre, sans fuite possible
        self.assertEqual(self.presentations(), ["points", "vecteur"])  # pas de composantes
        self.assertAucuneFuite()
        self.assertNotIn("(3", self.etat["messages"][-1]["texte"])

    def test_resultat_faux_sans_coordonnees_juge_plausible_progresse_mais_ne_devoile_pas_les_composantes(self):
        self.aller_a_la_question(3)
        self.repondre("On additionne les coordonnées des deux points.")  # fausse méthode, jugée plausible par l'IA simulée
        self.assertTrue(self.etat["etape_terminee"])
        self.assertEqual(self.statut()["statut"], "reussie_non_verifiee")
        self.assertEqual(self.presentations(), ["points", "vecteur"])  # la simulation révélatrice reste retenue
        self.assertIn("ne s'ouvrira que lorsque ce résultat aura été vérifié", self.etat["messages"][-1]["texte"])
        self.assertEqual(self.agir("suivante").status_code, 200)
        self.assertTrue(self.etat["termine"])
        self.assertEqual(self.presentations(), ["points", "vecteur"])  # même à la fin de l'exercice
        self.assertAucuneFuite()

    # --- Contrôle déterministe indépendant confirmant la réponse -------------------------------

    def test_reponse_confirmee_par_le_controle_independant_devoile_les_composantes(self):
        self.aller_a_la_question(3)
        appels = self.prof.nb_tours
        self.repondre("AB(3 ; 1)")
        self.assertTrue(self.etat["etape_terminee"])
        self.assertEqual(self.statut()["statut"], "reussie")
        self.assertEqual(self.statut()["preuve"], "controle")
        self.assertEqual(self.prof.nb_tours, appels)  # aucun avis d'IA n'intervient
        self.assertEqual(self.presentations(), ["points", "vecteur", "composantes"])
        self.assertEqual(self.etat["simulations"][2]["simulation"]["parametres"]["vecteur"], {"nom": "AB", "x": 3, "y": 1})

    def test_ab_3_1_ecrit_avant_la_question_3_ne_devoile_rien_en_avance(self):
        self.aller_a_la_question(2)
        self.repondre("(3 ; 1)")  # coordonnée plausible mais hors de la question 2 : pas de confirmation (points/vecteur)
        self.assertNotIn('"composantes"', self.etat and json.dumps(self.etat["simulations"]))

    def test_coordonnee_contredisant_l_enonce_est_refusee_des_la_question_1(self):
        self.repondre("Le point B est en (9 ; 9).")
        self.assertFalse(self.etat["etape_terminee"])
        self.assertEqual(self.etat["simulations"], [])
        self.assertEqual(self.etat["etape"]["tentatives"], 1)  # tentative sérieuse mais fausse

    # --- Tentatives recevables ------------------------------------------------------------------

    def test_reponses_arbitraires_ou_repetees_ne_comptent_pas_et_ne_coutent_aucun_appel_ia(self):
        self.repondre("banane")
        self.repondre("n'importe quoi")
        self.repondre("???")
        self.repondre("je ne sais pas")
        self.repondre("Quelle est l'ordonnée du point B ?")  # copie de la consigne
        self.assertEqual(self.etat["etape"]["tentatives"], 0)
        self.assertEqual(self.prof.nb_tours, 0)
        self.assertFalse(self.etat["etape_terminee"])
        self.assertEqual(self.repondre("   ").status_code, 400)  # vide : refusée
        self.assertIn("indice", self.etat["messages"][-1]["texte"].lower())  # aide orientée, sans bloquer
        # Une réponse sérieuse compte une fois ; son doublon (même reformaté) ne compte pas.
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        self.repondre("B a pour ordonnée 5")
        self.repondre("b a pour ordonnée 5 ")
        self.assertEqual(self.etat["etape"]["tentatives"], 1)
        self.assertEqual(self.prof.nb_tours, 1)

    def test_reponses_courtes_mais_legitimes_comptent(self):
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        for texte in ("5", "AB", "oui"):
            self.repondre(texte)
        self.assertEqual(self.etat["etape"]["tentatives"], 3)

    # --- Déblocage de la solution ---------------------------------------------------------------

    def test_quatre_tentatives_sans_indice_ne_debloquent_plus_la_solution(self):
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        for essai in ("B a pour ordonnée 5", "B a pour ordonnée 6", "B a pour ordonnée 7", "B a pour ordonnée 8"):
            self.repondre(essai)
        self.assertEqual(self.etat["etape"]["tentatives"], 4)
        self.assertFalse(self.etat["actions"]["solution"])
        r = self.agir("solution")
        self.assertEqual(r.status_code, 400)
        self.assertIn("indice", r.json()["detail"])
        self.assertAucuneFuite()

    def test_indices_seuls_ou_une_seule_tentative_ne_suffisent_pas(self):
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        self.agir("indice"); self.agir("indice")
        self.assertEqual(self.agir("solution").status_code, 400)
        self.repondre("B a pour ordonnée 5")  # une seule tentative recevable
        self.assertEqual(self.agir("solution").status_code, 400)
        for _ in range(5):  # des envois irrecevables ne comptent pas
            self.repondre("banane")
        self.assertEqual(self.agir("solution").status_code, 400)

    def test_deux_tentatives_recevables_et_deux_indices_debloquent_la_solution(self):
        self.aller_a_la_question(3)
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        self.repondre("On additionne les coordonnées.")
        self.agir("indice")
        self.repondre("On multiplie les coordonnées.")
        self.assertFalse(self.etat["actions"]["solution"])  # un seul indice
        self.agir("indice")
        self.assertTrue(self.etat["actions"]["solution"])
        self.assertEqual(self.presentations(), ["points", "vecteur"])  # rien avant la demande de solution
        r = self.agir("solution")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.statut()["statut"], "solution_vue")
        self.assertEqual(self.statut()["preuve"], "solution")
        # Solution légitimement débloquée : la simulation révélatrice est autorisée.
        self.assertEqual(self.presentations(), ["points", "vecteur", "composantes"])

    def test_deux_tentatives_identiques_ne_font_qu_une(self):
        self.prof.defaut = _retour("Regarde encore.", "calcul", "", "a_revoir")
        self.repondre("B a pour ordonnée 5")
        self.repondre("B a pour ordonnée 5")
        self.agir("indice"); self.agir("indice")
        self.assertEqual(self.agir("solution").status_code, 400)

    # --- Contournements -------------------------------------------------------------------------

    def test_le_client_ne_peut_ni_demander_ni_forcer_une_simulation(self):
        self.aller_a_la_question(3)
        avant = self.presentations()
        forges = {"simulation": "composantes", "simulations": [{"question": "3"}], "revelatrice": False, "statut": "reussie",
                  "preuve": "calcul", "etape_terminee": True, "question": 3, "presentation": "composantes"}
        r = self.agir("reponse", {"texte": "Je ne sais pas calculer ça comme il faut.", **forges})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.presentations(), avant)
        self.assertEqual(self.agir("indice", forges).status_code, 200)
        self.assertEqual(self.presentations(), avant)
        for route in ("simulations/", "simulation/", "solution/composantes/", "visualisation/"):
            self.assertEqual(self.client.post(f"{BASE}{self.etat['seance']}/{route}", {"version": self.etat["version"]}, format="json").status_code, 404, route)
        self.assertEqual(self.agir("solution", forges).status_code, 400)
        self.assertEqual(self.agir("suivante", forges).status_code, 400)  # l'étape n'est pas terminée
        self.assertEqual(self.agir("reponse", {"texte": "AB(3;1)"}, version=1).status_code, 409)  # version périmée
        self.assertEqual(self.presentations(), avant)
        self.assertAucuneFuite()

    def test_simulations_desactivees_ou_production_rien_ne_part(self):
        self.aller_a_la_question(3)
        self.repondre("AB(3 ; 1)")
        self.assertIn("composantes", self.presentations())
        with override_settings(DEBUG=False, IA_PROF_DEV_SEULEMENT=False, SIMULATIONS_DEV_SEULEMENT=True):
            self.assertEqual(self.client.get(f"{BASE}{self.etat['seance']}/").json()["seance"]["simulations"], [])
        with override_settings(SIMULATIONS_ACTIVES=False):
            self.assertEqual(self.client.get(f"{BASE}{self.etat['seance']}/").json()["seance"]["simulations"], [])

    def test_le_controle_independant_ne_depend_pas_des_simulations_actives_en_production(self):
        # Hors développement : pas de simulation, donc pas de contrôle ; l'avis d'IA seul n'est jamais une preuve.
        with override_settings(DEBUG=False, IA_PROF_DEV_SEULEMENT=False, SIMULATIONS_DEV_SEULEMENT=True):
            self.aller_a_la_question(3)
            self.repondre("AB(3 ; 1)")
            self.assertEqual(self.statut()["statut"], "reussie_non_verifiee")
            self.assertEqual(self.etat["simulations"], [])

    # --- Étape calculatoire dont la référence n'a pas pu être confirmée (catégorie B) -----------

    def test_calcul_non_confirme_n_est_jamais_declare_correct(self):
        self.prof.plan_brut = _plan_calcul_non_confirme()
        cache.clear()
        r = self.client.post(BASE, {"programme": self.maths.id, "analyse": copy.deepcopy(ANALYSE_VECTEUR)}, format="json")
        self.noter(r)
        self.repondre("B a pour ordonnée 5")
        etape = self.statut()
        self.assertNotEqual(etape["statut"], "reussie")
        self.assertNotIn("Bravo", self.etat["messages"][-1]["texte"])
        self.assertEqual(self.etat["simulations"], [])
