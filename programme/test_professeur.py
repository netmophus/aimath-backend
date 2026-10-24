"""
Tests du Professeur particulier IA (étape 7). AUCUN appel réel : Anthropic
(`professeur.ia.appeler_outil`) et Wolfram Alpha (`wolfram._requete_http`)
sont simulés ; SymPy tourne pour de vrai (c'est lui qui juge les réponses).
"""

import copy
import inspect
import json
import logging
import re
import time
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from comptes.models import User

from .correction import wolfram
from .ia.exceptions import IAConfigurationInvalide, IAErreurFournisseur, IATimeout
from .models import Cycle, Matiere, Niveau, Programme, Serie
from .professeur import fuite, ia, plan, reponses, seance, tour
from .professeur.reponses import verifier_reponse
from .test_correction_exercice import ANALYSE_EX2, _analyse, _wolfram_simule

BASE = "/api/eleve/professeur/seances/"
CACHE_TEST = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prof-tests"}}

# --------------------------------------------------------------------------
#  Plan simulé (f(x) = x³ − 3x) : 3 étapes, dont une sans calcul vérifiable
# --------------------------------------------------------------------------

def _etape(consigne, indices, solution, reussite, affirmation=None):
    return {"consigne": consigne, "indices": list(indices), "solution": solution, "message_reussite": reussite, "affirmation": affirmation}


AFF_DERIVEE = {"type": "derivee", "description": "Dérivée de f", "fonction": "x^3-3x", "variable": "x", "derivee": "3x^2-3"}
AFF_EQUATION = {"type": "equation", "description": "f'(x)=0", "variable": "x", "gauche": "3x^2-3", "droite": "0", "solutions": ["-1", "1"]}

PLAN_BRUT = {"questions": [
    {"numero": "1", "enonce": "Calculer la dérivée de $f$ et résoudre $f'(x)=0$.", "objectif": "Trouver les points où la tangente est horizontale.", "etapes": [
        _etape("Pour commencer, peux-tu calculer la dérivée de $f(x)=x^3-3x$ ?",
               ["Rappelle-toi la dérivée de $x^n$.", "Dérive terme par terme : d'abord $x^3$, puis $-3x$.", "Pour $x^3$ on obtient un terme en $x^2$ ; écris maintenant celui de $-3x$."],
               "On dérive terme par terme : $(x^3)'=3x^2$ et $(-3x)'=-3$, donc $f'(x)=3x^2-3$.", "Bravo : $f'$ est bien calculée !", AFF_DERIVEE),
        _etape("Maintenant, résous l'équation $f'(x)=0$.",
               ["Une équation du second degré sans terme en $x$ se résout en isolant $x^2$.", "Isole $x^2$ puis prends les deux racines carrées.", "Tu obtiens $x^2 = $ un entier ; quelles valeurs de $x$ conviennent ?"],
               "$3x^2-3=0 \\iff x^2=1 \\iff x=-1$ ou $x=1$.", "Parfait, les deux solutions sont trouvées.", AFF_EQUATION),
    ]},
    {"numero": "2", "enonce": "Étudier les variations de $f$.", "objectif": "Connaître le sens de variation sur chaque intervalle.", "etapes": [
        _etape("Explique avec tes mots pourquoi le signe de $f'$ donne les variations de $f$.",
               ["Pense au lien entre pente de la tangente et sens de variation.", "Si $f'>0$, que fait la fonction ?", "Compare avec une route qui monte ou qui descend."],
               "Si $f'>0$ sur un intervalle, $f$ y est croissante ; si $f'<0$, elle est décroissante.", "Très bien, tu as compris le lien."),
    ]},
]}


def _wolfram(requete: str) -> dict:
    if requete.startswith("solve 3*x^2 - 3 = 0"):
        return {"success": True, "error": False, "pods": [{"id": "Result", "title": "Result", "subpods": [{"plaintext": "x = ±1"}]}]}
    return _wolfram_simule(requete)


def _retour(message="Tu es sur la bonne voie : regarde le terme en $x$.", type_erreur="calcul", resume="Terme constant", evaluation="non_applicable"):
    return {"message": message, "type_erreur": type_erreur, "resume_erreur": resume, "evaluation": evaluation}


class FauxProfesseur:
    """Remplace `ia.appeler_outil` : un plan (jamais plusieurs) puis des retours scriptés."""

    def __init__(self, plan_brut=None, retours=None):
        self.plan_brut = copy.deepcopy(PLAN_BRUT if plan_brut is None else plan_brut)
        self.retours = list(retours or [])
        self.defaut = _retour()
        self.appels = []

    def __call__(self, *, modele, systeme, outil, message, max_tokens, etiquette):
        self.appels.append({"etiquette": etiquette, "message": message, "systeme": systeme, "modele": modele, "max_tokens": max_tokens})
        if etiquette == "plan":
            return copy.deepcopy(self.plan_brut), {"tokens_entree": 3000, "tokens_sortie": 4000}
        retour = self.retours.pop(0) if self.retours else self.defaut
        if isinstance(retour, Exception):
            raise retour
        return copy.deepcopy(retour), {"tokens_entree": 800, "tokens_sortie": 150}

    @property
    def nb_plans(self):
        return sum(1 for a in self.appels if a["etiquette"] == "plan")

    @property
    def nb_tours(self):
        return sum(1 for a in self.appels if a["etiquette"] == "tour")


@override_settings(
    CACHES=CACHE_TEST, DEBUG=True, IA_PROF_ACTIVE=True, IA_PROF_DEV_SEULEMENT=True,
    ANTHROPIC_API_KEY="cle-factice-pour-les-tests", WOLFRAM_APP_ID="app-id-factice", IA_PROF_SEANCE_SECONDES=600,
)
class ProfesseurTests(TestCase):
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
        cls.tle, cls.serie_c = tle, serie_c
        cls.eleve = cls._eleve("+22790000031")
        cls.autre = cls._eleve("+22790000032")

    @classmethod
    def _eleve(cls, tel):
        return User.objects.create_user(tel, password="Motdepasse-2026", prenom="E", nom="L", role=User.Role.ELEVE,
                                        statut=User.Statut.ACTIF, niveau=cls.tle, serie=cls.serie_c)

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.eleve)
        self.prof = FauxProfesseur()
        for cible, remplacement in (
            (ia, ("appeler_outil", self.prof)),
            (wolfram, ("_requete_http", _wolfram)),
        ):
            patcher = mock.patch.object(cible, remplacement[0], side_effect=remplacement[1])
            patcher.start()
            self.addCleanup(patcher.stop)
        lecture = mock.patch("programme.lecture_exercice._envoyer_a_anthropic", side_effect=AssertionError("lecture rappelée"))
        lecture.start()
        self.addCleanup(lecture.stop)
        correction = mock.patch("programme.correction.resolution._appeler_anthropic", side_effect=AssertionError("correction rappelée"))
        correction.start()
        self.addCleanup(correction.stop)

    # --- utilitaires ---------------------------------------------------------

    def demarrer(self, analyse=ANALYSE_EX2, programme=None, client=None):
        return (client or self.client).post(BASE, {"programme": (programme or self.maths_c).id, "analyse": copy.deepcopy(analyse)}, format="json")

    def ouvrir(self, **kw):
        r = self.demarrer(**kw)
        self.assertIn(r.status_code, (200, 201), r.content)
        self.etat = r.json()["seance"]
        return self.etat

    def agir(self, action, corps=None, client=None, version=None):
        donnees = {"version": self.etat["version"] if version is None else version, **(corps or {})}
        r = (client or self.client).post(f"{BASE}{self.etat['seance']}/{action}/", donnees, format="json")
        if r.status_code == 200:
            self.etat = r.json()["seance"]
        return r

    def repondre(self, texte, **kw):
        return self.agir("reponse", {"texte": texte}, **kw)

    def derniers(self, n=1, role="prof"):
        return [m for m in self.etat["messages"] if m["role"] == role][-n:]

    def reussir_etape_1(self):
        self.assertEqual(self.repondre("f'(x) = 3x² - 3").status_code, 200)

    # --- 1. Démarrage --------------------------------------------------------

    def test_demarrage_a_partir_d_un_enonce_confirme(self):
        r = self.demarrer()
        self.assertEqual(r.status_code, 201, r.content)
        corps = r.json()
        etat = corps["seance"]
        self.assertEqual(self.prof.nb_plans, 1)
        self.assertEqual(self.prof.nb_tours, 0)
        self.assertEqual(etat["progression"], {"question": 1, "nb_questions": 2, "etape": 1, "nb_etapes_question": 2,
                                               "etapes_terminees": 0, "nb_etapes_total": 3, "pourcentage": 0})
        self.assertEqual([m["role"] for m in etat["messages"]], ["prof", "prof"])
        self.assertIn("Question 1", etat["messages"][1]["texte"])
        self.assertIn("Ce qu'on cherche", etat["messages"][1]["texte"])
        self.assertIn("calculer la dérivée", etat["messages"][1]["texte"])
        self.assertEqual(etat["etape"]["indices_max"], 3)
        self.assertEqual(etat["actions"], {"repondre": True, "indice": True, "explication": True, "solution": False, "suivante": False})
        self.assertGreater(len(etat["seance"]), 20)

    def test_aucun_secret_dans_les_reponses_de_l_api(self):
        self.ouvrir()
        for r in (self.demarrer(), self.client.get(f"{BASE}{self.etat['seance']}/"), self.repondre("n'importe quoi")):
            texte = r.content.decode()
            for secret in ('"attendu"', '"plan"', '"solution":"', '"indices":[', '"affirmation"', "3x^2-3", "3*x^2 - 3", "On dérive terme par terme",
                           "Rappelle-toi la dérivée", "reference", "affirmation"):
                self.assertNotIn(secret, texte, secret)

    def test_refus_sans_appel_ia(self):
        cas = [
            ("illisible", _analyse("", [], lisible=False), self.maths_c, 400),
            ("incertain", _analyse("x", [("1", "y")], parties_incertaines=[{"page": 1, "extrait": None, "probleme": "tache"}]), self.maths_c, 400),
            ("figure", _analyse("x", [("1", "y")], figures=[{"description": "c", "page": 1, "exploitable": False}]), self.maths_c, 400),
            ("hors maths", ANALYSE_EX2, self.physique_c, 400),
            ("autre classe", ANALYSE_EX2, self.maths_d, 404),
        ]
        for nom, analyse, programme, code in cas:
            with self.subTest(nom):
                self.assertEqual(self.demarrer(analyse, programme).status_code, code)
        self.assertEqual(self.prof.appels, [])

    def test_non_authentifie_et_fonction_desactivee(self):
        self.assertEqual(self.demarrer(client=APIClient()).status_code, 401)
        with override_settings(IA_PROF_ACTIVE=False):
            r = self.demarrer()
            self.assertEqual((r.status_code, r.json()["code"]), (503, "professeur_desactive"))
        with override_settings(DEBUG=False):
            self.assertEqual(self.demarrer().status_code, 503)
        with override_settings(DEBUG=False, IA_PROF_DEV_SEULEMENT=False):
            self.assertEqual(self.demarrer().status_code, 201)
        self.assertEqual(self.prof.nb_plans, 1)

    def test_les_reglages_par_defaut_sont_desactives(self):
        from .reglages_defaut import reglages_par_defaut
        reglages = reglages_par_defaut()  # indépendant du .env local
        self.assertIs(reglages.IA_PROF_ACTIVE, False)
        self.assertIs(reglages.IA_PROF_DEV_SEULEMENT, True)

    def test_reprise_de_la_seance_sans_nouvel_appel_et_plan_partage(self):
        premiere = self.ouvrir()
        r = self.demarrer()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["reprise"])
        self.assertEqual(r.json()["seance"]["seance"], premiere["seance"])
        self.assertEqual(self.prof.nb_plans, 1)
        client = APIClient(); client.force_authenticate(self.autre)  # autre élève, même énoncé : plan réutilisé
        r2 = self.demarrer(client=client)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r2.json()["seance"]["seance"], premiere["seance"])
        self.assertEqual(self.prof.nb_plans, 1)

    # --- 2. Réponse correcte -----------------------------------------------------

    def test_reponse_correcte_validee_par_sympy_sans_appel_ia(self):
        self.ouvrir()
        r = self.repondre("f'(x) = 3x² - 3")
        self.assertEqual(r.status_code, 200, r.content)
        prof = self.derniers()[0]
        self.assertEqual((prof["type"], prof["verification"]), ("reussite", "verifiee"))
        self.assertIn("Bravo", prof["texte"])
        self.assertTrue(self.etat["etape_terminee"])
        self.assertTrue(self.etat["actions"]["suivante"])
        self.assertFalse(self.etat["actions"]["repondre"])
        self.assertEqual(self.prof.nb_tours, 0)  # une bonne réponse ne coûte rien
        self.assertEqual(self.etat["progression"]["etapes_terminees"], 1)

    def test_expressions_equivalentes_acceptees(self):
        for texte in ("3(x^2-1)", "f'(x)=3x^2-3", "$f'(x) = 3(x-1)(x+1)$", "3x^2 - 3 = 3(x²-1)", r"f'(x)=3x^{2}-3"):
            with self.subTest(texte):
                cache.clear(); self.ouvrir()
                self.repondre(texte)
                self.assertTrue(self.etat["etape_terminee"], texte)

    # --- 3. Réponse incorrecte, indices, explications -----------------------------

    def test_reponse_incorrecte_exemple_du_cahier_des_charges(self):
        self.prof.retours = [_retour("Tu as correctement dérivé $x^3$. Vérifie maintenant le signe du terme $-3x$ : quelle est sa dérivée ?")]
        self.ouvrir()
        r = self.repondre("f'(x) = 3x² + 3")
        self.assertEqual(r.status_code, 200)
        prof = self.derniers()[0]
        self.assertEqual((prof["type"], prof["verification"], prof["type_erreur"]), ("retour", "verifiee", "calcul"))
        self.assertIn("correctement dérivé", prof["texte"])
        self.assertFalse(self.etat["etape_terminee"])
        self.assertEqual(self.etat["etape"]["tentatives"], 1)
        # Le modèle a reçu le verdict des outils, la lecture de la réponse et la consigne — pas un historique du navigateur.
        envoye = self.prof.appels[-1]["message"]
        self.assertIn("Statut : incorrect", envoye)
        self.assertIn("3*x^2 + 3", envoye)
        self.assertIn("Éléments corrects : le terme en $x^2$", envoye)
        self.assertIn("Éléments à revoir : le terme constant (signe)", envoye)
        self.assertNotIn("Éléments à revoir : le terme en $x^2$", envoye)
        self.assertIn("<message_eleve>", envoye)
        self.assertIn("JAMAIS la réponse", self.prof.appels[-1]["systeme"])
        # L'élève corrige : la nouvelle expression est vérifiée, puis on peut passer à la suite.
        self.repondre("f'(x) = 3x² - 3")
        self.assertTrue(self.etat["etape_terminee"])
        self.assertEqual(self.etat["etape"]["tentatives"], 2)
        self.agir("suivante")
        self.assertIn("f'(x)=0", self.derniers()[0]["texte"])

    def test_le_modele_ne_peut_pas_declarer_juste_une_reponse_fausse(self):
        self.prof.retours = [_retour("Bravo, c'est correct ! Ta réponse est juste.")]
        self.ouvrir()
        self.repondre("f'(x) = 3x² + 3")
        prof = self.derniers()[0]
        self.assertNotIn("Bravo", prof["texte"])
        self.assertNotIn("est juste", prof["texte"])
        self.assertIn("Bien joué", prof["texte"])  # remplacé par le constat précis de SymPy
        self.assertIn("terme constant", prof["texte"])
        self.assertFalse(self.etat["etape_terminee"])
        self.assertEqual(self.etat["etape"]["tentatives"], 1)

    def test_fuite_de_la_reponse_attendue_est_ecartee(self):
        self.prof.retours = [_retour("Non : la bonne réponse est $f'(x) = 3x^2 - 3$.")]
        self.ouvrir()
        self.repondre("f'(x) = x")
        texte = self.derniers()[0]["texte"]
        self.assertNotIn("3x^2", texte)
        self.assertNotIn("3x²", texte)
        self.assertIn("regarde de plus près", texte)  # retour précis (SymPy) plutôt qu'un texte vague

    def test_reponse_illisible_retour_gratuit(self):
        self.ouvrir()
        r = self.repondre("blabla xyz")
        self.assertEqual(r.status_code, 200)
        prof = self.derniers()[0]
        self.assertEqual(prof["verification"], "illisible")
        self.assertIn("f'(x) = 3x^2 - 1", prof["texte"])
        self.assertEqual(self.prof.nb_tours, 0)
        self.assertEqual(self.etat["etape"]["tentatives"], 0)  # étape 9.2.2 : une entrée inutilisable n'est pas une tentative

    def test_trois_indices_gradues_sans_repetition_ni_appel_ia(self):
        self.ouvrir()
        textes = []
        for niveau in (1, 2, 3):
            self.assertEqual(self.agir("indice").status_code, 200)
            message = self.derniers()[0]
            self.assertEqual((message["type"], message["niveau"]), ("indice", niveau))
            textes.append(message["texte"])
            self.assertEqual(self.etat["etape"]["indices_donnes"], niveau)
        self.assertEqual(textes, PLAN_BRUT["questions"][0]["etapes"][0]["indices"])
        self.assertEqual(len(set(textes)), 3)
        self.assertFalse(self.etat["actions"]["indice"])
        r = self.agir("indice")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "action_refusee"))
        self.assertIn("trois indices", r.json()["detail"])
        self.assertEqual(self.prof.nb_tours, 0)
        # Le niveau suivant d'une AUTRE étape repart de 1.
        self.reussir_etape_1(); self.agir("suivante"); self.agir("indice")
        self.assertEqual(self.derniers()[0]["niveau"], 1)

    def test_explications_de_comprehension(self):
        self.prof.retours = [_retour("Pense à la dérivée comme à une *pente*.", "aucune", "", "non_applicable")] * 4 + [IATimeout("lent")]
        self.ouvrir()
        for type_ in ("incomprehension", "autre_explication", "exemple", "pourquoi"):
            r = self.agir("explication", {"type": type_})
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(self.derniers()[0]["type"], "explication")
        self.assertEqual(self.prof.nb_tours, 4)
        self.assertEqual(self.etat["etape"]["tentatives"], 0)  # une question n'est pas une tentative
        self.assertIn("exemple plus simple", self.prof.appels[-2]["message"])
        r = self.agir("explication", {"type": "question", "texte": "Pourquoi utilise-t-on cette formule ?"})
        self.assertEqual((r.status_code, r.json()["code"]), (504, "ia_lente"))
        self.assertEqual(self.etat["version"], 5)  # l'échec n'a rien consommé
        self.assertEqual(self.agir("explication", {"type": "question"}).status_code, 400)  # question vide

    def test_une_explication_ne_divulgue_pas_la_reponse(self):
        self.prof.retours = [_retour("Voici : $f'(x) = 3x^2 - 3$ !")]
        self.ouvrir()
        self.agir("explication", {"type": "exemple"})
        self.assertNotIn("3x^2 - 3", self.derniers()[0]["texte"])

    # --- 4. Solution progressive ----------------------------------------------------

    def test_solution_de_l_etape_deblocage_progressif(self):
        self.ouvrir()
        r = self.agir("solution")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "action_refusee"))
        self.assertIn("2 tentatives de plus et 2 indices de plus", r.json()["detail"])
        self.repondre("f'(x) = 3x² + 3")                       # tentative 1
        self.assertFalse(self.etat["etape"]["solution_disponible"])
        self.repondre("f'(x) = 3x² + 1")                       # tentative 2
        self.assertFalse(self.etat["etape"]["solution_disponible"])  # indices encore insuffisants
        self.assertIn("2 indices", self.etat["etape"]["conditions_solution"])
        self.agir("indice"); self.assertFalse(self.etat["etape"]["solution_disponible"])
        self.agir("indice")
        self.assertTrue(self.etat["etape"]["solution_disponible"])
        self.assertTrue(self.etat["actions"]["solution"])
        r = self.agir("solution")
        self.assertEqual(r.status_code, 200, r.content)
        prof = self.derniers()[0]
        self.assertEqual(prof["type"], "solution")
        self.assertIn("(x^3)'=3x^2", prof["texte"].replace(" ", "").replace("$", "").replace("\\", "") .replace("(x^3)'", "(x^3)'") or "")
        self.assertIn("cette étape", prof["texte"])
        # Seule l'étape en cours est révélée : ni la suivante, ni l'exercice entier.
        tout = json.dumps(self.etat["messages"], ensure_ascii=False)
        self.assertNotIn("x^2=1", tout)
        self.assertNotIn("route qui monte", tout)
        self.assertNotIn("Si $f'>0$ sur un intervalle", tout)
        self.assertTrue(self.etat["etape_terminee"])

    def test_plus_de_solution_sans_indices_meme_apres_quatre_tentatives(self):
        # Étape 9.2.2 : le raccourci « quatre réponses sans indice » est supprimé ; l'élève bloqué utilise les indices.
        self.ouvrir()
        for essai in ("1", "2", "3", "4"):
            self.repondre(f"f'(x) = {essai}x")
        self.assertEqual(self.etat["etape"]["tentatives"], 4)
        self.assertFalse(self.etat["etape"]["solution_disponible"])
        self.assertEqual(self.agir("solution").status_code, 400)
        self.agir("indice"); self.agir("indice")
        self.assertTrue(self.etat["etape"]["solution_disponible"])
        self.assertEqual(self.agir("solution").status_code, 200)

    def test_solution_refusee_une_fois_l_etape_terminee(self):
        self.ouvrir(); self.reussir_etape_1()
        self.assertEqual(self.agir("solution").status_code, 400)
        self.assertEqual(self.repondre("x").status_code, 400)
        self.assertEqual(self.agir("indice").status_code, 400)

    # --- 5. Progression -------------------------------------------------------------

    def test_passage_a_la_question_suivante_et_fin_de_l_exercice(self):
        self.ouvrir()
        r = self.agir("suivante")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "action_refusee"))  # étape non terminée
        self.reussir_etape_1()
        self.agir("suivante")
        self.assertEqual((self.etat["progression"]["question"], self.etat["progression"]["etape"]), (1, 2))
        self.repondre("x = -1 ou x = 1")
        self.assertTrue(self.etat["etape_terminee"])
        self.agir("suivante")
        self.assertEqual(self.etat["progression"]["question"], 2)
        self.assertIn("Question 2", self.derniers()[0]["texte"])
        self.assertIn("Connaître le sens de variation", self.derniers()[0]["texte"])
        # Étape sans calcul vérifiable : l'avis de l'IA ne vaut PAS validation automatique.
        self.prof.retours = [_retour("Oui, tu as saisi l'idée.", "aucune", "", "plausible")]
        self.repondre("Quand f' est positive, f monte.")
        prof = self.derniers()[0]
        self.assertEqual(prof["verification"], "non_verifiable")
        self.assertTrue(self.etat["etape_terminee"])
        self.agir("suivante")
        self.assertTrue(self.etat["termine"])
        self.assertEqual(self.etat["progression"]["pourcentage"], 100)
        fin = self.derniers()[0]
        self.assertEqual(fin["type"], "fin")
        self.assertIn("Exercice terminé", fin["texte"])
        self.assertIn("pas pu être vérifiée automatiquement : 1", fin["texte"])
        self.assertEqual(self.agir("suivante").status_code, 400)
        self.assertFalse(any(self.etat["actions"][a] for a in ("repondre", "indice", "solution", "suivante", "explication")))

    # --- 6. Vérification mathématique ----------------------------------------------

    def test_ensemble_de_solutions_complet_incomplet_et_faux(self):
        self.ouvrir(); self.reussir_etape_1(); self.agir("suivante")
        self.prof.retours = [_retour("Cherche aussi l'autre racine.")]
        self.repondre("x = 1")
        self.assertFalse(self.etat["etape_terminee"])
        self.assertIn("il manque 1 solution", self.prof.appels[-1]["message"])
        self.repondre("S = {-1 ; 1}")
        self.assertTrue(self.etat["etape_terminee"])

    def test_etape_sans_calcul_verifiable_n_est_jamais_dite_correcte(self):
        self.ouvrir(); self.reussir_etape_1(); self.agir("suivante"); self.repondre("x=1 ou x=-1"); self.agir("suivante")
        for evaluation, termine, reponse in (("a_revoir", False, "Parce que c'est comme ça."), ("plausible", True, "Parce que le signe change.")):
            cache.delete(f"prof:verrou:{self.etat['seance']}")
            self.prof.retours = [_retour("Voici mon avis.", "aucune", "", evaluation)]
            self.repondre(reponse)
            self.assertEqual(self.etat["etape_terminee"], termine, evaluation)
            self.assertEqual(self.derniers()[0]["verification"], "non_verifiable")
            self.assertIn("Statut : non vérifiable", self.prof.appels[-1]["message"])

    def test_contradiction_sympy_contre_reference_ia_rend_l_etape_incertaine(self):
        fausse = copy.deepcopy(PLAN_BRUT)
        fausse["questions"][0]["etapes"][0]["affirmation"] = {**AFF_DERIVEE, "derivee": "3x^2+3"}  # l'IA se trompe
        self.prof.plan_brut = fausse
        self.prof.retours = [_retour("Je ne peux pas confirmer cette réponse automatiquement.", "aucune", "", "plausible")]
        self.ouvrir()
        self.repondre("f'(x) = 3x² + 3")  # exactement la (fausse) référence de l'IA : elle ne doit PAS être validée
        prof = self.derniers()[0]
        self.assertEqual(prof["verification"], "incertaine")
        self.assertFalse(self.etat["etape_terminee"])
        self.assertFalse(self.etat["etape"]["verifiable"])
        self.assertNotIn("<reponse_attendue", self.prof.appels[-1]["message"])  # la référence douteuse n'est pas utilisée
        # La vraie dérivée n'est pas non plus « validée » par un outil contredit : on signale l'incertitude.
        self.repondre("f'(x) = 3x² - 3")
        self.assertFalse(self.etat["etape_terminee"])
        # Solution : signalée comme non confirmée.
        self.agir("indice"); self.agir("indice"); self.agir("solution")
        self.assertIn("ne confirment pas", self.derniers()[0]["texte"])
        self.assertEqual(self.derniers()[0]["verification"], "non_verifiable")

    def test_contradiction_wolfram_contre_sympy_rend_l_etape_incertaine(self):
        def wolfram_faux(requete):
            if requete.startswith("derivative of"):
                return {"success": True, "error": False, "pods": [{"id": "Input", "title": "", "subpods": [{"plaintext": "d/dx(x^3 - 3 x) = 3 x^2 + 3"}]}]}
            return _wolfram(requete)
        with mock.patch.object(wolfram, "_requete_http", side_effect=wolfram_faux):
            self.ouvrir()
        self.repondre("f'(x) = 3x² - 3")
        self.assertFalse(self.etat["etape_terminee"])  # les outils se contredisent : on ne valide pas
        self.assertEqual(self.derniers()[0]["verification"], "incertaine")

    def test_wolfram_en_panne_sympy_suffit(self):
        def panne(_):
            raise wolfram.WolframIndisponible("hors ligne")
        with mock.patch.object(wolfram, "_requete_http", side_effect=panne):
            self.ouvrir()
        self.repondre("f'(x) = 3x² - 3")
        self.assertTrue(self.etat["etape_terminee"])

    def test_wolfram_n_est_interroge_qu_au_demarrage_et_pour_les_types_utiles(self):
        with mock.patch.object(wolfram, "_requete_http", side_effect=_wolfram) as appel:
            self.ouvrir()
            n = appel.call_count
            self.repondre("f'(x) = 3x² - 3"); self.repondre("x"); self.agir("indice")
            self.assertEqual(appel.call_count, n)  # aucune requête Wolfram pendant les échanges avec l'élève
        self.assertEqual(n, 2)  # dérivée + équation ; l'étape sans calcul n'en demande aucune

    # --- 7. Double clic, concurrence, versions ------------------------------------------

    def test_double_clic_une_seule_action_prise_en_compte(self):
        self.prof.retours = [_retour()]
        self.ouvrir()
        version = self.etat["version"]
        premiere = self.client.post(f"{BASE}{self.etat['seance']}/reponse/", {"version": version, "texte": "f'(x) = 3x² + 3"}, format="json")
        seconde = self.client.post(f"{BASE}{self.etat['seance']}/reponse/", {"version": version, "texte": "f'(x) = 3x² + 3"}, format="json")
        self.assertEqual(premiere.status_code, 200)
        self.assertEqual((seconde.status_code, seconde.json()["code"]), (409, "etat_obsolete"))
        self.assertEqual(seconde.json()["seance"]["version"], version + 1)  # l'écran peut se resynchroniser
        self.assertEqual(self.prof.nb_tours, 1)
        self.assertEqual(premiere.json()["seance"]["etape"]["tentatives"], 1)

    def test_action_simultanee_refusee_par_le_verrou(self):
        self.ouvrir()
        cache.add(f"prof:verrou:{self.etat['seance']}", 1, timeout=60)
        r = self.repondre("f'(x) = 3x² + 3")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "occupee"))
        self.assertEqual(self.prof.nb_tours, 0)
        cache.delete(f"prof:verrou:{self.etat['seance']}")
        self.assertEqual(self.agir("indice").status_code, 200)

    def test_verrou_relache_apres_echec_ia(self):
        self.ouvrir()
        self.prof.retours = [IATimeout("lent")]
        self.assertEqual(self.agir("explication", {"type": "exemple"}).status_code, 504)
        self.assertEqual(self.agir("indice").status_code, 200)

    def test_double_demarrage_simultane(self):
        analyse = service_normalisee = None  # noqa: F841
        from .lecture_exercice import ContexteProgramme, normaliser_analyse
        brute = normaliser_analyse(copy.deepcopy(ANALYSE_EX2), ContexteProgramme("Mathématiques", "Terminale C"))
        cache.add(f"prof:verrou_plan:{self.eleve.id}:{seance._empreinte(brute)}", 1, timeout=60)
        r = self.demarrer()
        self.assertEqual((r.status_code, r.json()["code"]), (409, "occupee"))
        self.assertEqual(self.prof.appels, [])

    # --- 8. Accès, session, limites -----------------------------------------------------

    def test_la_seance_d_un_autre_eleve_est_introuvable(self):
        self.ouvrir()
        client = APIClient(); client.force_authenticate(self.autre)
        self.assertEqual(client.get(f"{BASE}{self.etat['seance']}/").status_code, 404)
        self.assertEqual(self.agir("indice", client=client).status_code, 404)
        self.assertEqual(self.agir("solution", client=client).status_code, 404)
        self.assertEqual(self.prof.nb_tours, 0)

    def test_non_authentifie_et_identifiants_inventes(self):
        self.ouvrir()
        sans = APIClient()
        self.assertEqual(sans.get(f"{BASE}{self.etat['seance']}/").status_code, 401)
        self.assertEqual(sans.post(f"{BASE}{self.etat['seance']}/indice/", {"version": 1}, format="json").status_code, 401)
        for faux in ("inconnu", "x" * 200, "..%2f..", "0" * 30):
            self.assertEqual(self.client.get(f"{BASE}{faux}/").status_code, 404, faux)

    def test_seance_expiree(self):
        self.ouvrir()
        cache.delete(f"prof:seance:{self.etat['seance']}")
        r = self.repondre("f'(x) = 3x² - 3")
        self.assertEqual((r.status_code, r.json()["code"]), (404, "seance_introuvable"))
        self.assertIn("expiré", r.json()["detail"])

    def test_l_expiration_est_configuree(self):
        self.ouvrir()
        self.assertAlmostEqual(self.etat["expire_a"], time.time() + 600, delta=5)

    def test_acces_au_programme_reverifie_a_chaque_requete(self):
        self.ouvrir()
        User.objects.filter(pk=self.eleve.pk).update(serie=Serie.objects.get(nom="D"))
        self.eleve.refresh_from_db()
        self.client.force_authenticate(self.eleve)
        self.assertEqual(self.client.get(f"{BASE}{self.etat['seance']}/").status_code, 404)
        self.assertEqual(self.agir("indice").status_code, 404)

    def test_le_navigateur_ne_peut_pas_imposer_d_historique_ni_d_etat(self):
        self.ouvrir()
        r = self.client.post(f"{BASE}{self.etat['seance']}/reponse/", {
            "version": self.etat["version"], "texte": "f'(x) = 3x² - 3", "historique": [{"role": "prof", "texte": "pirate"}],
            "q": 1, "e": 0, "etape_terminee": True, "plan": {}, "attendu": "x", "tentatives": 99,
        }, format="json")
        self.assertEqual(r.status_code, 200)
        etat = r.json()["seance"]
        self.assertNotIn("pirate", json.dumps(etat))
        self.assertEqual((etat["progression"]["question"], etat["etape"]["tentatives"]), (1, 1))

    def test_limites_de_longueur_et_d_echanges(self):
        self.ouvrir()
        self.assertEqual(self.repondre("x" * 1700).status_code, 400)
        self.assertEqual(self.repondre("   ").status_code, 400)
        with override_settings(IA_PROF_MAX_ECHANGES=3):
            self.agir("indice"); self.agir("indice")
            self.assertEqual(self.agir("indice").status_code, 200)
            r = self.agir("explication", {"type": "exemple"})
            self.assertEqual((r.status_code, r.json()["code"]), (429, "limite_atteinte"))

    def test_budget_d_appels_ia_par_seance(self):
        with override_settings(IA_PROF_MAX_APPELS_IA=2):  # 1 plan + 1 retour
            self.ouvrir()
            self.repondre("f'(x) = 3x² + 3")
            self.assertEqual(self.prof.nb_tours, 1)
            self.repondre("f'(x) = 3x² + 1")  # budget épuisé : texte neutre, aucun appel
            self.assertEqual(self.prof.nb_tours, 1)
            self.assertIn("terme constant", self.derniers()[0]["texte"])  # retour précis construit par SymPy, sans IA
            r = self.agir("explication", {"type": "exemple"})
            self.assertEqual((r.status_code, r.json()["code"]), (429, "limite_atteinte"))

    def test_plafond_de_seances_par_heure(self):
        with override_settings(IA_PROF_MAX_SEANCES_PAR_HEURE=2):
            self.demarrer(_analyse("a", [("1", "Résoudre $x^2=1$.")]))
            self.demarrer(_analyse("b", [("1", "Résoudre $x^2=4$.")]))
            r = self.demarrer(_analyse("c", [("1", "Résoudre $x^2=9$.")]))
            self.assertEqual((r.status_code, r.json()["code"]), (429, "limite_atteinte"))

    def test_retour_ia_en_panne_donne_un_texte_neutre_sans_perdre_le_verdict(self):
        self.prof.retours = [IAErreurFournisseur("boom")]
        self.ouvrir()
        r = self.repondre("f'(x) = 3x² + 3")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.derniers()[0]["verification"], "verifiee")
        self.assertIn("terme constant", self.derniers()[0]["texte"])
        self.assertIn("Bien joué", self.derniers()[0]["texte"])
        self.assertFalse(self.etat["etape_terminee"])

    def test_erreurs_du_plan_messages_francais_sans_fuite(self):
        for erreur, code in ((IAConfigurationInvalide("cle-factice-pour-les-tests"), 503), (IATimeout("t"), 504), (IAErreurFournisseur("http 500"), 502)):
            cache.clear()
            with mock.patch.object(ia, "appeler_outil", side_effect=erreur):
                r = self.demarrer()
            self.assertEqual(r.status_code, code)
            self.assertNotIn("cle-factice", r.content.decode())
        r = self.demarrer()  # le verrou a été relâché, rien n'est resté en cache
        self.assertEqual(r.status_code, 201)

    def test_plan_vide_refuse(self):
        self.prof.plan_brut = {"questions": []}
        self.assertEqual(self.demarrer().status_code, 502)

    # --- 9. Suivi des coûts -------------------------------------------------------------------

    def test_suivi_des_tokens(self):
        with self.assertLogs("programme.professeur.seance", level=logging.INFO) as journaux:
            self.ouvrir()
        self.assertTrue(any("professeur plan" in ligne for ligne in journaux.output))
        r = self.client.get(f"{BASE}{self.etat['seance']}/")
        self.assertEqual(r.json()["meta_dev"], {"tokens_entree": 3000, "tokens_sortie": 4000, "appels_ia": 1})
        self.repondre("f'(x) = 3x² + 3")
        self.assertEqual(self.client.get(f"{BASE}{self.etat['seance']}/").json()["meta_dev"],
                         {"tokens_entree": 3800, "tokens_sortie": 4150, "appels_ia": 2})
        with override_settings(DEBUG=False, IA_PROF_DEV_SEULEMENT=False):
            self.assertNotIn("meta_dev", self.client.get(f"{BASE}{self.etat['seance']}/").json())

    def test_depot_annonce_le_professeur_seulement_si_active(self):
        def depot():
            with mock.patch("programme.lecture_exercice._envoyer_a_anthropic", return_value=(copy.deepcopy(ANALYSE_EX2), {})):
                return self.client.post("/api/eleve/resoudre/", {"programme": self.maths_c.id, "mode": "professeur", "enonce": "x", "analyser": "true"}, format="multipart")
        with override_settings(IA_LECTURE_ACTIVE=True):
            self.assertIs(depot().json()["professeur_disponible"], True)
            with override_settings(IA_PROF_ACTIVE=False):
                self.assertIs(depot().json()["professeur_disponible"], False)
        with override_settings(IA_LECTURE_ACTIVE=False):
            self.assertIs(depot().json()["professeur_disponible"], False)


    # --- 7.1 Pédagogie des retours et aide progressive ---------------------------------

    SOLUTION_ETAPE_1 = "On dérive terme par terme"
    SOLUTION_ETAPE_2 = "x^2=1"

    def _aucune_fuite(self, etat=None):
        """Ni la réponse attendue ni les solutions (de cette étape comme des suivantes) dans ce que voit l'élève."""
        tout = json.dumps((etat or self.etat)["messages"], ensure_ascii=False)
        for secret in (self.SOLUTION_ETAPE_1, self.SOLUTION_ETAPE_2, "route qui monte"):
            self.assertNotIn(secret, tout, secret)
        texte_prof = " ".join(m["texte"] for m in (etat or self.etat)["messages"] if m["role"] == "prof")
        self.assertNotIn("3x^2-3", texte_prof.replace(" ", "").replace("$", ""))
        self.assertNotIn("3x²-3", texte_prof.replace(" ", "").replace("$", ""))

    def test_scenario_complet_de_l_aide_progressive(self):
        self.prof.retours = [
            _retour("Tu as correctement dérivé $x^3$. Vérifie maintenant le signe du terme $-3x$ : quelle est sa dérivée ?", "calcul", "Signe du terme constant"),
            _retour("Ton terme en $x^2$ est juste ; regarde ce que devient le terme constant : quelle règle appliques-tu à $-3x$ ?", "aucune", ""),
            _retour("On cherche à comprendre la dérivée comme une pente : celle de $-3x$ est la même partout.", "aucune", "", "non_applicable"),
        ]
        self.ouvrir()
        # 1. réponse incorrecte
        self.repondre("f'(x) = 3x² + 3")
        retour = self.derniers()[0]
        self.assertEqual((retour["type"], retour["verification"], retour["type_erreur"]), ("retour", "verifiee", "calcul"))
        self.assertIn("correctement dérivé", retour["texte"])
        self.assertIn("signe du terme", retour["texte"])
        self.assertFalse(self.etat["actions"]["solution"])
        # 2. premier indice : la notion, sans calcul
        self.agir("indice")
        niveau1 = self.derniers()[0]
        self.assertEqual((niveau1["type"], niveau1["niveau"]), ("indice", 1))
        self.assertIn("Rappelle-toi la dérivée de $x^n$", niveau1["texte"])
        self.assertEqual(self.etat["etape"]["indices_donnes"], 1)
        # 3. nouvelle erreur : retour adapté (le terme en x² est reconnu juste), nouvelle tentative
        self.repondre("f'(x) = 3x² + 1")
        self.assertEqual(self.etat["etape"]["tentatives"], 2)
        self.assertIn("terme en $x^2$ est juste", self.derniers()[0]["texte"])
        self.assertFalse(self.etat["actions"]["solution"])  # 2 tentatives mais un seul indice
        r = self.agir("solution")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn(self.SOLUTION_ETAPE_1, r.content.decode())
        # 4. deuxième indice : la méthode
        self.agir("indice")
        niveau2 = self.derniers()[0]
        self.assertEqual(niveau2["niveau"], 2)
        self.assertNotEqual(niveau2["texte"], niveau1["texte"])
        self.assertIn("terme par terme", niveau2["texte"])
        # 5. explication supplémentaire : n'avance ni les tentatives ni les indices
        avant = (self.etat["etape"]["tentatives"], self.etat["etape"]["indices_donnes"])
        self.agir("explication", {"type": "autre_explication"})
        self.assertEqual((self.etat["etape"]["tentatives"], self.etat["etape"]["indices_donnes"]), avant)
        self.assertEqual(self.derniers()[0]["type"], "explication")
        # 6. troisième indice : l'étape intermédiaire, sans tout dévoiler
        self.agir("indice")
        niveau3 = self.derniers()[0]
        self.assertEqual(niveau3["niveau"], 3)
        self.assertEqual(len({niveau1["texte"], niveau2["texte"], niveau3["texte"]}), 3)  # aucun indice répété
        self.assertNotIn("3x^2 - 3", niveau3["texte"])
        self.assertFalse(self.etat["actions"]["indice"])
        self.assertEqual(self.agir("indice").status_code, 400)  # pas de 4e indice
        self._aucune_fuite()
        # 7-8. la solution de l'ÉTAPE ACTUELLE seulement
        self.assertTrue(self.etat["actions"]["solution"])
        self.assertEqual(self.agir("solution").status_code, 200)
        solution = self.derniers()[0]
        self.assertEqual(solution["type"], "solution")
        self.assertIn(self.SOLUTION_ETAPE_1, solution["texte"])
        self.assertNotIn(self.SOLUTION_ETAPE_2, json.dumps(self.etat["messages"], ensure_ascii=False))
        self.assertEqual(self.repondre("f'(x) = 3x² - 3").status_code, 400)  # étape terminée : plus de réponse
        # 9. étape suivante : la solution de CETTE étape n'est pas accessible
        self.agir("suivante")
        self.assertIn("f'(x)=0", self.derniers()[0]["texte"])
        self.assertFalse(self.etat["actions"]["solution"])
        r = self.agir("solution")
        self.assertEqual(r.status_code, 400)
        self.assertNotIn(self.SOLUTION_ETAPE_2, r.content.decode())
        self.assertEqual(self.prof.nb_tours, 3)  # 2 retours + 1 explication : aucun appel superflu

    def test_api_directe_ne_contourne_pas_le_deblocage(self):
        self.ouvrir()
        interdits = (self.SOLUTION_ETAPE_1, "3x^2-3", "3x²-3")
        refus = []
        def tenter():
            r = self.agir("solution")
            self.assertEqual((r.status_code, r.json()["code"]), (400, "action_refusee"), r.content)
            refus.append(r.content.decode())
        tenter()                                            # rien fait
        self.agir("indice"); self.agir("indice"); self.agir("indice")
        tenter()                                            # indices seuls : 0 tentative
        self.repondre("f'(x) = 3x² + 3")
        tenter()                                            # 1 tentative
        self.repondre("f'(x) = 3x² + 3")                    # même réponse : ne compte pas comme tentative
        self.assertEqual(self.etat["etape"]["tentatives"], 1)
        self.assertIn("déjà envoyé", self.derniers()[0]["texte"])
        tenter()
        self.repondre("f'(x) = 3x² + 2")                    # 2e tentative : les conditions (2 + 2) sont remplies
        r = self.agir("solution")
        self.assertEqual(r.status_code, 200)
        for corps in refus:
            for secret in interdits:
                self.assertNotIn(secret, corps)
        # Autres contournements : mauvaise version, autre élève, étape non terminée (nouvelle séance).
        cache.clear()
        self.ouvrir()
        r = self.agir("solution", version=self.etat["version"] + 5)
        self.assertEqual((r.status_code, r.json()["code"]), (409, "etat_obsolete"))
        self.assertIsNone(cache.get(f"prof:verrou:{self.etat['seance']}"))  # une requête périmée ne verrouille pas la séance
        autre = APIClient(); autre.force_authenticate(self.autre)
        self.assertEqual(self.agir("solution", client=autre).status_code, 404)
        self.assertEqual(self.agir("suivante").status_code, 400)

    def test_plusieurs_reponses_incorrectes_et_aucun_double_appel_ia(self):
        self.ouvrir()
        for essai in ("3x²+3", "3x²+2", "2x²-3", "3x", "x²-3"):
            self.repondre(f"f'(x) = {essai}")
        self.assertEqual(self.prof.nb_tours, 5)
        self.assertEqual(self.etat["etape"]["tentatives"], 5)
        self.assertFalse(self.etat["actions"]["solution"])                 # étape 9.2.2 : il faut aussi deux indices
        self.agir("indice"); self.agir("indice")
        self.assertTrue(self.etat["actions"]["solution"])                  # on ne bloque pas indéfiniment
        self._aucune_fuite()
        # Renvoyer deux fois la même réponse (double clic, réponse recopiée) : aucun nouvel appel IA.
        appels = self.prof.nb_tours
        self.repondre("f'(x) = x²-3")
        self.repondre("f'(x)=x² - 3")
        self.assertEqual(self.prof.nb_tours, appels)
        self.assertEqual(self.etat["etape"]["tentatives"], 5)
        # Requête rejouée avec une version périmée : refusée, aucun appel IA.
        r = self.repondre("f'(x) = 7x", version=self.etat["version"] - 1)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.prof.nb_tours, appels)

    def test_retours_precis_selon_l_erreur_reelle(self):
        self.prof.retours = [IAErreurFournisseur("boom")] * 4  # IA en panne : le retour précis vient de SymPy seul
        attendus = (
            ("f'(x) = 3x² + 3", ["terme en $x^2$", "terme constant"], "calcul"),
            ("f'(x) = 3x²", ["terme en $x^2$", "terme constant"], "non_precise"),
            ("f'(x) = 2x² - 3", ["terme constant", "terme en $x^2$"], "non_precise"),
            ("f'(x) = -3x² + 3", ["terme en $x^2$"], "calcul"),
        )
        self.ouvrir()
        for reponse, mots, type_erreur in attendus:
            with self.subTest(reponse):
                self.repondre(reponse)
                prof = self.derniers()[0]
                for mot in mots:
                    self.assertIn(mot, prof["texte"])
                self.assertEqual((prof["verification"], prof["type_erreur"]), ("verifiee", type_erreur))
                self.assertIn("?", prof["texte"])  # une question qui permet de se corriger
        self.assertNotIn("Bien joué sur ce point : le terme constant", self.etat["messages"][-1]["texte"])  # rien d'inventé
        self._aucune_fuite()

    def test_cause_d_erreur_jamais_inventee(self):
        # Coefficient faux : SymPy ne peut pas dire POURQUOI (règle mal appliquée ? étourderie ?) → pas de cause affirmée.
        faux = verifier_reponse({"type": "expression", "valeur": "3x^2-3"}, "2x^2-3")
        self.assertEqual(faux.erreur_probable, "")
        self.assertEqual([i["nature"] for i in faux.a_revoir], ["coefficient"])
        self.assertEqual(faux.acquis, ["le terme constant"])
        # Seul un écart de signe est qualifié d'étourderie probable.
        self.assertEqual(verifier_reponse({"type": "expression", "valeur": "3x^2-3"}, "3x^2+3").erreur_probable, "calcul")
        envoye = None
        self.ouvrir()
        self.repondre("f'(x) = 2x² - 3")
        envoye = self.prof.appels[-1]["message"]
        self.assertIn("Nature probable de l'écart : indéterminée", envoye)
        self.assertIn("NE L'INVENTE PAS", self.prof.appels[-1]["systeme"])

    def test_phrases_qui_declarent_juste_la_reponse_entiere_sont_retirees_le_reste_est_garde(self):
        self.prof.retours = [_retour("Ton terme en $x^2$ est juste. Bravo, tu as tout bon ! Quel est le signe du terme constant ?")]
        self.ouvrir()
        self.repondre("f'(x) = 3x² + 3")
        texte = self.derniers()[0]["texte"]
        self.assertIn("terme en $x^2$ est juste", texte)      # validation d'une PARTIE précise : conservée
        self.assertIn("signe du terme constant", texte)
        self.assertNotIn("Bravo", texte)                       # validation de la réponse entière : retirée
        self.assertNotIn("tout bon", texte)
        self.assertFalse(self.etat["etape_terminee"])

    def test_la_protection_contre_la_divulgation_n_est_pas_assouplie(self):
        for message in ("Il faut obtenir $3x^2 - 3$.", "La réponse est f'(x)=3x²−3", "donc $f'(x) = 3(x^2-1)$ ... soit $3x^2-3$."):
            with self.subTest(message):
                cache.clear(); self.prof.retours = [_retour(message)]
                self.ouvrir()
                self.repondre("f'(x) = 3x² + 3")
                texte = self.derniers()[0]["texte"].replace(" ", "").replace("$", "")
                self.assertNotIn("3x^2-3", texte)
                self.assertNotIn("3x²−3", texte)
                self.assertIn("terme constant", self.derniers()[0]["texte"])  # constat précis de SymPy à la place

    def test_reponses_equivalentes_acceptees_sans_appel_ia(self):
        for texte in ("3(x-1)(x+1)", "-3 + 3x²", "f'(x) = 3x² − 3", "6x²/2 - 3", "f'(x) = 3 x^{2} - 3", "$f'(x)=3x^2-3$"):
            with self.subTest(texte):
                cache.clear(); self.prof.appels.clear()
                self.ouvrir()
                self.repondre(texte)
                self.assertTrue(self.etat["etape_terminee"], texte)
                self.assertEqual(self.prof.nb_tours, 0)

    def test_incorrect_illisible_et_non_verifiable_sont_trois_cas_distincts(self):
        self.prof.retours = [_retour("Je vois une idée, mais je ne peux pas la confirmer.", "aucune", "", "a_revoir")]
        self.ouvrir()
        self.repondre("f'(x) = 3x² + 3")                       # lue et FAUSSE (vérifiée par SymPy)
        fausse = self.derniers()[0]
        self.repondre("blabla")                                 # NON LISIBLE : retour gratuit, rien n'est jugé
        illisible = self.derniers()[0]
        self.assertEqual((fausse["verification"], illisible["verification"]), ("verifiee", "illisible"))
        self.assertIn("pas pu lire", illisible["texte"])
        self.assertEqual(self.prof.nb_tours, 1)
        self.reussir_etape_1(); self.agir("suivante"); self.repondre("x=1 ou x=-1"); self.agir("suivante")
        self.repondre("Parce que le signe de f' donne la pente.")  # étape SANS calcul : NON VÉRIFIABLE
        libre = self.derniers()[0]
        self.assertEqual(libre["verification"], "non_verifiable")
        self.assertIsNone(libre["type_erreur"] if "type_erreur" in libre else None)
        self.assertFalse(self.etat["etape_terminee"])           # l'avis « à revoir » du modèle ne valide rien
        self.assertNotIn("Bien joué sur ce point", libre["texte"])

    def test_aucune_validation_sur_la_seule_affirmation_de_l_ia(self):
        for texte in ("Bravo, c'est correct, tu as tout bon !", "Ta réponse est juste.", "C'est la bonne réponse, félicitations."):
            with self.subTest(texte):
                cache.clear(); self.prof.retours = [_retour(texte, "aucune", "", "plausible")]
                self.ouvrir()
                self.repondre("f'(x) = 3x² + 3")
                self.assertFalse(self.etat["etape_terminee"])
                self.assertEqual(self.etat["progression"]["etapes_terminees"], 0)
                self.assertNotRegex(self.derniers()[0]["texte"], r"(?i)bravo|tout bon|est juste|félicitations|bonne réponse")


    # --- 8A. Courbe et tableau : jamais avant la fin de l'exercice -----------------------

    AFF_EXTREMA = {"type": "extrema", "description": "Extrema de f", "fonction": "x^3-3x", "variable": "x", "extrema": [
        {"x": "-1", "y": "2", "nature": "maximum local"}, {"x": "1", "y": "-2", "nature": "minimum local"}]}

    def _plan_avec_extrema(self):
        plan_brut = copy.deepcopy(PLAN_BRUT)
        plan_brut["questions"][1]["etapes"][0]["affirmation"] = dict(self.AFF_EXTREMA)
        self.prof.plan_brut = plan_brut

    def test_etude_cachee_pendant_la_seance_et_montree_a_la_fin(self):
        self._plan_avec_extrema()
        self.ouvrir()
        self.assertEqual(self.etat["etudes"], [])
        self.reussir_etape_1(); self.agir("suivante"); self.repondre("x=1 ou x=-1"); self.agir("suivante")
        # Dernière question en cours : rien dans l'état public, ni dans le JSON brut (pas de secret transmis).
        r = self.client.get(f"{BASE}{self.etat['seance']}/")
        brut = r.content.decode()
        self.assertEqual(r.json()["seance"]["etudes"], [])
        for secret in ('"tableau"', '"courbe"', '"domaine_x"', "maximum local", '"extrema"'):
            self.assertNotIn(secret, brut, secret)
        self.assertNotIn("maximum local", json.dumps(self.etat["messages"], ensure_ascii=False))
        # Fin de l'exercice : l'étude (calculée par SymPy au démarrage) est montrée.
        self.prof.retours = [_retour("Voici mon avis.", "aucune", "", "plausible")]
        self.repondre("Le signe de f' donne les variations.")
        if not self.etat["etape_terminee"]:  # étape sans référence vérifiable : on débloque la solution
            for essai in ("signe", "variations"):
                self.repondre(f"réponse {essai} de f'")
            self.agir("indice"); self.agir("indice")
            self.agir("solution")
        self.agir("suivante")
        self.assertTrue(self.etat["termine"])
        etude = self.etat["etudes"][0]
        self.assertEqual(etude["question"], "2")
        self.assertEqual(etude["etude"]["statut"], "verifie")
        self.assertEqual(etude["etude"]["tableau"]["f"], ["-\infty", "2", "-2", "+\infty"])
        self.assertEqual([x["nature"] for x in etude["etude"]["extrema"]], ["maximum local", "minimum local"])

    def test_pas_d_etude_sans_question_de_variations_ou_d_extrema(self):
        self.ouvrir()
        self.assertEqual(seance.charger(self.etat["seance"], self.eleve.id)["etudes"], [])


# --------------------------------------------------------------------------
#  Briques unitaires
# --------------------------------------------------------------------------

class ReponsesTests(SimpleTestCase):
    EXPR = {"type": "expression", "valeur": "3x^2-3"}
    ENS = {"type": "ensemble", "valeurs": ["2", "3"]}

    def test_expressions(self):
        self.assertEqual(verifier_reponse(self.EXPR, "3(x²-1)").statut, "correct")
        faux = verifier_reponse(self.EXPR, "3x²+3")
        self.assertEqual((faux.statut, faux.erreur_probable), ("incorrect", "calcul"))
        self.assertIn("terme constant a le mauvais signe", faux.diagnostic)
        self.assertEqual(faux.acquis, ["le terme en $x^2$"])
        signe = verifier_reponse(self.EXPR, "-3x²+3")
        self.assertIn("mauvais signe", signe.diagnostic)
        self.assertFalse(fuite.contient_la_reponse(verifier_reponse(self.EXPR, "x^3").diagnostic, self.EXPR))  # jamais la valeur attendue
        self.assertEqual(verifier_reponse(self.EXPR, "bof").statut, "non_verifiable")

    def test_le_diagnostic_ne_contient_jamais_la_reponse_attendue(self):
        for essai in ("3x²+3", "-3x²+3", "6x²-6", "x^3", "3x^2-4"):
            diagnostic = verifier_reponse(self.EXPR, essai).diagnostic
            self.assertFalse(fuite.contient_la_reponse(diagnostic, self.EXPR), diagnostic)

    def test_ensembles(self):
        for texte in ("x=2 ou x=3", "S={2;3}", "{3, 2}", "2 et 3", r"S=\{2;3\}"):
            self.assertEqual(verifier_reponse(self.ENS, texte).statut, "correct", texte)
        self.assertEqual(verifier_reponse(self.ENS, "x=2").statut, "incorrect")
        self.assertEqual(verifier_reponse({"type": "ensemble", "valeurs": []}, "aucune solution").statut, "correct")
        self.assertEqual(verifier_reponse({"type": "ensemble", "valeurs": []}, "x=1").statut, "incorrect")

    def test_forme_a_obtenir(self):
        attendu = {"type": "expression", "valeur": "(x-2)(x-3)", "depart": "x^2-5x+6"}
        self.assertEqual(verifier_reponse(attendu, "(x-3)(x-2)").statut, "correct")
        recopie = verifier_reponse(attendu, "x^2-5x+6")
        self.assertEqual(recopie.statut, "incorrect")
        self.assertIn("recopié", recopie.diagnostic)

    def test_pas_de_reference_pas_de_verdict(self):
        self.assertEqual(verifier_reponse(None, "x").statut, "non_verifiable")

    def test_aucune_execution_de_code(self):
        for hostile in ("__import__('os').system('calc')", "open('x')", "lambda: 1", "exec('1')", "x" * 5000):
            self.assertEqual(verifier_reponse(self.EXPR, hostile).statut, "non_verifiable", hostile[:20])
        for module in (reponses, seance, plan, tour, fuite, ia):
            source = inspect.getsource(module)
            for interdit in ("eval(", "exec(", "sympify(", "parse_expr(", "subprocess", "os.system", "__import__"):
                self.assertNotIn(interdit, source, f"{module.__name__}: {interdit}")


class FuiteTests(SimpleTestCase):
    def test_detection(self):
        expr = {"type": "expression", "valeur": "3x^2-3"}
        self.assertTrue(fuite.contient_la_reponse("La réponse est $3x^2 - 3$.", expr))
        self.assertTrue(fuite.contient_la_reponse("donc f'(x)=3x²−3", expr))
        self.assertFalse(fuite.contient_la_reponse("Dérive $x^3$ puis $-3x$.", expr))
        ens = {"type": "ensemble", "valeurs": ["-1", "1"]}
        self.assertTrue(fuite.contient_la_reponse("Les solutions sont x = -1 et x = 1", ens))
        self.assertTrue(fuite.contient_la_reponse("S = {-1 ; 1}", ens))
        self.assertFalse(fuite.contient_la_reponse("Isole $x^2$ puis prends les racines carrées.", ens))
        self.assertFalse(fuite.contient_la_reponse("n'importe quoi", None))

    def test_citer_la_reponse_de_l_eleve_n_est_pas_une_fuite(self):
        attendu = {"type": "expression", "valeur": "3x^2"}
        message = "Ton résultat $3x^2 + 3$ a le bon terme en $x^2$, mais vérifie le signe de la constante."
        self.assertTrue(fuite.contient_la_reponse(message, attendu))  # sans le filtre d'écho : faux positif
        self.assertFalse(fuite.contient_la_reponse(message, attendu, ignorer=["f'(x) = 3x² + 3"]))
        # une vraie divulgation reste bloquée même si l'élève a écrit autre chose
        self.assertTrue(fuite.contient_la_reponse("La dérivée de $x^3$ est $3x^2$.", attendu, ignorer=["f'(x) = 3x² + 3"]))

    def test_les_indices_du_plan_qui_divulguent_sont_remplaces(self):
        brut = copy.deepcopy(PLAN_BRUT)
        etape = brut["questions"][0]["etapes"][0]
        etape["indices"][2] = "Tu obtiens $3x^2 - 3$, c'est fini."
        etape["consigne"] = "Montre que $f'(x) = 3x^2 - 3$."
        questions, resume = plan.preparer_plan(brut)
        e = questions[0]["etapes"][0]
        self.assertEqual(e["indices"][2], plan.INDICES_GENERIQUES[2])
        self.assertEqual(e["consigne"], plan.CONSIGNE_GENERIQUE)
        self.assertEqual(resume["indices_remplaces"], 2)
        self.assertEqual((resume["verifiees"], resume["sans_calcul"]), (2, 1))

    def test_plan_mal_forme_est_assaini(self):
        questions = plan.normaliser_plan({"questions": [
            {"numero": 1, "etapes": [{"consigne": "", "indices": ["a"], "affirmation": {"type": "inconnu"}}, "oups"]}, "x",
            {"etapes": []}]})
        self.assertEqual(len(questions), 1)
        e = questions[0]["etapes"][0]
        self.assertEqual(len(e["indices"]), 3)
        self.assertEqual(e["consigne"], plan.CONSIGNE_GENERIQUE)
        self.assertIsNone(e["affirmation"])

    def test_nombre_d_etapes_borne(self):
        brut = {"questions": [{"numero": str(i), "enonce": "e", "objectif": "o", "etapes": [_etape("c", ["1", "2", "3"], "s", "r")] * 6} for i in range(8)]}
        total = sum(len(q["etapes"]) for q in plan.normaliser_plan(brut))
        self.assertEqual(total, plan.MAX_ETAPES_TOTAL)

    def test_message_qui_pretend_valider(self):
        incorrect = reponses.Verdict("incorrect")
        for texte in ("Ta réponse est correcte !", "C'est juste.", "Oui, bonne réponse"):
            self.assertIn("Je ne peux pas valider", tour.filtrer_fuite(texte, None, incorrect)[0], texte)
        self.assertEqual(tour.filtrer_fuite("Tu as correctement dérivé $x^3$.", None, incorrect)[0], "Tu as correctement dérivé $x^3$.")


class AppelAnthropicTests(SimpleTestCase):
    @override_settings(ANTHROPIC_API_KEY="cle-factice", IA_PROF_TIMEOUT_SECONDES=33)
    def test_requete(self):
        reponse = SimpleNamespace(content=[SimpleNamespace(type="tool_use", name=tour.NOM_OUTIL, input={"message": "ok"})],
                                  stop_reason="tool_use", usage=SimpleNamespace(input_tokens=5, output_tokens=7))
        faux = mock.Mock(); faux.messages.create.return_value = reponse
        with mock.patch("anthropic.Anthropic", return_value=faux) as constructeur:
            brut, usage = ia.appeler_outil(modele="m", systeme="S", outil=tour.OUTIL, message="texte", max_tokens=321, etiquette="tour")
        constructeur.assert_called_once_with(api_key="cle-factice", timeout=33.0, max_retries=0)
        kwargs = faux.messages.create.call_args.kwargs
        self.assertEqual((kwargs["model"], kwargs["max_tokens"], kwargs["system"]), ("m", 321, "S"))
        self.assertEqual(kwargs["tool_choice"], {"type": "tool", "name": tour.NOM_OUTIL})
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "texte"}])
        self.assertEqual((brut, usage), ({"message": "ok"}, {"tokens_entree": 5, "tokens_sortie": 7}))

    @override_settings(ANTHROPIC_API_KEY="")
    def test_cle_absente(self):
        with mock.patch("anthropic.Anthropic") as constructeur:
            with self.assertRaises(IAConfigurationInvalide):
                ia.appeler_outil(modele="m", systeme="S", outil=tour.OUTIL, message="t", max_tokens=1, etiquette="tour")
        constructeur.assert_not_called()

    def test_le_prompt_du_plan_est_du_texte_seul(self):
        message = plan.construire_message({"enonce": "e", "donnees": [], "formules": [], "questions": [{"numero": "1", "texte": "q"}], "tableaux": [], "figures": []}, "Mathématiques, Terminale C")
        self.assertIn("<enonce_confirme>", message)
        self.assertNotIn("base64", message)
        self.assertTrue(re.search(r"EXACTEMENT 3", plan.SYSTEME))
