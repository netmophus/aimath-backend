"""
Liste blanche de comptes (mode pilote) : seuls les comptes listés peuvent utiliser les fonctions IA, de la soumission
au worker. Fournisseurs SIMULÉS (faux SDK qui compte ses appels) : aucun appel Anthropic payant.
"""

from unittest import mock

from django.test import override_settings
from rest_framework.test import APIClient

from budget_ia import acces
from budget_ia import service as budget
from budget_ia.models import OperationIA
from budget_ia.rapport import rapport_mensuel
from budget_ia.tests.outils import creer_eleve
from comptes.models import User
from programme import lecture_exercice as lecture
from programme.correction import resolution
from programme.correction.service import correction_activee
from programme.ia.exceptions import IANonAutorisee
from programme.professeur import plan as plan_module
from programme.professeur import tour
from programme.professeur.seance import professeur_actif
from programme.test_correction_exercice import CORRECTION_EX1
from traitement_ia.models import TacheIA
from traitement_ia.tests.test_taches import ANALYSE, REGLAGES, BaseAsync, faux_sdk, traiter_tout

TEL_LISTE = "+22790000055"      # l'élève créé par BaseAsync


@override_settings(**REGLAGES)
class RegleDAccesTests(BaseAsync):
    def autre(self, tel="+22790000077"):
        return creer_eleve(tel, niveau=self.programme.niveau, serie=self.programme.serie)

    def test_liste_vide_comportement_historique_inchange(self):
        for dev, debug, attendu in ((True, False, False), (False, False, True), (True, True, True)):
            with override_settings(IA_COMPTES_AUTORISES=[], IA_LECTURE_DEV_SEULEMENT=dev, DEBUG=debug):
                self.assertEqual(lecture.lecture_activee(self.eleve.id), attendu)
                self.assertEqual(lecture.lecture_activee(), attendu)       # appel sans identité, comme avant
                self.assertFalse(acces.mode_pilote())

    def test_mode_pilote_ouvre_les_comptes_listes_meme_sans_debug_ni_dev_seulement(self):
        autre = self.autre()
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE], IA_LECTURE_DEV_SEULEMENT=True, IA_CORRECTION_DEV_SEULEMENT=True,
                               IA_PROF_DEV_SEULEMENT=True, DEBUG=False):
            self.assertTrue(acces.mode_pilote())
            for porte in (lecture.lecture_activee, correction_activee, professeur_actif):
                self.assertTrue(porte(self.eleve.id), porte.__name__)
                self.assertFalse(porte(autre.id), porte.__name__)           # autre élève : fermé
                self.assertFalse(porte(None), porte.__name__)               # sans identité : fermé
                self.assertFalse(porte(), porte.__name__)

    def test_les_drapeaux_et_l_interrupteur_restent_necessaires(self):
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
            with override_settings(IA_LECTURE_ACTIVE=False):
                self.assertFalse(lecture.lecture_activee(self.eleve.id))
            with override_settings(IA_INTERRUPTEUR_GLOBAL=False):
                self.assertFalse(correction_activee(self.eleve.id))
            with override_settings(IA_PROF_ACTIVE=False):
                self.assertFalse(professeur_actif(self.eleve.id))

    def test_liste_inexistante_ou_mal_saisie_n_ouvre_a_personne(self):
        with override_settings(IA_COMPTES_AUTORISES=["+22700000000", "n'importe quoi"]):
            self.assertTrue(acces.mode_pilote())
            for porte in (lecture.lecture_activee, correction_activee, professeur_actif):
                self.assertFalse(porte(self.eleve.id))

    def test_normalisation_des_numeros_comme_a_l_inscription(self):
        with override_settings(IA_COMPTES_AUTORISES=[" +227 90 00 00 55 "]):
            self.assertEqual(acces.comptes_autorises(), frozenset({TEL_LISTE}))
            self.assertTrue(lecture.lecture_activee(self.eleve.id))

    def test_compte_inactif_ou_non_eleve_refuse_meme_liste(self):
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
            User.objects.filter(pk=self.eleve.pk).update(is_active=False)
            self.assertFalse(lecture.lecture_activee(self.eleve.id))
            User.objects.filter(pk=self.eleve.pk).update(is_active=True, role=User.Role.ADMIN)
            self.assertFalse(lecture.lecture_activee(self.eleve.id))

    def test_variable_d_environnement_lue_comme_une_liste(self):
        import importlib
        import os
        from config import settings as reglages
        with mock.patch.dict(os.environ, {"IA_COMPTES_AUTORISES": "+22790000055, +227 90 00 00 66 ,,"}):
            importlib.reload(reglages)
            lue = reglages.IA_COMPTES_AUTORISES
        importlib.reload(reglages)          # hors du patch : retour au défaut
        self.assertEqual(lue, ["+22790000055", "+22790000066"])
        self.assertEqual(reglages.IA_COMPTES_AUTORISES, [])     # défaut : vide


@override_settings(**REGLAGES)
class VuesEnModePiloteTests(BaseAsync):
    def setUp(self):
        super().setUp()
        self.autre = creer_eleve("+22790000077", niveau=self.programme.niveau, serie=self.programme.serie)
        self.api_autre = APIClient()
        self.api_autre.force_authenticate(self.autre)

    def deposer_par(self, api, texte="Résoudre x^2 - 5x + 6 = 0 dans R."):
        return api.post("/api/eleve/resoudre/", {"programme": self.programme.id, "mode": "correction", "enonce": texte, "analyser": "true"}, format="multipart")

    def test_un_eleve_non_liste_n_a_aucune_fonction_ia_ni_tache_ni_appel(self):
        client = faux_sdk(analyse=ANALYSE, correction=CORRECTION_EX1)
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]), mock.patch("anthropic.Anthropic", return_value=client):
            r = self.deposer_par(self.api_autre)
            self.assertEqual(r.status_code, 200, r.content)            # dépôt simple, synchrone, sans IA
            corps = r.json()
            self.assertEqual((corps["analyse_disponible"], corps["correction_disponible"], corps["professeur_disponible"], corps["analysee"]),
                             (False, False, False, False))
            c = self.api_autre.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": ANALYSE}, format="json")
            self.assertEqual((c.status_code, c.json()["code"]), (503, "correction_desactivee"))
            p = self.api_autre.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": ANALYSE}, format="json")
            self.assertEqual((p.status_code, p.json()["code"]), (503, "professeur_desactive"))
            self.assertEqual(traiter_tout(), 0)
        self.assertEqual(client.appels, [])
        self.assertEqual((TacheIA.objects.count(), OperationIA.objects.count()), (0, 0))

    def test_chaine_complete_pour_un_compte_liste_202_worker_consultation(self):
        client = faux_sdk(analyse=ANALYSE, correction=CORRECTION_EX1)
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]), mock.patch("anthropic.Anthropic", return_value=client):
            lect = self.tache(self.deposer_par(self.api))
            self.assertEqual(client.appels, [])                        # la requête web n'attend jamais l'IA
            traiter_tout()
            e = self.etat(lect)
            self.assertEqual((e["statut"], e["http"], e["corps"]["analysee"]), ("terminee", 200, True))
            self.assertTrue(e["corps"]["correction_disponible"] and e["corps"]["professeur_disponible"])
            analyse = e["corps"]["analyse"]

            corr = self.api.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": analyse}, format="json")
            corr = self.tache(corr)
            traiter_tout()
            self.assertEqual(self.etat(corr)["http"], 200)

            sea = self.tache(self.api.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": analyse}, format="json"))
            traiter_tout()
            vue = self.etat(sea)["corps"]["seance"]
            exp = self.tache(self.api.post(f"/api/eleve/professeur/seances/{vue['seance']}/explication/",
                                           {"version": vue["version"], "type": "exemple"}, format="json"))
            traiter_tout()
            self.assertEqual(self.etat(exp)["http"], 200)

        self.assertEqual(client.appels.count(lecture.NOM_OUTIL), 1)
        self.assertEqual(client.appels.count(resolution.NOM_OUTIL), 1)
        self.assertEqual(client.appels.count(plan_module.NOM_OUTIL), 1)
        self.assertEqual(client.appels.count(tour.NOM_OUTIL), 1)
        self.assertEqual(set(OperationIA.objects.values_list("utilisateur_id", flat=True)), {self.eleve.id})   # que le compte listé

    def test_les_quotas_restent_appliques_au_compte_liste(self):
        client = faux_sdk(analyse=ANALYSE)
        codes = []
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE], IA_EXERCICES_PAR_JOUR=3), mock.patch("anthropic.Anthropic", return_value=client):
            for i in range(4):
                t = self.tache(self.deposer_par(self.api, f"Exercice numéro {i} : résoudre x^2 = {i + 1}."))
                traiter_tout()
                codes.append(self.etat(t)["http"])
        self.assertEqual(codes, [200, 200, 200, 429])                  # 4e exercice du jour refusé
        self.assertEqual(len(client.appels), 3)

    def test_le_budget_reste_applique_au_compte_liste(self):
        client = faux_sdk(analyse=ANALYSE)
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE], BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=1), mock.patch("anthropic.Anthropic", return_value=client):
            t = self.tache(self.deposer_par(self.api))
            traiter_tout()
            e = self.etat(t)
        self.assertEqual((e["http"], e["corps"]["code"]), (503, "budget_epuise"))
        self.assertEqual(client.appels, [])

    def test_retrait_de_la_liste_apres_la_mise_en_file_aucun_appel(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
                t = self.tache(self.deposer_par(self.api))
            with override_settings(IA_COMPTES_AUTORISES=["+22790000077"]):    # le compte est retiré avant le passage du worker
                traiter_tout()
            e = self.etat(t)
        # Retiré avant le passage du worker : refus explicite (détail dans test_liste_blanche_retrait).
        self.assertEqual((e["statut"], e["http"], e["corps"]["code"]), ("terminee", 503, "ia_non_autorisee"))
        self.assertEqual(e["corps"]["detail"], "Service IA indisponible.")
        self.assertEqual(client.appels, [])
        self.assertEqual(OperationIA.objects.count(), 0)

    def test_verrou_central_ouvrir_refuse_un_compte_non_liste_meme_si_une_vue_l_oubliait(self):
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
            with budget.contexte(utilisateur_id=self.autre.id, exercice_cle="x"):
                with self.assertRaises(IANonAutorisee):
                    budget.ouvrir(fonctionnalite="lecture", modele="m", tokens_entree=1000, tokens_sortie_max=1000)
            with budget.contexte(utilisateur_id=self.eleve.id, exercice_cle="x"):
                op = budget.ouvrir(fonctionnalite="lecture", modele="m", tokens_entree=1000, tokens_sortie_max=1000)
                self.assertEqual(op.utilisateur_id, self.eleve.id)
        self.assertEqual(OperationIA.objects.filter(utilisateur_id=self.autre.id).count(), 0)

    def test_rapport_admin_expose_le_nombre_de_comptes_jamais_les_numeros(self):
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE, "+22790000077"]):
            r = rapport_mensuel()
        self.assertEqual((r["mode_pilote"], r["comptes_autorises"]), (True, 2))
        self.assertNotIn("+2279000", str(r))
        with override_settings(IA_COMPTES_AUTORISES=[]):
            r = rapport_mensuel()
        self.assertEqual((r["mode_pilote"], r["comptes_autorises"]), (False, 0))
