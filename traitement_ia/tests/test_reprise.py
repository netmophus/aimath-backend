"""Reprise après actualisation : lecture, correction, séance fahimta ai. Fournisseurs SIMULÉS ; la reprise est en lecture seule."""

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from budget_ia import service as budget
from budget_ia import tarifs
from budget_ia.models import OperationIA
from budget_ia.tests.outils import creer_eleve
from programme.correction import resolution
from programme.professeur import tour
from programme.test_correction_exercice import CORRECTION_EX1
from traitement_ia import service
from traitement_ia.models import TacheIA
from traitement_ia.tests.test_taches import ANALYSE, REGLAGES, BaseAsync, faux_sdk, traiter_tout


@override_settings(**REGLAGES)
class RepriseBase(BaseAsync):
    def nouveau_navigateur(self, eleve=None):
        api = APIClient()
        api.force_authenticate(eleve or self.eleve)
        return api

    def reprise(self, api=None, programme=None):
        r = (api or self.nouveau_navigateur()).get(f"/api/eleve/reprise/?programme={programme or self.programme.id}")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def lire(self):
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(analyse=ANALYSE)):
            tache = self.tache(self.deposer())
            traiter_tout()
        return tache, self.etat(tache)["corps"]["analyse"]

    def demander_correction(self, analyse):
        r = self.api.post("/api/eleve/correction/", {"programme": self.programme.id, "analyse": analyse}, format="json")
        return self.tache(r)

    def demarrer_seance(self, analyse):
        r = self.api.post("/api/eleve/professeur/seances/", {"programme": self.programme.id, "analyse": analyse}, format="json")
        t = self.tache(r)
        traiter_tout()
        return self.etat(t)["corps"]["seance"]


class RepriseLectureTests(RepriseBase):
    def test_apres_actualisation_la_lecture_et_l_analyse_sont_retrouvees_sans_appel(self):
        tache, analyse = self.lire()
        client = faux_sdk(analyse=ANALYSE)
        with mock.patch("anthropic.Anthropic", return_value=client):
            r1, r2 = self.reprise(), self.reprise()   # deux actualisations de suite
        self.assertEqual(client.appels, [])
        self.assertEqual(OperationIA.objects.count(), 1)   # rien de refacturé
        self.assertEqual((r1["lecture"]["statut"], r1["lecture"]["http"], r1["lecture"]["id"]), ("terminee", 200, str(tache.id)))
        self.assertEqual(r1["analyse"]["enonce"], analyse["enonce"])
        self.assertEqual(r1, r2)

    def test_lecture_en_cours_visible_avec_son_statut(self):
        tache = self.tache(self.deposer())
        r = self.reprise()
        self.assertEqual((r["lecture"]["statut"], r["analyse"]), ("en_attente", None))
        t = service.reclamer("w")
        self.assertEqual(self.reprise()["lecture"]["statut"], "en_cours")
        self.assertEqual(t.pk, tache.pk)


class RepriseCorrectionTests(RepriseBase):
    def test_correction_en_cours_puis_terminee_retrouvee_apres_actualisation(self):
        _, analyse = self.lire()
        client = faux_sdk(correction=CORRECTION_EX1)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.demander_correction(analyse)
            en_cours = self.reprise()                         # l'élève actualise PENDANT la correction
            self.assertEqual(en_cours["correction"]["statut"], "en_attente")
            self.assertEqual(en_cours["analyse"]["enonce"], analyse["enonce"])   # il retrouve aussi son énoncé confirmé
            self.assertEqual(client.appels, [])
            traiter_tout()
            fini = self.reprise()                             # puis APRÈS la fin
        self.assertEqual((fini["correction"]["statut"], fini["correction"]["http"]), ("terminee", 200))
        self.assertIn("correction", fini["correction"]["corps"])
        self.assertEqual(client.appels.count(resolution.NOM_OUTIL), 1)
        self.assertEqual(self.etat(tache)["http"], 200)

    def test_erreur_de_correction_retrouvee_telle_quelle(self):
        _, analyse = self.lire()
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk(correction=CORRECTION_EX1)):
            self.demander_correction(analyse)
        with override_settings(IA_INTERRUPTEUR_GLOBAL=False):   # coupé entre la mise en file et le traitement
            traiter_tout()
        c = self.reprise()["correction"]
        self.assertEqual((c["statut"], c["http"], c["corps"]["code"]), ("terminee", 503, "correction_desactivee"))

    def test_interruption_du_worker_issue_inconnue_erreur_claire_sans_second_appel_payant(self):
        _, analyse = self.lire()
        client = faux_sdk(correction=CORRECTION_EX1)
        with mock.patch("anthropic.Anthropic", return_value=client):
            tache = self.demander_correction(analyse)
            t = service.reclamer("A")
            with budget.tache(t.id, reprise=False), budget.contexte(utilisateur_id=self.eleve.id, exercice_cle="x"):
                budget.ouvrir(fonctionnalite="correction", modele="m", tokens_entree=1000, tokens_sortie_max=1000)   # appel parti, worker mort
            TacheIA.objects.filter(pk=tache.pk).update(verrou_jusqua=timezone.now() - timedelta(seconds=1))
            traiter_tout("B")
        self.assertEqual(client.appels, [])   # AUCUN second appel payant
        c = self.reprise()["correction"]
        self.assertEqual((c["statut"], c["http"], c["corps"]["code"]), ("terminee", 503, "resultat_inconnu"))
        self.assertIn("interrompu", c["corps"]["detail"])


class RepriseSeanceTests(RepriseBase):
    def test_la_seance_et_son_historique_survivent_a_l_actualisation(self):
        _, analyse = self.lire()
        client = faux_sdk()
        with mock.patch("anthropic.Anthropic", return_value=client):
            vue = self.demarrer_seance(analyse)
            r = self.api.post(f"/api/eleve/professeur/seances/{vue['seance']}/indice/", {"version": vue["version"]}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            avant = r.json()["seance"]
            appels = len(client.appels)
            apres = self.reprise(self.nouveau_navigateur())["seance"]       # nouveau navigateur / actualisation
        self.assertEqual(len(client.appels), appels)                       # reprise = lecture seule
        self.assertEqual(apres["seance"], avant["seance"])
        self.assertEqual(apres["version"], avant["version"])
        self.assertEqual(apres["messages"], avant["messages"])             # historique pédagogique autorisé
        self.assertEqual(apres["etape"]["indices_donnes"], avant["etape"]["indices_donnes"])
        self.assertEqual(apres["echanges_restants"], avant["echanges_restants"])
        self.assertEqual(apres["progression"], avant["progression"])
        for secret in ("plan", "attendu", "reference"):
            self.assertNotIn(secret, apres)

    def test_le_compteur_de_dix_interactions_et_les_quotas_survivent_a_l_actualisation(self):
        _, analyse = self.lire()
        client = faux_sdk()
        with mock.patch("anthropic.Anthropic", return_value=client), override_settings(IA_PROF_MAX_APPELS_IA=40):
            vue = self.demarrer_seance(analyse)
            for _ in range(6):
                r = self.api.post(f"/api/eleve/professeur/seances/{vue['seance']}/explication/", {"version": vue["version"], "type": "exemple"}, format="json")
                self.tache(r)
                traiter_tout()
                vue = self.reprise(self.nouveau_navigateur())["seance"]       # actualisation après CHAQUE interaction
            codes = []
            for _ in range(5):
                r = self.nouveau_navigateur().post(f"/api/eleve/professeur/seances/{vue['seance']}/explication/", {"version": vue["version"], "type": "exemple"}, format="json")
                t = self.tache(r)
                traiter_tout()
                e = self.etat(t)
                codes.append(e["http"])
                if e["http"] == 200:
                    vue = e["corps"]["seance"]
        self.assertEqual(codes, [200, 200, 200, 200, 429])                    # 6 + 4 = 10, la 11e est refusée
        self.assertEqual(client.appels.count(tour.NOM_OUTIL), 10)

    def test_seance_expiree_non_reprise(self):
        _, analyse = self.lire()
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk()):
            vue = self.demarrer_seance(analyse)
        cache.delete(f"prof:seance:{vue['seance']}")
        self.assertIsNone(self.reprise()["seance"])

    def test_isolation_entre_eleves_et_programmes(self):
        _, analyse = self.lire()
        with mock.patch("anthropic.Anthropic", return_value=faux_sdk()):
            vue = self.demarrer_seance(analyse)
        autre = creer_eleve("+22790000066", niveau=self.programme.niveau, serie=self.programme.serie)
        api_autre = self.nouveau_navigateur(autre)
        r = self.reprise(api_autre)
        self.assertEqual((r["seance"], r["analyse"], r["lecture"], r["correction"]), (None, None, None, None))
        self.assertEqual(api_autre.get(f"/api/eleve/professeur/seances/{vue['seance']}/").status_code, 404)
        self.assertEqual(api_autre.get("/api/eleve/taches/").json()["taches"], [])
        self.assertEqual(self.nouveau_navigateur().get("/api/eleve/reprise/?programme=99999").status_code, 404)
        self.assertEqual(self.nouveau_navigateur().get("/api/eleve/reprise/").status_code, 404)
        self.assertIn(APIClient().get(f"/api/eleve/reprise/?programme={self.programme.id}").status_code, (401, 403))


class ResultatsExpiresTests(RepriseBase):
    def test_apres_deux_heures_message_expire_sans_contenu_meme_avant_la_purge(self):
        tache, _ = self.lire()
        TacheIA.objects.filter(pk=tache.pk).update(expire_le=timezone.now() - timedelta(seconds=1))
        r = self.reprise()
        self.assertEqual(r["lecture"]["statut"], "expiree")
        self.assertNotIn("corps", r["lecture"])
        self.assertIsNone(r["analyse"])
        self.assertEqual(self.api.get(f"/api/eleve/taches/{tache.id}/").json()["statut"], "expiree")

    def test_la_purge_efface_le_contenu_mais_garde_la_trace_24_h(self):
        tache, _ = self.lire()
        TacheIA.objects.filter(pk=tache.pk).update(expire_le=timezone.now() - timedelta(hours=3))
        service.purger()
        t = TacheIA.objects.get(pk=tache.pk)
        self.assertEqual((t.resultat, t.donnees, t.kwargs), (None, {"programme": str(self.programme.id)}, {}))
        self.assertEqual(self.reprise()["lecture"]["statut"], "expiree")   # la trace garde le bon programme

    def test_duree_de_disponibilite_inchangee_deux_heures(self):
        self.assertEqual(settings.IA_TACHE_RESULTAT_SECONDES, 7200)


class ModeleRecommandeTests(RepriseBase):
    def test_modele_par_defaut_tarifie_et_transmis_tel_quel_au_sdk(self):
        source = open(settings.BASE_DIR / "config" / "settings.py", encoding="utf-8").read()
        self.assertIn("IA_MODELE = config('IA_MODELE', default='claude-sonnet-5-5')", source)   # modèle recommandé par défaut
        client = faux_sdk(analyse=ANALYSE)
        with override_settings(IA_MODELE="claude-sonnet-5-5", IA_TARIFS_USD=None), mock.patch("anthropic.Anthropic", return_value=client):
            self.assertGreater(tarifs.cout_usd("claude-sonnet-5-5", entree=1_000_000, sortie=0), 0)
            self.tache(self.deposer())
            traiter_tout()
        self.assertEqual(client.messages.create.call_args.kwargs["model"], "claude-sonnet-5-5")
