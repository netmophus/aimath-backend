"""
Liste blanche : compte retiré (ou devenu inactif) APRÈS la mise en file, et validation stricte des numéros.
Fournisseurs SIMULÉS (faux SDK qui compte ses appels) : aucun appel Anthropic payant.
"""

from datetime import timedelta
from unittest import mock

from django.core.checks import run_checks
from django.test import override_settings
from django.utils import timezone

from budget_ia import acces
from budget_ia import service as budget
from budget_ia.models import BudgetMensuel, OperationIA
from budget_ia.rapport import rapport_mensuel
from budget_ia.tests.outils import creer_eleve
from comptes.models import User
from programme import lecture_exercice as lecture
from programme.correction.service import correction_activee
from programme.ia.exceptions import IANonAutorisee
from programme.professeur.seance import professeur_actif
from programme.test_correction_exercice import CORRECTION_EX1
from traitement_ia import service
from traitement_ia.models import TacheIA
from traitement_ia.tests.test_taches import ANALYSE, REGLAGES, BaseAsync, faux_sdk, traiter_tout

TEL_LISTE = "+22790000055"      # l'élève créé par BaseAsync
AUTRE = ["+22790000077"]        # liste qui ne contient plus ce compte


@override_settings(**REGLAGES)
class RetraitPendantLAttenteTests(BaseAsync):
    """Refus explicite par le worker, sans appel fournisseur, sans opération (donc sans quota), sans tâche bloquée."""

    def verifier_refus(self, tache):
        e = self.etat(tache)
        self.assertEqual((e["statut"], e["http"]), ("terminee", 503), e)
        self.assertEqual((e["corps"]["detail"], e["corps"]["code"]), ("Service IA indisponible.", "ia_non_autorisee"))

    def test_lecture_correction_et_seance_refusees_explicitement_sans_appel_ni_operation(self):
        client = faux_sdk(analyse=ANALYSE, correction=CORRECTION_EX1)
        with mock.patch("anthropic.Anthropic", return_value=client):
            with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
                lect = self.tache(self.deposer())
                corr = self.tache(self.api.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": ANALYSE}, format="json"))
                sea = self.tache(self.api.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": ANALYSE}, format="json"))
            with override_settings(IA_COMPTES_AUTORISES=AUTRE):
                self.assertEqual(traiter_tout(), 3)
        for t in (lect, corr, sea):
            self.verifier_refus(t)
        self.assertEqual(client.messages.create.call_count, 0)
        self.assertEqual(OperationIA.objects.count(), 0)
        self.assertFalse(TacheIA.objects.filter(statut__in=("en_attente", "en_cours")).exists())   # aucune tâche bloquée

    def test_action_de_seance_refusee_apres_retrait(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
                sea = self.tache(self.api.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": ANALYSE}, format="json"))
                traiter_tout()
                vue = self.etat(sea)["corps"]["seance"]
                appels = len(client.appels)
                exp = self.tache(self.api.post(f"/api/eleve/professeur/seances/{vue['seance']}/explication/",
                                               {"version": vue["version"], "type": "exemple"}, format="json"))
            with override_settings(IA_COMPTES_AUTORISES=AUTRE):
                traiter_tout()
        self.verifier_refus(exp)
        self.assertEqual(len(client.appels), appels)       # aucun tour supplémentaire

    def test_une_tache_refusee_ne_consomme_aucun_quota(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
                refusee = self.tache(self.deposer("Exercice refusé : résoudre x^2 = 9."))
            with override_settings(IA_COMPTES_AUTORISES=AUTRE):
                traiter_tout()
            self.verifier_refus(refusee)
            codes = []
            with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE], IA_EXERCICES_PAR_JOUR=3):   # le compte est rétabli
                for i in range(3):
                    t = self.tache(self.deposer(f"Exercice {i} : résoudre x^2 = {i + 1}."))
                    traiter_tout()
                    codes.append(self.etat(t)["http"])
        self.assertEqual(codes, [200, 200, 200])          # les 3 exercices du jour sont tous disponibles
        self.assertEqual(len(client.appels), 3)

    def test_les_operations_deja_ouvertes_sont_preservees(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client), override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
            tache = self.tache(self.deposer())
            t = service.reclamer("A")
            with budget.tache(t.id, reprise=False), budget.contexte(utilisateur_id=self.eleve.id, exercice_cle="x"):
                op = budget.ouvrir(fonctionnalite="lecture", modele="m", tokens_entree=1000, tokens_sortie_max=1000)   # appel parti, worker mort
            reserve = BudgetMensuel.objects.get().reserve_fcfa
            TacheIA.objects.filter(pk=tache.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))
            with override_settings(IA_COMPTES_AUTORISES=AUTRE):
                traiter_tout("B")
        self.verifier_refus(tache)
        op.refresh_from_db()
        self.assertEqual((OperationIA.objects.count(), op.statut, op.tache_id), (1, "reservee", t.id))   # toujours comptée
        self.assertGreater(reserve, 0)
        self.assertEqual(BudgetMensuel.objects.get().reserve_fcfa, reserve)
        self.assertEqual(client.messages.create.call_count, 0)

    def test_compte_devenu_inactif_apres_la_mise_en_file(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client), override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
            tache = self.tache(self.deposer())
            User.objects.filter(pk=self.eleve.pk).update(is_active=False)
            traiter_tout()
        self.verifier_refus(tache)
        self.assertEqual((client.messages.create.call_count, OperationIA.objects.count()), (0, 0))

    def test_le_refus_du_service_budgetaire_porte_le_meme_message(self):
        self.assertEqual(IANonAutorisee().args[0], "Service IA indisponible.")
        self.assertEqual((IANonAutorisee.statut_http, IANonAutorisee.code), (503, "ia_non_autorisee"))


@override_settings(**REGLAGES)
class ValidationDesNumerosTests(BaseAsync):
    MAL_FORMES = ["22790000055", "+2279000005", "+227900000551", "+22790000055x", "abc", "+33612345678", "00227 90000055"]

    def test_le_format_est_celui_du_validateur_de_comptes(self):
        from comptes.models import telephone_validator
        self.assertEqual(acces.FORMAT_TELEPHONE.pattern, telephone_validator.regex.pattern)

    def test_numeros_mal_formes_ignores_jamais_corriges(self):
        with override_settings(IA_COMPTES_AUTORISES=self.MAL_FORMES + [TEL_LISTE]):
            self.assertEqual(acces.comptes_autorises(), frozenset({TEL_LISTE}))
            self.assertEqual(acces.entrees_invalides(), len(self.MAL_FORMES))
            self.assertTrue(acces.compte_autorise(self.eleve.id))

    def test_une_liste_uniquement_mal_formee_ferme_tout_meme_si_dev_seulement_est_desactive(self):
        autre = creer_eleve("+22790000066", niveau=self.programme.niveau, serie=self.programme.serie)
        with override_settings(IA_COMPTES_AUTORISES=["22790000055", "abc"], IA_LECTURE_DEV_SEULEMENT=False,
                               IA_CORRECTION_DEV_SEULEMENT=False, IA_PROF_DEV_SEULEMENT=False, DEBUG=False):
            self.assertTrue(acces.mode_pilote())                       # une liste erronée ne revient JAMAIS au mode ouvert
            self.assertEqual(acces.comptes_autorises(), frozenset())
            for u in (self.eleve, autre):
                for porte in (lecture.lecture_activee, correction_activee, professeur_actif):
                    self.assertFalse(porte(u.id))
                self.assertFalse(acces.compte_autorise(u.id))

    def test_avertissement_de_configuration_sans_afficher_les_numeros(self):
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE, "22790000099"]):
            avertissements = [m for m in run_checks() if m.id == "budget_ia.W001"]
        self.assertEqual(len(avertissements), 1)
        texte = avertissements[0].msg + avertissements[0].hint
        self.assertIn("1 entrée", texte)
        self.assertNotIn("2279000", texte)
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE]):
            self.assertEqual([m for m in run_checks() if m.id == "budget_ia.W001"], [])
        with override_settings(IA_COMPTES_AUTORISES=[]):
            self.assertEqual([m for m in run_checks() if m.id == "budget_ia.W001"], [])

    def test_rapport_admin_compte_les_entrees_invalides_sans_les_montrer(self):
        with override_settings(IA_COMPTES_AUTORISES=[TEL_LISTE, "22790000099"]):
            r = rapport_mensuel()
        self.assertEqual((r["comptes_autorises"], r["entrees_invalides"]), (1, 1))
        self.assertNotIn("2279000", str(r))
