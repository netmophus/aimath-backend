"""
Intégration : vrai chemin des appels (SDK remplacé par un faux client qui COMPTE ses appels), vraies vues DRF,
et concurrence réelle (threads, verrous de ligne PostgreSQL). AUCUN appel Anthropic payant.
"""

import threading
from decimal import Decimal
from unittest import mock

try:
    import httpx
except ImportError:  # le SDK Anthropic installé s'appuie sur httpx2
    import httpx2 as httpx
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from budget_ia import service as budget
from budget_ia.models import BudgetMensuel, OperationIA
from budget_ia.tests.outils import TARIFS_TEST, creer_eleve, creer_programme_maths, faux_client, fcfa
from programme import lecture_exercice as lecture
from programme.ia.exceptions import (
    BudgetEpuise, IATimeout, LimiteInteractionsAtteinte, LimiteJourAtteinte, OperationDejaEnCours,
)
from programme.professeur import ia as ia_prof
from programme.professeur import tour

S = OperationIA.Statut
SOUS_CLE = override_settings(IA_TARIFS_USD=TARIFS_TEST, ANTHROPIC_API_KEY="cle-secrete-factice", BUDGET_IA_PLAFOND_ACTIF=True, BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=90000)


def ouvrir(fonction="lecture", **kw):
    return budget.ouvrir(fonctionnalite=fonction, **{**dict(modele="m", tokens_entree=1000, tokens_sortie_max=1000), **kw})


@SOUS_CLE
class AppelsSdkTests(TestCase):
    """Chemin réel de `ia.appeler_outil` / `lecture._envoyer_a_anthropic` : si un contrôle échoue, AUCUN appel ne part."""

    def setUp(self):
        self.eleve = creer_eleve()

    def appel_prof(self, client, exercice="ex", etiquette="tour", max_tokens=1000):
        with budget.contexte(utilisateur_id=self.eleve.id, exercice_cle=exercice), mock.patch("anthropic.Anthropic", return_value=client):
            return ia_prof.appeler_outil(modele="m", systeme="S", outil=tour.OUTIL, message="bonjour", max_tokens=max_tokens, etiquette=etiquette)

    def client_ok(self, **kw):
        return faux_client(outil=tour.NOM_OUTIL, entree_outil={"message": "ok"}, **kw)

    def test_succes_enregistre_la_consommation_reelle(self):
        self.appel_prof(self.client_ok(entree=1500, sortie=300))
        op = OperationIA.objects.get()
        self.assertEqual((op.statut, op.fonctionnalite, op.tokens_entree, op.tokens_sortie), (S.TERMINEE, "professeur_tour", 1500, 300))
        self.assertEqual(op.cout_fcfa, fcfa(2, 1500, 10, 300))
        self.assertEqual(BudgetMensuel.objects.get().depense_fcfa, op.cout_fcfa)

    def test_budget_epuise_aucun_appel_anthropic(self):
        BudgetMensuel.objects.create(mois=budget.mois_et_jour()[0], depense_fcfa=Decimal("90000"))
        client = self.client_ok()
        with self.assertRaises(BudgetEpuise):
            self.appel_prof(client)
        client.messages.create.assert_not_called()

    def test_quota_atteint_aucun_appel_anthropic(self):
        for _ in range(10):
            self.appel_prof(self.client_ok())
        client = self.client_ok()
        with self.assertRaises(LimiteInteractionsAtteinte):
            self.appel_prof(client)
        client.messages.create.assert_not_called()

    def test_plafond_de_tokens_de_sortie_par_reponse(self):
        client = self.client_ok()
        self.appel_prof(client, max_tokens=14000)
        self.assertEqual(client.messages.create.call_args.kwargs["max_tokens"], 4000)   # IA_MAX_TOKENS_SORTIE_PAR_REPONSE
        with override_settings(IA_MAX_TOKENS_SORTIE_PAR_REPONSE=1500):
            client = self.client_ok()
            self.appel_prof(client, max_tokens=14000)
            self.assertEqual(client.messages.create.call_args.kwargs["max_tokens"], 1500)   # réglable sans code

    def test_plan_n_est_pas_borne_a_4000_il_a_son_propre_plafond(self):
        client = self.client_ok()
        self.appel_prof(client, etiquette="plan", max_tokens=14000)
        self.assertEqual(client.messages.create.call_args.kwargs["max_tokens"], 14000)

    def test_timeout_fournisseur_resultat_inconnu_cout_conserve(self):
        import anthropic
        requete = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        with self.assertRaises(IATimeout):
            self.appel_prof(faux_client(effets=anthropic.APITimeoutError(request=requete)))
        op = OperationIA.objects.get()
        self.assertEqual(op.statut, S.INCONNUE)
        self.assertEqual(BudgetMensuel.objects.get().depense_fcfa, op.cout_reserve_fcfa)

    def test_erreur_fournisseur_429_ne_coute_rien(self):
        import anthropic
        requete = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        erreur = anthropic.RateLimitError("limite", response=httpx.Response(429, request=requete), body=None)
        with self.assertRaises(Exception):
            self.appel_prof(faux_client(effets=erreur))
        self.assertEqual((OperationIA.objects.get().statut, BudgetMensuel.objects.get().depense_fcfa), (S.ECHOUEE, 0))

    def test_reponse_sans_usage_compte_la_reservation(self):
        self.appel_prof(self.client_ok(usage=False))
        op = OperationIA.objects.get()
        self.assertEqual((op.consommation_connue, op.cout_fcfa), (False, op.cout_reserve_fcfa))

    def test_reponse_tronquee_est_quand_meme_facturee(self):
        client = faux_client(entree=800, sortie=8000, stop_reason="max_tokens")
        with override_settings(IA_LECTURE_TIMEOUT_SECONDES=10), budget.contexte(utilisateur_id=self.eleve.id, exercice_cle="ex"), \
                mock.patch("anthropic.Anthropic", return_value=client):
            with self.assertRaises(lecture.LectureTropLongue):
                lecture._envoyer_a_anthropic(modele="m", contenu=[{"type": "text", "text": "x"}])
        op = OperationIA.objects.get()
        self.assertEqual((op.statut, op.tokens_sortie), (S.TERMINEE, 8000))

    def test_aucun_contenu_ni_cle_n_est_stocke(self):
        self.appel_prof(self.client_ok())
        for op in OperationIA.objects.values():
            self.assertNotIn("cle-secrete-factice", str(op))
            self.assertNotIn("bonjour", str(op))

    def test_cle_absente_aucune_operation_ouverte(self):
        with override_settings(ANTHROPIC_API_KEY=""), self.assertRaises(Exception):
            self.appel_prof(self.client_ok())
        self.assertEqual(OperationIA.objects.count(), 0)

    def test_contenu_admin_compte_dans_le_meme_budget(self):
        from programme.ia import fournisseurs
        reponse = mock.Mock(content=[mock.Mock(type="text", text="Bonjour")], stop_reason="end_turn")
        reponse.usage = mock.Mock(input_tokens=500, output_tokens=200, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        client = mock.Mock()
        client.messages.create.return_value = reponse
        with override_settings(IA_MODELE="m"), mock.patch("anthropic.Anthropic", return_value=client) as constructeur:
            r = fournisseurs.appeler_ia("système", "prompt", max_tokens=500)
        self.assertEqual(r.texte, "Bonjour")
        self.assertEqual(constructeur.call_args.kwargs["max_retries"], 0)   # un retry automatique doublerait le coût
        op = OperationIA.objects.get()
        self.assertEqual((op.fonctionnalite, op.utilisateur_id, op.statut), ("contenu_admin", None, S.TERMINEE))


@override_settings(IA_TARIFS_USD=TARIFS_TEST, ANTHROPIC_API_KEY="cle-secrete-factice", IA_LECTURE_ACTIVE=True, IA_LECTURE_DEV_SEULEMENT=False,
                   IA_CORRECTION_ACTIVE=True, IA_CORRECTION_DEV_SEULEMENT=False, IA_PROF_ACTIVE=True, IA_PROF_DEV_SEULEMENT=False,
                   IA_MODELE="m", IA_LECTURE_MODELE="", IA_CORRECTION_MODELE="", IA_PROF_MODELE="", BUDGET_IA_PLAFOND_ACTIF=True, BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=90000)
class VuesTests(TestCase):
    """Vraies vues DRF + faux SDK : codes HTTP, messages élève, aucun secret, aucun appel quand un contrôle refuse."""

    def setUp(self):
        cache.clear()
        self.eleve, self.programme = creer_programme_maths()
        self.api = APIClient()
        self.api.force_authenticate(self.eleve)

    ANALYSE = {"lisible": True, "matiere": {"valeur": "mathematiques", "confiance": "haute"}, "niveau": {"valeur": "Terminale C", "confiance": "haute"},
               "enonce": "Résoudre x^2 - 5x + 6 = 0", "donnees": [], "formules": [], "questions": [{"numero": "1", "texte": "Résoudre", "incertain": False}],
               "figures": [], "tableaux": [], "parties_incertaines": [], "remarques": [], "concordance_programme": "concorde"}

    def deposer(self, texte="Résoudre x^2 - 5x + 6 = 0 dans R."):
        return self.api.post("/api/eleve/resoudre/", {"programme": self.programme.id, "mode": "correction", "enonce": texte, "analyser": "true"}, format="multipart")

    def test_lecture_puis_quota_du_jour_en_429_sans_appel(self):
        client = faux_client(entree_outil=dict(self.ANALYSE), outil=lecture.NOM_OUTIL)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i in range(3):
                r = self.deposer(f"Exercice numero {i} : résoudre x^2 = {i + 1}.")
                self.assertEqual(r.status_code, 200, r.content)
                self.assertTrue(r.json()["analysee"])
            appels = client.messages.create.call_count
            r = self.deposer("Un quatrième exercice : résoudre x^2 = 9.")
        self.assertEqual((r.status_code, r.json()["code"], r.json()["detail"]), (429, "limite_jour", "Limite du jour atteinte."))
        self.assertEqual(client.messages.create.call_count, appels)   # le 4e n'a PAS atteint Anthropic

    def test_lecture_puis_correction_comptent_pour_un_seul_exercice(self):
        """La correction demandée sur l'analyse reçue de la lecture reste LE MÊME exercice (un seul sur les 3 du jour)."""
        with mock.patch("anthropic.Anthropic", return_value=faux_client(entree_outil=dict(self.ANALYSE), outil=lecture.NOM_OUTIL)):
            analyse = self.deposer().json()["analyse"]
        correction = {"donnees": [], "formules": [], "questions": [], "conclusion": "ok", "incertitudes_generales": []}
        client = faux_client(entree_outil=correction, outil="enregistrer_correction")
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = self.api.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": analyse}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        ops = list(OperationIA.objects.order_by("id"))
        self.assertEqual([o.fonctionnalite for o in ops], ["lecture", "correction"])
        self.assertEqual(ops[0].exercice_cle, ops[1].exercice_cle)
        self.assertEqual(len({o.exercice_cle for o in ops}), 1)

    def test_budget_epuise_503_sans_appel_et_sans_detail_interne(self):
        BudgetMensuel.objects.create(mois=budget.mois_et_jour()[0], depense_fcfa=Decimal("90000"))
        client = faux_client()
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = self.deposer()
        client.messages.create.assert_not_called()
        self.assertEqual((r.status_code, r.json()["code"]), (503, "budget_epuise"))
        corps = r.content.decode()
        for interdit in ("cle-secrete-factice", "FCFA", "USD", "90000", "token", "claude"):
            self.assertNotIn(interdit, corps)

    def test_interrupteur_global_les_vues_disent_indisponible(self):
        client = faux_client()
        with override_settings(IA_INTERRUPTEUR_GLOBAL=False), mock.patch("anthropic.Anthropic", return_value=client):
            r = self.deposer()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["analyse_disponible"])
        client.messages.create.assert_not_called()

    def test_correction_et_seance_refusees_si_budget_epuise(self):
        BudgetMensuel.objects.create(mois=budget.mois_et_jour()[0], depense_fcfa=Decimal("90000"))
        client = faux_client()
        corps = {"programme": self.programme.id, "analyse": dict(self.ANALYSE)}
        with mock.patch("anthropic.Anthropic", return_value=client):
            r1 = self.api.post("/api/eleve/correction/", corps, format="json")
            r2 = self.api.post("/api/eleve/professeur/seances/", corps, format="json")
        client.messages.create.assert_not_called()
        self.assertEqual((r1.status_code, r1.json()["code"]), (503, "budget_epuise"))
        self.assertEqual((r2.status_code, r2.json()["code"]), (503, "budget_epuise"))

    def test_permissions_anonyme_et_non_eleve(self):
        for url in ("/api/eleve/resoudre/", "/api/eleve/correction/", "/api/eleve/professeur/seances/"):
            self.assertEqual(APIClient().post(url, {}, format="json").status_code, 401, url)
        from comptes.models import User
        vendeur = User.objects.create_user("+22790000066", password="Motdepasse-2026", prenom="V", nom="V", role=User.Role.VENDEUR, statut=User.Statut.ACTIF)
        c = APIClient()
        c.force_authenticate(vendeur)
        self.assertEqual(c.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": {}}, format="json").status_code, 403)

    def test_programme_hors_classe_reste_404_avant_tout_comptage(self):
        client = faux_client()
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = self.api.post("/api/eleve/correction/", {"programme": 99999, "analyse": dict(self.ANALYSE)}, format="json")
        self.assertEqual(r.status_code, 404)
        client.messages.create.assert_not_called()
        self.assertEqual(OperationIA.objects.count(), 0)

    def test_forme_de_la_reponse_resoudre_inchangee(self):
        """Compatibilité de l'ancien endpoint : mêmes champs qu'avant, aucun champ de budget exposé."""
        with mock.patch("anthropic.Anthropic", return_value=faux_client(entree_outil=dict(self.ANALYSE), outil=lecture.NOM_OUTIL)):
            corps = self.deposer().json()
        for champ in ("valide", "enregistre", "traite", "analyse_disponible", "correction_disponible", "professeur_disponible", "analysee", "analyse", "recapitulatif"):
            self.assertIn(champ, corps)
        self.assertNotIn("cout", str(corps).lower())


class ConcurrenceTests(TransactionTestCase):
    """Verrous de ligne PostgreSQL réels : des threads simultanés ne peuvent dépasser ni le plafond ni un quota."""

    def lancer(self, nb, cible):
        resultats, barriere = [], threading.Barrier(nb)

        def tache(i):
            try:
                barriere.wait(timeout=10)
                resultats.append(cible(i))
            except Exception as exc:  # noqa: BLE001
                resultats.append(exc)
            finally:
                connection.close()

        fils = [threading.Thread(target=tache, args=(i,)) for i in range(nb)]
        for f in fils:
            f.start()
        for f in fils:
            f.join(60)
        return resultats

    @override_settings(IA_TARIFS_USD=TARIFS_TEST, BUDGET_IA_PLAFOND_ACTIF=True, BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=40)   # 5 réservations de 7,92 tiennent (39,6)
    def test_requetes_simultanees_ne_depassent_jamais_le_plafond(self):
        eleves = [creer_eleve(f"+2279000{i:04d}") for i in range(12)]

        def cible(i):
            with budget.contexte(utilisateur_id=eleves[i].id, exercice_cle=f"ex{i}"):
                return ouvrir()

        res = self.lancer(12, cible)
        reussies = [r for r in res if isinstance(r, OperationIA)]
        self.assertEqual([r for r in res if not isinstance(r, (OperationIA, BudgetEpuise))], [])
        self.assertEqual((len(reussies), len([r for r in res if isinstance(r, BudgetEpuise)])), (5, 7))
        b = BudgetMensuel.objects.get()
        self.assertLessEqual(b.depense_fcfa + b.reserve_fcfa, 40)
        self.assertEqual(b.reserve_fcfa, sum(o.cout_reserve_fcfa for o in reussies))

    @override_settings(IA_TARIFS_USD=TARIFS_TEST)
    def test_requetes_simultanees_d_un_meme_eleve_respectent_le_quota_du_jour(self):
        eleve = creer_eleve()

        def cible(i):
            with budget.contexte(utilisateur_id=eleve.id, exercice_cle=f"ex{i}"):
                return ouvrir()

        res = self.lancer(8, cible)
        self.assertEqual(len([r for r in res if isinstance(r, OperationIA)]), 3)
        self.assertEqual(len([r for r in res if isinstance(r, LimiteJourAtteinte)]), 5)

    @override_settings(IA_TARIFS_USD=TARIFS_TEST)
    def test_double_clic_simultane_une_seule_operation(self):
        eleve = creer_eleve()

        def cible(i):
            with budget.contexte(utilisateur_id=eleve.id, exercice_cle="ex", cle_requete="meme-requete"):
                return ouvrir()

        res = self.lancer(6, cible)
        self.assertEqual(len([r for r in res if isinstance(r, OperationIA)]), 1)
        self.assertEqual(len([r for r in res if isinstance(r, OperationDejaEnCours)]), 5)

    @override_settings(IA_TARIFS_USD=TARIFS_TEST)
    def test_interactions_simultanees_ne_depassent_pas_dix_par_exercice(self):
        eleve = creer_eleve()

        def cible(i):
            with budget.contexte(utilisateur_id=eleve.id, exercice_cle="ex", cle_requete=f"r{i}"):
                return ouvrir("professeur_tour")

        res = self.lancer(16, cible)
        self.assertEqual(len([r for r in res if isinstance(r, OperationIA)]), 10)
        self.assertEqual(len([r for r in res if isinstance(r, LimiteInteractionsAtteinte)]), 6)
