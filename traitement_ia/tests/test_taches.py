"""
Traitements IA longs : mise en file, worker, reprise après interruption, quotas, séances partagées.
Fournisseurs SIMULÉS (faux SDK qui compte ses appels) : aucun appel Anthropic payant.
"""

import copy
import threading
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from budget_ia import service as budget
from budget_ia.models import BudgetMensuel, OperationIA
from budget_ia.tests.outils import TARIFS_TEST, creer_eleve, creer_programme_maths
from programme import lecture_exercice as lecture
from programme.correction import resolution
from programme.professeur import plan as plan_module
from programme.professeur import seance, tour
from programme.test_correction_exercice import ANALYSE_EX1, CORRECTION_EX1
from programme.test_professeur import PLAN_BRUT, _wolfram
from traitement_ia import service
from traitement_ia.models import FichierTacheIA, TacheIA

S = TacheIA.Statut
SORTIE_TOUR = {"message": "Tu es sur la bonne voie.", "type_erreur": "aucune", "resume_erreur": "", "evaluation": "non_applicable"}


def faux_sdk(**sorties):
    """Faux client Anthropic : renvoie, selon l'outil demandé, la sortie scénarisée. Mémorise chaque appel."""
    par_outil = {
        lecture.NOM_OUTIL: sorties.get("analyse"), resolution.NOM_OUTIL: sorties.get("correction"),
        plan_module.NOM_OUTIL: sorties.get("plan", PLAN_BRUT), tour.NOM_OUTIL: sorties.get("tour", SORTIE_TOUR),
    }
    appels = []

    def create(**kw):
        nom = kw["tool_choice"]["name"]
        appels.append(nom)
        action = sorties.get("action")
        if action:
            action(nom)
        return SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name=nom, input=copy.deepcopy(par_outil[nom]))],
            stop_reason="tool_use", usage=SimpleNamespace(input_tokens=1200, output_tokens=600),
        )

    client = mock.Mock()
    client.messages.create.side_effect = create
    client.appels = appels
    return client


ANALYSE = {"lisible": True, "matiere": {"valeur": "mathematiques", "confiance": "haute"}, "niveau": {"valeur": "Terminale C", "confiance": "haute"},
           "enonce": "Résoudre x^2 - 5x + 6 = 0", "donnees": [], "formules": [], "questions": [{"numero": "1", "texte": "Résoudre", "incertain": False}],
           "figures": [], "tableaux": [], "parties_incertaines": [], "remarques": [], "concordance_programme": "concorde"}

REGLAGES = dict(
    IA_TARIFS_USD=TARIFS_TEST, ANTHROPIC_API_KEY="cle-secrete-factice", IA_MODELE="m", IA_LECTURE_MODELE="", IA_CORRECTION_MODELE="", IA_PROF_MODELE="",
    IA_LECTURE_ACTIVE=True, IA_LECTURE_DEV_SEULEMENT=False, IA_CORRECTION_ACTIVE=True, IA_CORRECTION_DEV_SEULEMENT=False,
    IA_PROF_ACTIVE=True, IA_PROF_DEV_SEULEMENT=False, IA_TRAITEMENT_ASYNCHRONE=True, WOLFRAM_APP_ID="app-id-factice",
    BUDGET_IA_PLAFOND_ACTIF=True, BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=90000, IA_PROF_SEANCE_SECONDES=600,
)


def traiter_tout(nom="w-test"):
    """Ce que fait le worker : réclamer puis exécuter jusqu'à épuisement."""
    n = 0
    while (t := service.reclamer(nom)) is not None:
        service.executer(t)
        n += 1
    return n


@override_settings(**REGLAGES)
class BaseAsync(TestCase):
    def setUp(self):
        cache.clear()
        self.eleve, self.programme = creer_programme_maths()
        self.api = APIClient()
        self.api.force_authenticate(self.eleve)
        p = mock.patch("programme.correction.wolfram._requete_http", side_effect=_wolfram)
        p.start()
        self.addCleanup(p.stop)

    def deposer(self, texte="Résoudre x^2 - 5x + 6 = 0 dans R.", **extra):
        return self.api.post("/api/eleve/resoudre/", {"programme": self.programme.id, "mode": "correction", "enonce": texte, "analyser": "true", **extra}, format="multipart")

    def tache(self, reponse):
        self.assertEqual(reponse.status_code, 202, reponse.content)
        return TacheIA.objects.get(pk=reponse.json()["tache"]["id"])

    def etat(self, tache):
        r = self.api.get(f"/api/eleve/taches/{tache.id}/")
        self.assertEqual(r.status_code, 200)
        return r.json()


class LectureAsynchroneTests(BaseAsync):
    def test_la_requete_web_rend_la_main_sans_appeler_le_fournisseur(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = self.deposer()
            self.assertEqual(r.status_code, 202)
            self.assertEqual(r.json()["tache"]["statut"], "en_attente")
            self.assertEqual(client.appels, [])   # rien n'est parti : la requête web n'attend jamais l'IA
            self.assertEqual(OperationIA.objects.count(), 0)

    def test_le_worker_produit_le_meme_resultat_que_le_mode_synchrone(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.tache(self.deposer())
            traiter_tout()
        etat = self.etat(tache)
        self.assertEqual((etat["statut"], etat["http"]), ("terminee", 200))
        corps = etat["corps"]
        for champ in ("valide", "analyse_disponible", "analysee", "analyse", "recapitulatif", "correction_disponible", "professeur_disponible"):
            self.assertIn(champ, corps)
        self.assertTrue(corps["analysee"])
        self.assertEqual(corps["recapitulatif"]["mode"], "correction")
        self.assertEqual(client.appels, [lecture.NOM_OUTIL])

    def test_fichiers_supprimes_a_la_fin_et_resultat_purge_a_l_expiration(self):
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 200
        from django.core.files.uploadedfile import SimpleUploadedFile
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            r = self.api.post("/api/eleve/resoudre/", {"programme": self.programme.id, "mode": "professeur", "analyser": "true",
                                                      "fichiers": [SimpleUploadedFile("p.png", png, content_type="image/png")]}, format="multipart")
            tache = self.tache(r)
            self.assertEqual(FichierTacheIA.objects.filter(tache=tache).count(), 1)   # conservé le temps du traitement
            traiter_tout()
        self.assertEqual(FichierTacheIA.objects.count(), 0)
        tache.refresh_from_db()
        self.assertEqual(tache.resultat_http, 200)
        TacheIA.objects.filter(pk=tache.pk).update(expire_le=timezone.now() - timedelta(seconds=1))
        self.assertEqual(service.purger(), 0)   # contenu effacé, trace conservée 24 h
        expiree = self.api.get(f"/api/eleve/taches/{tache.id}/")
        self.assertEqual((expiree.status_code, expiree.json()), (200, {"id": str(tache.id), "statut": "expiree"}))
        TacheIA.objects.filter(pk=tache.pk).update(expire_le=timezone.now() - timedelta(days=2))
        self.assertEqual(service.purger(), 1)
        self.assertEqual(self.api.get(f"/api/eleve/taches/{tache.id}/").status_code, 404)

    def test_validation_simple_sans_analyse_reste_synchrone(self):
        r = self.api.post("/api/eleve/resoudre/", {"programme": self.programme.id, "mode": "correction", "enonce": "x^2=4"}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(TacheIA.objects.count(), 0)

    def test_erreurs_de_validation_immediates_jamais_mises_en_file(self):
        r = self.api.post("/api/eleve/resoudre/", {"programme": self.programme.id, "mode": "inconnu", "enonce": "x", "analyser": "true"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        r = self.api.post("/api/eleve/resoudre/", {"programme": 99999, "mode": "correction", "enonce": "x", "analyser": "true"}, format="multipart")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(TacheIA.objects.count(), 0)

    def test_double_clic_meme_tache_un_seul_traitement(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)) as ctor:
            a, b = self.tache(self.deposer()), self.tache(self.deposer())
            self.assertEqual(a.pk, b.pk)
            self.assertEqual(TacheIA.objects.count(), 1)
            traiter_tout()
            self.assertEqual(ctor.return_value.messages.create.call_count, 1)

    def test_trop_de_taches_actives_429(self):
        for i in range(3):
            self.tache(self.deposer(f"Exercice distinct numero {i} : résoudre x^2 = {i}."))
        r = self.deposer("Un quatrième exercice distinct : x^2 = 7.")
        self.assertEqual((r.status_code, r.json()["code"]), (429, "trop_de_taches"))

    def test_une_tache_n_est_lisible_que_par_son_proprietaire(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            tache = self.tache(self.deposer())
        autre = APIClient()
        autre.force_authenticate(creer_eleve("+22790000044"))
        self.assertEqual(autre.get(f"/api/eleve/taches/{tache.id}/").status_code, 404)
        self.assertEqual(APIClient().get(f"/api/eleve/taches/{tache.id}/").status_code, 401)


class QuotasEtBudgetDansLeWorkerTests(BaseAsync):
    def test_quota_du_jour_applique_par_le_worker_sans_appel(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i in range(3):
                self.tache(self.deposer(f"Exercice numero {i} : résoudre x^2 = {i + 1}."))
                traiter_tout()
            appels = len(client.appels)
            quatrieme = self.tache(self.deposer("Quatrième exercice : résoudre x^2 = 99."))
            traiter_tout()
        etat = self.etat(quatrieme)
        self.assertEqual((etat["http"], etat["corps"]["code"]), (429, "limite_jour"))
        self.assertEqual(len(client.appels), appels)

    def test_budget_epuise_applique_par_le_worker_sans_appel(self):
        BudgetMensuel.objects.create(mois=budget.mois_et_jour()[0], depense_fcfa=Decimal("90000"))
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.tache(self.deposer())
            traiter_tout()
        etat = self.etat(tache)
        self.assertEqual((etat["http"], etat["corps"]["code"]), (503, "budget_epuise"))
        self.assertEqual(client.appels, [])

    def test_interrupteur_global_coupe_aussi_les_taches_deja_en_file(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.tache(self.deposer())
            with override_settings(IA_INTERRUPTEUR_GLOBAL=False):
                traiter_tout()
        self.assertEqual(client.appels, [])   # aucun appel : la tâche se termine en « analyse indisponible »
        self.assertFalse(self.etat(tache)["corps"]["analyse_disponible"])

    def test_eleve_desactive_apres_mise_en_file_tache_refusee(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)) as ctor:
            tache = self.tache(self.deposer())
            self.eleve.statut = self.eleve.Statut.EN_ATTENTE
            self.eleve.save()
            traiter_tout()
            ctor.return_value.messages.create.assert_not_called()
        tache.refresh_from_db()
        self.assertEqual(tache.resultat_http, 403)


class ReprisesApresInterruptionTests(BaseAsync):
    def deposer_et_reclamer(self):
        tache = self.tache(self.deposer())
        return service.reclamer("worker-A")

    def test_une_tache_en_cours_n_est_pas_prise_par_un_autre_worker(self):
        self.deposer_et_reclamer()
        self.assertIsNone(service.reclamer("worker-B"))

    def test_bail_expire_un_autre_worker_reprend_puis_abandon_apres_les_tentatives(self):
        t = self.deposer_et_reclamer()
        self.assertEqual(t.tentatives, 1)
        TacheIA.objects.filter(pk=t.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))   # worker A est mort
        t2 = service.reclamer("worker-B")
        self.assertEqual((t2.pk, t2.tentatives, t2.travailleur), (t.pk, 2, "worker-B"))
        TacheIA.objects.filter(pk=t.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))   # B meurt aussi
        self.assertIsNone(service.reclamer("worker-C"))   # 2 tentatives maximum : abandon propre
        etat = self.etat(t)
        self.assertEqual((etat["statut"], etat["http"], etat["corps"]["code"]), ("echouee", 503, "tache_abandonnee"))

    def test_crash_apres_la_reponse_du_fournisseur_la_reprise_ne_refacture_pas(self):
        """Worker tué APRÈS l'appel Anthropic mais AVANT l'enregistrement du résultat : la reprise relit le cache partagé."""
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.tache(self.deposer())
            t = service.reclamer("A")
            with mock.patch("traitement_ia.service._clore", side_effect=RuntimeError("worker tué")):
                with self.assertRaises(RuntimeError):
                    service.executer(t)
            self.assertEqual(len(client.appels), 1)
            TacheIA.objects.filter(pk=tache.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))
            traiter_tout("B")
        self.assertEqual(len(client.appels), 1)   # PAS de second appel payant
        self.assertEqual(self.etat(tache)["http"], 200)
        self.assertEqual(OperationIA.objects.filter(statut="terminee").count(), 1)

    def test_crash_pendant_l_appel_la_reservation_orpheline_reste_comptee(self):
        """Worker tué PENDANT l'appel : la réservation reste ouverte puis est soldée comme dépense (jamais effacée)."""
        tache = self.tache(self.deposer())
        t = service.reclamer("A")
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)), \
                mock.patch("traitement_ia.service._clore", side_effect=RuntimeError("tué")):
            with self.assertRaises(RuntimeError):
                service.executer(t)
        op = OperationIA.objects.get()
        # simulons un crash AVANT toute réponse : on remet l'opération « en cours »
        OperationIA.objects.filter(pk=op.pk).update(statut="reservee", cout_fcfa=None, termine_le=None)
        BudgetMensuel.objects.update(reserve_fcfa=op.cout_reserve_fcfa, depense_fcfa=0)
        with mock.patch("django.utils.timezone.now", return_value=op.cree_le + timedelta(seconds=1000)):
            self.assertEqual(budget.reconcilier_abandonnees(), 1)
        op.refresh_from_db()
        self.assertEqual(op.statut, "inconnue")
        self.assertEqual(BudgetMensuel.objects.get().depense_fcfa, op.cout_reserve_fcfa)
        self.assertEqual(TacheIA.objects.get(pk=tache.pk).tentatives, 1)

    def test_une_reprise_ne_contourne_pas_le_quota_par_exercice(self):
        """Les tentatives rejouent le MÊME exercice : jamais un exercice de plus, jamais plus de 3 lectures."""
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i in range(4):   # 4 envois du même exercice avec une remarque de relecture différente
                self.tache(self.deposer("Résoudre x^2 - 5x + 6 = 0 dans R.", correction=f"Relis la question {i}"))
                traiter_tout()
        lectures = OperationIA.objects.filter(fonctionnalite="lecture", statut="terminee").count()
        self.assertLessEqual(lectures, 3)
        self.assertEqual(len({o.exercice_cle for o in OperationIA.objects.all()}), 1)

    def test_nouvel_essai_differe_si_un_verrou_deja_en_cours_est_laisse_par_un_worker_mort(self):
        tache = self.tache(self.deposer())
        t = service.reclamer("A")
        with mock.patch.object(service, "import_string") as imp:
            vue = imp.return_value.return_value
            vue.executer.return_value = SimpleNamespace(status_code=409, data={"detail": "Cet exercice est déjà en cours d'analyse."})
            service.executer(t)
        tache.refresh_from_db()
        self.assertEqual(tache.statut, S.EN_ATTENTE)
        self.assertGreater(tache.disponible_le, timezone.now())   # réessayé plus tard, pas affiché comme une erreur
        self.assertIsNone(service.reclamer("B"))


class DeuxModesTests(BaseAsync):
    def lire_analyse(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            tache = self.tache(self.deposer())
            traiter_tout()
        return self.etat(tache)["corps"]["analyse"]

    def test_mode_correction_via_worker_garde_le_meme_exercice_que_la_lecture(self):
        analyse = self.lire_analyse()   # étape « Relis ton énoncé » : le résultat de la lecture est rendu à l'élève
        client = faux_sdk(correction=CORRECTION_EX1)
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = self.api.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": analyse}, format="json")
            tache = self.tache(r)
            self.assertEqual(client.appels, [])
            traiter_tout()
        etat = self.etat(tache)
        self.assertEqual((etat["statut"], etat["http"]), ("terminee", 200))
        self.assertIn("correction", etat["corps"])
        ops = list(OperationIA.objects.order_by("id"))
        self.assertEqual([o.fonctionnalite for o in ops], ["lecture", "correction"])
        self.assertEqual(len({o.exercice_cle for o in ops}), 1)

    def test_mode_professeur_via_worker_demarrage_puis_interaction(self):
        analyse = self.lire_analyse()
        client = faux_sdk()
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = self.api.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": analyse}, format="json")
            demarrage = self.tache(r)
            traiter_tout()
            etat = self.etat(demarrage)
            self.assertEqual((etat["statut"], etat["http"]), ("terminee", 201))
            vue = etat["corps"]["seance"]
            self.assertEqual(client.appels, [plan_module.NOM_OUTIL])
            # une interaction : « je n'ai pas compris »
            r = self.api.post(f"/api/eleve/professeur/seances/{vue['seance']}/explication/", {"version": vue["version"], "type": "incomprehension"}, format="json")
            interaction = self.tache(r)
            traiter_tout()
        etat = self.etat(interaction)
        self.assertEqual(etat["http"], 200, etat)
        self.assertEqual(client.appels, [plan_module.NOM_OUTIL, tour.NOM_OUTIL])
        ops = list(OperationIA.objects.order_by("id"))
        self.assertEqual([o.fonctionnalite for o in ops], ["lecture", "professeur_plan", "professeur_tour"])
        self.assertEqual(len({o.exercice_cle for o in ops}), 1)   # lecture + plan + interaction = UN exercice

    def test_dix_interactions_puis_onzieme_refusee_par_le_worker(self):
        analyse = self.lire_analyse()
        client = faux_sdk()
        with mock.patch("anthropic.Anthropic", return_value=client), override_settings(IA_PROF_MAX_APPELS_IA=40):
            r = self.api.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": analyse}, format="json")
            traiter_tout()
            vue = self.etat(self.tache(r))["corps"]["seance"]
            codes = []
            for i in range(11):
                r = self.api.post(f"/api/eleve/professeur/seances/{vue['seance']}/explication/", {"version": vue["version"], "type": "exemple"}, format="json")
                t = self.tache(r)
                traiter_tout()
                e = self.etat(t)
                codes.append(e["http"])
                if e["http"] == 200:
                    vue = e["corps"]["seance"]
        self.assertEqual(codes[:10], [200] * 10)
        self.assertEqual(codes[10], 429)
        self.assertEqual(client.appels.count(tour.NOM_OUTIL), 10)


class WorkerEtConcurrenceTests(TransactionTestCase):
    """Plusieurs threads = plusieurs workers : chacun a SA connexion PostgreSQL."""

    def setUp(self):
        cache.clear()

    @override_settings(**REGLAGES)
    def test_une_tache_n_est_reclamee_que_par_un_seul_worker(self):
        eleve, programme = creer_programme_maths()
        api = APIClient()
        api.force_authenticate(eleve)
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            api.post("/api/eleve/resoudre/", {"programme": programme.id, "mode": "correction", "enonce": "x^2=4", "analyser": "true"}, format="multipart")
        resultats, barriere = [], threading.Barrier(6)

        def worker(i):
            try:
                barriere.wait(timeout=10)
                resultats.append(service.reclamer(f"w{i}"))
            finally:
                connection.close()

        fils = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        [f.start() for f in fils]
        [f.join(30) for f in fils]
        self.assertEqual(len([r for r in resultats if r is not None]), 1)

    @override_settings(**REGLAGES)
    def test_traitement_long_en_cours_visible_puis_termine_sans_bloquer_le_web(self):
        """Le fournisseur « met longtemps » : pendant ce temps l'API web répond tout de suite et voit « en_cours »."""
        eleve, programme = creer_programme_maths()
        api = APIClient()
        api.force_authenticate(eleve)
        debut, libere = threading.Event(), threading.Event()

        def lent(nom):
            debut.set()
            libere.wait(timeout=30)   # représente 60 s de génération

        client = faux_sdk(analyse=ANALYSE, action=lent)
        with mock.patch("anthropic.Anthropic", return_value=client):
            r = api.post("/api/eleve/resoudre/", {"programme": programme.id, "mode": "correction", "enonce": "x^2=4", "analyser": "true"}, format="multipart")
            self.assertEqual(r.status_code, 202)
            tache_id = r.json()["tache"]["id"]

            def travail():
                try:
                    traiter_tout("lent")
                finally:
                    connection.close()

            fil = threading.Thread(target=travail)
            fil.start()
            self.assertTrue(debut.wait(timeout=20))
            suivi = api.get(f"/api/eleve/taches/{tache_id}/")   # le web répond immédiatement pendant l'appel IA
            self.assertEqual((suivi.status_code, suivi.json()["statut"]), (200, "en_cours"))
            libere.set()
            fil.join(30)
        final = api.get(f"/api/eleve/taches/{tache_id}/").json()
        self.assertEqual((final["statut"], final["http"]), ("terminee", 200))

    @override_settings(**REGLAGES)
    def test_commande_worker_une_fois_traite_les_taches_en_parallele(self):
        eleve, programme = creer_programme_maths()
        api = APIClient()
        api.force_authenticate(eleve)
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i in range(3):
                api.post("/api/eleve/resoudre/", {"programme": programme.id, "mode": "correction", "enonce": f"exercice {i} : x^2={i + 1}", "analyser": "true"}, format="multipart")
            call_command("traiter_taches_ia", "--une-fois", "--threads", "3")
        self.assertEqual(TacheIA.objects.filter(statut="terminee", resultat_http=200).count(), 3)
        self.assertEqual(len(client.appels), 3)


class SeancesPartageesTests(TransactionTestCase):
    """Le cache est PARTAGÉ (PostgreSQL), pas la mémoire d'un processus : séances et verrous valent pour tous les processus."""

    def test_le_cache_par_defaut_est_la_base_pas_la_memoire_locale(self):
        from django.conf import settings
        self.assertEqual(settings.CACHES["default"]["BACKEND"], "django.core.cache.backends.db.DatabaseCache")
        self.assertGreaterEqual(settings.CACHES["default"]["OPTIONS"]["MAX_ENTRIES"], 100000)   # jamais d'éviction anticipée

    def test_un_autre_processus_et_un_redemarrage_voient_la_seance(self):
        cache.set("prof:seance:essai", {"id": "essai", "user_id": 1, "version": 3}, timeout=600)
        vu = []

        def autre_processus():
            try:
                vu.append(cache.get("prof:seance:essai"))   # autre connexion = autre processus
            finally:
                connection.close()

        t = threading.Thread(target=autre_processus)
        t.start()
        t.join(20)
        self.assertEqual(vu[0]["version"], 3)
        connection.close()   # « redémarrage » : plus rien en mémoire locale
        self.assertEqual(cache.get("prof:seance:essai")["version"], 3)

    def test_verrou_anti_double_envoi_atomique_entre_processus(self):
        cache.delete("verrou:essai")
        gagnants, barriere = [], threading.Barrier(8)

        def tenter():
            try:
                barriere.wait(timeout=10)
                gagnants.append(cache.add("verrou:essai", 1, timeout=60))
            finally:
                connection.close()

        fils = [threading.Thread(target=tenter) for _ in range(8)]
        [f.start() for f in fils]
        [f.join(30) for f in fils]
        self.assertEqual(gagnants.count(True), 1)

    @override_settings(**REGLAGES)
    def test_une_seance_creee_par_un_processus_est_utilisable_par_un_autre(self):
        eleve, programme = creer_programme_maths()
        api = APIClient()
        api.force_authenticate(eleve)
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk()):
            analyse = copy.deepcopy(ANALYSE_EX1)
            from programme.test_correction_exercice import ANALYSE_EX2
            etat = seance.demarrer(utilisateur_id=eleve.id, programme_id=programme.id,
                                   contexte=lecture.ContexteProgramme("Mathématiques", "Terminale C"), analyse_brute=copy.deepcopy(ANALYSE_EX2))
        resultat = []

        def autre_processus():
            try:
                resultat.append(seance.charger(etat["id"], eleve.id)["version"])
            finally:
                connection.close()

        t = threading.Thread(target=autre_processus)
        t.start()
        t.join(20)
        self.assertEqual(resultat, [etat["version"]])
        self.assertEqual(analyse, ANALYSE_EX1)


class RecuperationDesTachesTests(BaseAsync):
    """L'élève retrouve ses analyses après actualisation, fermeture du navigateur ou coupure réseau."""

    def test_liste_les_taches_actives_et_recentes_de_l_eleve_seulement(self):
        t1 = self.tache(self.deposer())
        autre = creer_eleve("+22790000077", niveau=self.programme.niveau, serie=self.programme.serie)
        TacheIA.objects.create(utilisateur=autre, type="lecture", vue="x", cle_requete="autre", disponible_le=timezone.now())
        r = self.api.get("/api/eleve/taches/")
        self.assertEqual(r.status_code, 200)
        ids = [t["id"] for t in r.json()["taches"]]
        self.assertEqual(ids, [str(t1.id)])
        self.assertEqual(r.json()["taches"][0]["statut"], "en_attente")

    def test_apres_actualisation_le_resultat_termine_est_retrouve(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            self.tache(self.deposer())
            traiter_tout()
        nouveau_navigateur = APIClient()
        nouveau_navigateur.force_authenticate(self.eleve)
        taches = nouveau_navigateur.get("/api/eleve/taches/").json()["taches"]
        self.assertEqual((taches[0]["statut"], taches[0]["http"], taches[0]["type"]), ("terminee", 200, "lecture"))

    def test_une_tache_expiree_est_listee_sans_contenu(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            t = self.tache(self.deposer())
            traiter_tout()
        TacheIA.objects.filter(pk=t.pk).update(expire_le=timezone.now() - timedelta(seconds=1))
        liste = self.api.get("/api/eleve/taches/").json()["taches"]
        self.assertEqual([(x["statut"], "corps" in x) for x in liste], [("expiree", False)])

    def test_visiteur_anonyme_et_non_eleve_refuses(self):
        self.assertIn(APIClient().get("/api/eleve/taches/").status_code, (401, 403))

    def test_la_retention_est_documentee_et_bornee(self):
        from django.conf import settings
        self.assertEqual(settings.IA_TACHE_RESULTAT_SECONDES, 7200)   # 2 h puis purge par le worker


class AucunSecondAppelPayantTests(BaseAsync):
    def test_reprise_apres_crash_pendant_l_appel_ne_refait_pas_d_appel_payant(self):
        """Issue du premier appel INCONNUE : la reprise s'arrête net (503 resultat_inconnu), un seul appel au total."""
        client = faux_sdk(analyse=ANALYSE)

        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.tache(self.deposer())
            t = service.reclamer("A")
            # Simule : réservation ouverte, appel parti, worker mort avant toute réponse.
            with budget.tache(t.id, reprise=False):
                with budget.contexte(utilisateur_id=self.eleve.id, exercice_cle="x"):
                    budget.ouvrir(fonctionnalite="lecture", modele="m", tokens_entree=1000, tokens_sortie_max=1000)
            TacheIA.objects.filter(pk=tache.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))
            traiter_tout("B")
        self.assertEqual(len(client.appels), 0)   # la reprise n'a PAS rappelé le fournisseur
        etat = self.etat(tache)
        self.assertEqual((etat["http"], etat["corps"]["code"]), (503, "resultat_inconnu"))
        self.assertEqual(OperationIA.objects.count(), 1)

    def test_reprise_sans_appel_prealable_s_execute_normalement(self):
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.tache(self.deposer())
            service.reclamer("A")   # worker A meurt avant d'appeler quoi que ce soit
            TacheIA.objects.filter(pk=tache.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))
            traiter_tout("B")
        self.assertEqual((len(client.appels), self.etat(tache)["http"]), (1, 200))

    def test_l_eleve_qui_relance_lui_meme_reste_soumis_aux_quotas(self):
        """Après un échec 'resultat_inconnu', une nouvelle soumission est une nouvelle demande : quotas appliqués."""
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i in range(4):
                self.tache(self.deposer(correction=f"Relis {i}"))
                traiter_tout()
        self.assertLessEqual(OperationIA.objects.filter(fonctionnalite="lecture", statut="terminee").count(), 3)


class CoherenceDesDelaisTests(TestCase):
    def test_bail_peremption_tentatives_et_delais_reels(self):
        from django.conf import settings as s
        plus_long = max(
            s.IA_LECTURE_TIMEOUT_SECONDES,
            s.IA_CORRECTION_TIMEOUT_SECONDES + 4 * s.WOLFRAM_TIMEOUT_SECONDES,
            s.IA_PROF_TIMEOUT_SECONDES + 2 * s.WOLFRAM_TIMEOUT_SECONDES,
        )
        # une tentative vivante ne perd jamais son bail ; une réservation périmée ne bloque pas une reprise légitime
        self.assertGreater(s.IA_RESERVATION_PEREMPTION_SECONDS, plus_long)
        self.assertGreater(s.IA_TACHE_BAIL_SECONDES, s.IA_RESERVATION_PEREMPTION_SECONDS)
        self.assertEqual(s.IA_TACHE_TENTATIVES_MAX, 2)
        self.assertGreater(s.IA_TACHE_RESULTAT_SECONDES, s.IA_TACHE_BAIL_SECONDES * 2)


class PlusieursElevesSimultanesTests(TransactionTestCase):
    @override_settings(**REGLAGES)
    def test_quatre_eleves_en_meme_temps_chacun_son_resultat_une_facturation(self):
        cache.clear()
        eleve, programme = creer_programme_maths()
        eleves = [eleve] + [creer_eleve(f"+2279000009{i}", niveau=programme.niveau, serie=programme.serie) for i in range(3)]
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            for i, e in enumerate(eleves):
                api = APIClient()
                api.force_authenticate(e)
                r = api.post("/api/eleve/resoudre/", {"programme": programme.id, "mode": "correction", "enonce": f"exercice {i} : x^2={i + 1}", "analyser": "true"}, format="multipart")
                self.assertEqual(r.status_code, 202)
            call_command("traiter_taches_ia", "--une-fois", "--threads", "4")
        self.assertEqual(TacheIA.objects.filter(statut="terminee", resultat_http=200).count(), 4)
        self.assertEqual(OperationIA.objects.filter(statut="terminee").count(), 4)
        self.assertEqual(len(client.appels), 4)
        self.assertEqual({t.utilisateur_id for t in TacheIA.objects.all()}, {e.id for e in eleves})


class WorkerSansConsommationPropreTests(TransactionTestCase):
    @override_settings(**REGLAGES)
    def test_le_worker_demarre_a_vide_sans_aucun_appel_ia_ni_operation(self):
        """Démarrer ou redémarrer le dyno worker ne consomme rien : il ne fait que traiter des tâches d'élèves."""
        cache.clear()
        with mock.patch("anthropic.Anthropic") as sdk:
            call_command("traiter_taches_ia", "--une-fois", "--threads", "2")
        sdk.assert_not_called()
        self.assertEqual(OperationIA.objects.count(), 0)

    def test_mode_asynchrone_desactive_par_defaut(self):
        from django.conf import settings as s
        self.assertFalse(s.IA_TRAITEMENT_ASYNCHRONE)
