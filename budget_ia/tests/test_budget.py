"""
Tests du contrôle budgétaire (tarifs, quotas, fuseau, réservation, réconciliation, alertes).
AUCUN appel Anthropic réel : ni réseau ni clé.
"""

import base64
from datetime import datetime, timezone as fuseau_utc
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from budget_ia import service as budget
from budget_ia import tarifs
from budget_ia.models import AlerteBudgetIA, BudgetMensuel, OperationIA
from budget_ia.tests.outils import TARIFS_TEST, creer_eleve, faux_client, fcfa
from programme import lecture_exercice as lecture
from programme.ia.exceptions import (
    BudgetEpuise, IADesactivee, LimiteExerciceAtteinte, LimiteInteractionsAtteinte, LimiteJourAtteinte,
    OperationDejaEnCours, RefusBudget,
)

S = OperationIA.Statut
PETIT = dict(modele="m", tokens_entree=1000, tokens_sortie_max=1000)   # coût max : 12 000 / 1e6 $ x 600 x 1,10 = 7,92 FCFA


def ouvrir(fonction="lecture", **kw):
    return budget.ouvrir(fonctionnalite=fonction, **{**PETIT, **kw})


def instant(annee, mois, jour, h=12, mn=0):
    return datetime(annee, mois, jour, h, mn, tzinfo=fuseau_utc.utc)


@override_settings(IA_TARIFS_USD=TARIFS_TEST, BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=90000)
class BaseBudget(TestCase):
    def setUp(self):
        self.eleve = creer_eleve()

    def ctx(self, exercice="ex", requete=""):
        return budget.contexte(utilisateur_id=self.eleve.id, exercice_cle=exercice, cle_requete=requete)


class TarifsTests(BaseBudget):
    def test_cout_calcule_avec_tarif_taux_et_marge(self):
        usd = tarifs.cout_usd("m", entree=1000, sortie=500)   # 1000 x 2 $/M + 500 x 10 $/M
        self.assertEqual(usd, Decimal("0.007"))
        self.assertEqual(tarifs.usd_vers_fcfa(usd), fcfa(2, 1000, 10, 500))

    def test_cache_pris_en_compte(self):
        usd = tarifs.cout_usd("m", entree=0, sortie=0, cache_ecriture=1_000_000, cache_lecture=1_000_000)
        self.assertEqual(usd, Decimal("2.7"))   # 2,50 + 0,20

    @override_settings(IA_TAUX_USD_FCFA="650", IA_MARGE_SECURITE="0.20")
    def test_taux_et_marge_configurables(self):
        self.assertEqual(tarifs.usd_vers_fcfa(Decimal(1)), Decimal("780.0000"))

    def test_tarifs_officiels_par_defaut(self):
        defaut = tarifs.TARIFS_PAR_DEFAUT
        self.assertEqual((defaut["claude-sonnet-5"]["entree"], defaut["claude-sonnet-5"]["sortie"]), ("2", "10"))
        self.assertEqual(defaut["claude-sonnet-5-5"]["cache_lecture"], "0.1")

    def test_modele_sans_tarif_refuse_avant_tout_appel(self):
        client = faux_client()
        with self.ctx(), mock.patch("anthropic.Anthropic", return_value=client):
            with self.assertRaises(tarifs.ModeleNonTarife):
                ouvrir(modele="modele-inconnu")
        client.messages.create.assert_not_called()
        self.assertEqual(OperationIA.objects.count(), 0)


class QuotasTests(BaseBudget):
    def test_quota_journalier_trois_exercices(self):
        for i in range(3):
            with self.ctx(f"ex{i}"):
                budget.terminer(ouvrir(), {"tokens_entree": 10, "tokens_sortie": 10})
        with self.ctx("ex3"), self.assertRaises(LimiteJourAtteinte):
            ouvrir()

    def test_les_etapes_d_un_meme_exercice_ne_comptent_qu_une_fois(self):
        for i in range(2):
            with self.ctx(f"ex{i}"):
                budget.terminer(ouvrir(), None)
        with self.ctx("ex2"):
            for fonction in ("lecture", "correction", "professeur_plan", "professeur_tour"):
                budget.terminer(ouvrir(fonction), None)   # 4 étapes, 1 seul exercice : il reste le 3e du jour
        with self.ctx("ex2"):
            budget.terminer(ouvrir("professeur_tour"), None)

    def test_quota_journalier_reglable_sans_code(self):
        with override_settings(IA_EXERCICES_PAR_JOUR=1):
            with self.ctx("a"):
                budget.terminer(ouvrir(), None)
            with self.ctx("b"), self.assertRaises(LimiteJourAtteinte):
                ouvrir()

    def test_quota_par_eleve_pas_global(self):
        autre = creer_eleve("+22790000098")
        for i in range(3):
            with self.ctx(f"ex{i}"):
                budget.terminer(ouvrir(), None)
        with budget.contexte(utilisateur_id=autre.id, exercice_cle="x"):
            budget.terminer(ouvrir(), None)

    def test_dix_interactions_fahimta_ai_par_exercice(self):
        with self.ctx():
            for _ in range(10):
                budget.terminer(ouvrir("professeur_tour"), None)
            with self.assertRaises(LimiteInteractionsAtteinte):
                ouvrir("professeur_tour")

    def test_renouvellement_de_seance_ne_remet_pas_le_compteur_a_zero(self):
        for i in range(10):   # séances successives : même exercice_cle (clé de l'exercice, pas de la séance)
            with self.ctx("ex", requete=f"seance-{i % 2}"):
                budget.terminer(ouvrir("professeur_tour"), None)
        with self.ctx("ex", requete="seance-nouvelle"), self.assertRaises(LimiteInteractionsAtteinte):
            ouvrir("professeur_tour")

    def test_relectures_corrections_et_plans_bornes_par_exercice(self):
        with self.ctx():
            for fonction, maximum in (("lecture", 3), ("correction", 2), ("professeur_plan", 2)):
                for _ in range(maximum):
                    budget.terminer(ouvrir(fonction), None)
                with self.assertRaises(LimiteExerciceAtteinte):
                    ouvrir(fonction)

    def test_tentative_echouee_ne_consomme_ni_exercice_ni_interaction(self):
        for i in range(5):   # 5 refus fournisseur « propres » sur 5 exercices différents
            with self.ctx(f"ex{i}"):
                budget.echouer(ouvrir(), "RateLimitError", resultat_inconnu=False)
        with self.ctx("ex-ok"):
            budget.terminer(ouvrir(), None)   # le quota du jour est intact

    def test_resultat_inconnu_consomme_le_quota_par_prudence(self):
        with override_settings(IA_EXERCICES_PAR_JOUR=1):
            with self.ctx("a"):
                budget.echouer(ouvrir(), "APITimeoutError", resultat_inconnu=True)
            with self.ctx("b"), self.assertRaises(LimiteJourAtteinte):
                ouvrir()

    def test_double_clic_ou_retry_simultane_refuse(self):
        with self.ctx("ex", requete="req-1"):
            op = ouvrir()
            with self.assertRaises(OperationDejaEnCours):
                ouvrir()                    # même requête encore en cours
            budget.terminer(op, None)
            ouvrir()                        # une fois soldée, un nouvel essai est possible

    def test_appel_sans_contexte_est_refuse_ferme_par_defaut(self):
        with self.assertRaises(Exception) as cm:
            ouvrir()
        self.assertNotIsInstance(cm.exception, RefusBudget)   # erreur de configuration, pas un quota
        self.assertEqual(OperationIA.objects.count(), 0)


class FuseauEtMoisTests(BaseBudget):
    def test_jour_calcule_en_africa_niamey_pas_en_utc(self):
        mois, jour = budget.mois_et_jour(instant(2026, 11, 30, 23, 30))   # 00:30 le 1er décembre à Niamey (UTC+1)
        self.assertEqual((mois, jour.isoformat()), ("2026-12", "2026-12-01"))
        mois, jour = budget.mois_et_jour(instant(2026, 11, 30, 22, 30))   # 23:30 à Niamey : encore novembre
        self.assertEqual((mois, jour.isoformat()), ("2026-11", "2026-11-30"))

    def test_le_quota_du_jour_repart_a_zero_a_minuit_niamey(self):
        with override_settings(IA_EXERCICES_PAR_JOUR=1):
            with mock.patch("django.utils.timezone.now", return_value=instant(2026, 11, 10, 22, 30)):   # 23:30 Niamey
                with self.ctx("a"):
                    budget.terminer(ouvrir(), None)
                with self.ctx("b"), self.assertRaises(LimiteJourAtteinte):
                    ouvrir()
            with mock.patch("django.utils.timezone.now", return_value=instant(2026, 11, 10, 23, 30)):   # 00:30, jour suivant
                with self.ctx("b"):
                    budget.terminer(ouvrir(), None)

    def test_changement_de_mois_nouveau_budget(self):
        with override_settings(BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=10):   # une seule opération (7,92) par mois
            with mock.patch("django.utils.timezone.now", return_value=instant(2026, 11, 15)):
                with self.ctx("a"):
                    budget.terminer(ouvrir(), {"tokens_entree": 1000, "tokens_sortie": 1000})
                    with self.assertRaises(BudgetEpuise):
                        ouvrir()
            with mock.patch("django.utils.timezone.now", return_value=instant(2026, 12, 2)):
                with self.ctx("a"):
                    budget.terminer(ouvrir(), None)   # décembre : compteur neuf
        self.assertEqual(sorted(BudgetMensuel.objects.values_list("mois", flat=True)), ["2026-11", "2026-12"])


class ReservationTests(BaseBudget):
    def test_reservation_puis_cout_reel(self):
        with self.ctx():
            op = ouvrir()
        b = BudgetMensuel.objects.get()
        self.assertEqual(op.cout_reserve_fcfa, fcfa(2, 1000, 10, 1000))
        self.assertEqual((b.reserve_fcfa, b.depense_fcfa), (op.cout_reserve_fcfa, 0))
        budget.terminer(op, {"tokens_entree": 800, "tokens_sortie": 200})
        b.refresh_from_db()
        op.refresh_from_db()
        self.assertEqual(b.reserve_fcfa, 0)
        self.assertEqual(b.depense_fcfa, fcfa(2, 800, 10, 200))
        self.assertTrue(op.consommation_connue)
        self.assertEqual((op.tokens_entree, op.tokens_sortie, op.statut), (800, 200, S.TERMINEE))

    def test_solder_plusieurs_fois_ne_compte_qu_une_fois(self):
        with self.ctx():
            op = ouvrir()
        budget.terminer(op, {"tokens_entree": 100, "tokens_sortie": 100})
        budget.terminer(op, {"tokens_entree": 999999, "tokens_sortie": 999999})
        budget.echouer(op, "X", resultat_inconnu=True)
        self.assertEqual(BudgetMensuel.objects.get().depense_fcfa, fcfa(2, 100, 10, 100))

    def test_reponse_sans_information_de_consommation_compte_la_reservation(self):
        with self.ctx():
            op = ouvrir()
        budget.terminer(op, None)
        op.refresh_from_db()
        self.assertFalse(op.consommation_connue)
        self.assertEqual(BudgetMensuel.objects.get().depense_fcfa, op.cout_reserve_fcfa)

    def test_erreur_fournisseur_libere_la_reservation(self):
        with self.ctx():
            op = ouvrir()
        budget.echouer(op, "RateLimitError", resultat_inconnu=False)
        b = BudgetMensuel.objects.get()
        op.refresh_from_db()
        self.assertEqual((b.reserve_fcfa, b.depense_fcfa, op.statut), (0, 0, S.ECHOUEE))

    def test_timeout_garde_le_cout_reserve_a_reconcilier(self):
        with self.ctx():
            op = ouvrir()
        budget.echouer(op, "APITimeoutError", resultat_inconnu=True)
        b = BudgetMensuel.objects.get()
        op.refresh_from_db()
        self.assertEqual((b.reserve_fcfa, op.statut), (0, S.INCONNUE))
        self.assertEqual(b.depense_fcfa, op.cout_reserve_fcfa)

    def test_reservation_abandonnee_devient_inconnue(self):
        with self.ctx():
            op = ouvrir()
        with mock.patch("django.utils.timezone.now", return_value=op.cree_le.replace(year=op.cree_le.year + 1)):
            self.assertEqual(budget.reconcilier_abandonnees(), 1)
        op.refresh_from_db()
        self.assertEqual((op.statut, op.code_erreur), (S.INCONNUE, "abandonnee"))
        b = BudgetMensuel.objects.get()
        self.assertEqual((b.reserve_fcfa, b.depense_fcfa), (0, op.cout_reserve_fcfa))

    def test_cout_maximal_couvre_le_pire_cas_de_sortie(self):
        with self.ctx():
            op = ouvrir(tokens_entree=1000, tokens_sortie_max=4000)
        self.assertEqual(op.cout_reserve_fcfa, fcfa(2, 1000, 10, 4000))   # tous les tokens de sortie autorisés produits

    def test_estimation_d_entree_images_pdf_et_texte(self):
        pdf = base64.b64encode(b"/Type /Page\n/Type /Page\n/Type /Pages").decode()
        blocs = [{"type": "text", "text": "x" * 250}, {"type": "image", "source": {}}, {"type": "document", "source": {"data": pdf}}]
        # fixes 1500 + texte 100 + image (réglage) + PDF : 2 pages (« /Pages » ignoré) x 3500
        self.assertEqual(budget.estimer_entree(blocs=blocs), 1500 + 100 + 5000 + 2 * 3500)

    def test_cout_reel_superieur_a_la_reservation_compte_en_entier_et_est_signale(self):
        from budget_ia.rapport import rapport_mensuel
        with self.ctx():
            op = ouvrir(tokens_entree=100, tokens_sortie_max=100)           # réservation volontairement trop petite
        petit = op.cout_reserve_fcfa
        budget.terminer(op, {"tokens_entree": 100_000, "tokens_sortie": 50_000})   # réel : bien plus
        reel = fcfa(2, 100_000, 10, 50_000)
        b = BudgetMensuel.objects.get()
        self.assertEqual((b.reserve_fcfa, b.depense_fcfa), (0, reel))      # le réel est compté ENTIÈREMENT
        self.assertAlmostEqual(rapport_mensuel()["depassement_estimation_fcfa"], float(reel - petit), places=3)
        with override_settings(BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=int(reel) + 1), self.ctx("autre"):
            with self.assertRaises(BudgetEpuise):                           # et il pèse sur les opérations suivantes
                ouvrir(tokens_entree=100_000, tokens_sortie_max=10_000)


class AlertesEtBlocageTests(BaseBudget):
    @override_settings(BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=97)
    def test_alertes_une_seule_fois_puis_blocage_a_100(self):
        with self.ctx():
            for _ in range(10):   # 10 x 9,24 = 92,4 FCFA sur un plafond de 97 : franchit 80 % et 95 % sans le dépasser
                budget.terminer(ouvrir("professeur_tour", tokens_entree=2000, tokens_sortie_max=1000), None)
        self.assertEqual(sorted(AlerteBudgetIA.objects.values_list("seuil", flat=True)), [80, 95])   # une fois chacun
        with self.ctx("ex2"):
            for _ in range(2):
                with self.assertRaises(BudgetEpuise):
                    ouvrir(tokens_entree=2000, tokens_sortie_max=1000)
        self.assertEqual(AlerteBudgetIA.objects.filter(seuil=100).count(), 1)   # refus répétés : une seule alerte 100 %

    def test_interrupteur_global_coupe_tout(self):
        client = faux_client()
        with override_settings(IA_INTERRUPTEUR_GLOBAL=False), mock.patch("anthropic.Anthropic", return_value=client):
            with self.ctx(), self.assertRaises(IADesactivee):
                ouvrir()
            self.assertFalse(lecture.lecture_activee())
        client.messages.create.assert_not_called()

    def test_le_blocage_s_applique_aux_fonctions_ia_et_au_contenu_admin(self):
        BudgetMensuel.objects.create(mois=budget.mois_et_jour()[0], depense_fcfa=Decimal("89999.9"))
        with self.ctx():
            for fonction in ("lecture", "correction", "professeur_plan", "professeur_tour"):
                with self.assertRaises(BudgetEpuise):
                    ouvrir(fonction)
        with self.assertRaises(BudgetEpuise):
            ouvrir("contenu_admin")


class AnalyseEtExerciceTests(BaseBudget):
    ANALYSE = {"enonce": "e", "donnees": [], "formules": [], "questions": [{"numero": "1", "texte": "q"}], "tableaux": [], "figures": []}

    def test_l_analyse_lue_est_rattachee_a_son_exercice(self):
        with self.ctx("depot-1") as ctx:
            budget.terminer(ouvrir(), None)
            ctx.associer_analyse(self.ANALYSE)
        self.assertEqual(budget.resoudre_exercice(self.eleve.id, budget.empreinte_analyse(self.ANALYSE)), "depot-1")
        inconnue = {**self.ANALYSE, "enonce": "autre"}   # une analyse inconnue forme un NOUVEL exercice
        self.assertEqual(budget.resoudre_exercice(self.eleve.id, budget.empreinte_analyse(inconnue)), budget.empreinte_analyse(inconnue))
        autre = creer_eleve("+22790000097")   # et un autre élève ne peut pas se rattacher à cet exercice
        self.assertNotEqual(budget.resoudre_exercice(autre.id, budget.empreinte_analyse(self.ANALYSE)), "depot-1")

    def test_normalisation_idempotente_l_empreinte_ne_change_pas(self):
        from programme.lecture_exercice import ContexteProgramme, normaliser_analyse
        ctx = ContexteProgramme(matiere="Mathématiques", classe="Terminale C")
        brute = {"lisible": True, "matiere": {"valeur": "mathematiques", "confiance": "haute"},
                 "niveau": {"valeur": "Terminale C", "confiance": "haute"}, "enonce": "Résoudre x^2=4", "donnees": [], "formules": [],
                 "questions": [{"numero": "1", "texte": "Résoudre", "incertain": False}], "figures": [], "tableaux": [],
                 "parties_incertaines": [], "remarques": [], "concordance_programme": "concorde"}
        une = normaliser_analyse(brute, ctx)
        self.assertEqual(budget.empreinte_analyse(une), budget.empreinte_analyse(normaliser_analyse(une, ctx)))

    def test_depot_identique_meme_exercice(self):
        a = budget.empreinte_depot(1, 2, [b"img"], "texte")
        self.assertEqual(a, budget.empreinte_depot(1, 2, [b"img"], "texte"))
        self.assertNotEqual(a, budget.empreinte_depot(1, 2, [b"autre"], "texte"))
        self.assertNotEqual(a, budget.empreinte_depot(9, 2, [b"img"], "texte"))   # autre élève : autre exercice
