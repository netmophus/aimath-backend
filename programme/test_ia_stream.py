"""POST /api/admin/ia/generer/ en streaming SSE (contre le H12 Heroku).

Aucun appel réseau : faux client Anthropic. Vérifie surtout que
  - SANS `stream` le contrat historique est inchangé (JSON d'un bloc) ;
  - AVEC `stream: true` la réponse est un flux SSE dont l'événement "fin"
    porte exactement le même corps que la réponse JSON ;
  - le budget IA est soldé (succès, coupure du client, erreur du SDK) ;
  - un refus avant flux (budget épuisé) reste une vraie erreur HTTP JSON.
"""

import json
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from budget_ia import service as budget
from budget_ia.models import BudgetMensuel, OperationIA
from budget_ia.tests.outils import TARIFS_TEST
from comptes.models import User

from .models import Chapitre, Cycle, Lecon, Matiere, Niveau, Notion, Programme, Serie, Theme

SOUS_REGLAGES = override_settings(
    IA_TARIFS_USD=TARIFS_TEST, ANTHROPIC_API_KEY="cle-factice", IA_MODELE="m", IA_FOURNISSEUR="anthropic",
    BUDGET_IA_PLAFOND_ACTIF=True, BUDGET_IA_SEUIL_OPERATIONNEL_FCFA=90000,
)


def _evt_texte(texte):
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=texte))


def _evt_autre():
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="thinking_delta", thinking="..."))


class _FauxFlux:
    def __init__(self, evenements, texte_final, stop_reason="end_turn", erreur=None):
        self._evenements = evenements
        self._erreur = erreur
        self._final = SimpleNamespace(
            content=[SimpleNamespace(type="text", text=texte_final)],
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for e in self._evenements:
            yield e
        if self._erreur:
            raise self._erreur

    def get_final_message(self):
        return self._final


def faux_client_flux(flux):
    client = mock.Mock()
    client.messages.stream.return_value = flux
    return client


def lire_sse(reponse):
    """Concatène le flux, renvoie la liste des événements JSON (les commentaires ": ..." sont ignorés)."""
    brut = b"".join(reponse.streaming_content).decode("utf-8")
    evenements = []
    for bloc in brut.split("\n\n"):
        if bloc.startswith("data: "):
            evenements.append(json.loads(bloc[len("data: "):]))
    return brut, evenements


@SOUS_REGLAGES
class GenerationFluxTests(TestCase):
    def setUp(self):
        cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
        niveau = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
        serie = Serie.objects.create(niveau=niveau, nom="C")
        matiere = Matiere.objects.create(nom="Mathématiques")
        prog = Programme.objects.create(matiere=matiere, niveau=niveau, serie=serie)
        theme = Theme.objects.create(programme=prog, titre="Arithmétique", ordre=1)
        chapitre = Chapitre.objects.create(theme=theme, titre="Divisibilité", ordre=1)
        self.notion = Notion.objects.create(chapitre=chapitre, titre="PGCD", ordre=1)
        # Leçon modèle exigée par les prompts (réglage IA_NOTION_MODELE_ID) : ici, celle de la notion elle-même.
        Lecon.objects.create(notion=self.notion, titre="Modèle")
        self.admin = User.objects.create_user(
            "+22790000001", password="Motdepasse-2026", prenom="A", nom="D",
            role=User.Role.ADMIN, statut=User.Statut.ACTIF,
        )
        self.api = APIClient()
        self.api.force_authenticate(self.admin)

    def post(self, client, **extra):
        corps = {"notion_id": self.notion.id, "section": "sujet_examen", **extra}
        with mock.patch("anthropic.Anthropic", return_value=client), override_settings(IA_NOTION_MODELE_ID=self.notion.id):
            return self.api.post("/api/admin/ia/generer/", corps, format="json")

    def test_sans_stream_contrat_historique_inchange(self):
        client = faux_client_flux(None)
        client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Durée : 1 heure")], stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
        )
        r = self.post(client)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(r.json(), {"tronque": False, "contenu": "Durée : 1 heure"})
        client.messages.stream.assert_not_called()

    def test_stream_emet_des_deltas_puis_fin_identique_au_json(self):
        flux = _FauxFlux([_evt_texte("Durée : "), _evt_autre(), _evt_texte("1 heure")], "Durée : 1 heure")
        r = self.post(faux_client_flux(flux), stream=True)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/event-stream"))
        self.assertEqual(r["Cache-Control"], "no-cache")
        brut, evenements = lire_sse(r)
        self.assertTrue(brut.startswith(": ouverture\n\n"))  # premier octet immédiat
        self.assertEqual([e["type"] for e in evenements], ["delta", "delta", "fin"])
        self.assertEqual("".join(e["texte"] for e in evenements if e["type"] == "delta"), "Durée : 1 heure")
        self.assertEqual(evenements[-1], {"type": "fin", "tronque": False, "contenu": "Durée : 1 heure"})

    def test_reponse_streamee_porte_les_memes_en_tetes_cors_que_le_json(self):
        origine = "http://localhost:3000"  # dans CORS_ALLOWED_ORIGINS : pas d'élargissement de la config
        corps = {"notion_id": self.notion.id, "section": "sujet_examen", "stream": True}
        flux = _FauxFlux([_evt_texte("abc")], "abc")
        with mock.patch("anthropic.Anthropic", return_value=faux_client_flux(flux)), override_settings(IA_NOTION_MODELE_ID=self.notion.id):
            r = self.api.post("/api/admin/ia/generer/", corps, format="json", HTTP_ORIGIN=origine)
        self.assertEqual(r["Access-Control-Allow-Origin"], origine)
        lire_sse(r)

    def test_stream_solde_le_budget_avec_la_consommation_reelle(self):
        flux = _FauxFlux([_evt_texte("abc")], "abc")
        lire_sse(self.post(faux_client_flux(flux), stream=True))
        op = OperationIA.objects.get()
        self.assertEqual((op.statut, op.fonctionnalite, op.tokens_entree, op.tokens_sortie), ("terminee", "contenu_admin", 1000, 500))
        self.assertEqual(BudgetMensuel.objects.get().reserve_fcfa, Decimal(0))

    def test_stream_tronque_signale_tronque(self):
        flux = _FauxFlux([_evt_texte("abc")], "abc", stop_reason="max_tokens")
        _, evenements = lire_sse(self.post(faux_client_flux(flux), stream=True))
        fin = evenements[-1]
        self.assertTrue(fin["tronque"])
        self.assertIn("message", fin)

    def test_stream_exercices_renvoie_le_json_parse(self):
        exos = json.dumps([{"enonce": "E", "corrige": "C", "difficulte": "facile"}])
        flux = _FauxFlux([_evt_texte(exos)], exos)
        _, evenements = lire_sse(self.post(faux_client_flux(flux), stream=True, section="exercices"))
        self.assertEqual(evenements[-1]["type"], "fin")
        self.assertEqual(evenements[-1]["exercices"][0]["enonce"], "E")

    def test_erreur_sdk_en_cours_de_flux_donne_un_evenement_erreur_et_solde_le_budget(self):
        import anthropic

        erreur = anthropic.APIConnectionError(request=mock.Mock())
        flux = _FauxFlux([_evt_texte("abc")], "abc", erreur=erreur)
        _, evenements = lire_sse(self.post(faux_client_flux(flux), stream=True))
        self.assertEqual(evenements[0]["type"], "delta")
        self.assertEqual(evenements[-1]["type"], "erreur")
        self.assertEqual(evenements[-1]["status"], 502)
        op = OperationIA.objects.get()
        self.assertEqual(op.statut, "inconnue")  # connexion coupée : le fournisseur a pu facturer, on compte la réservation
        self.assertEqual(BudgetMensuel.objects.get().reserve_fcfa, Decimal(0))

    def test_client_qui_se_deconnecte_solde_le_budget(self):
        """Le client part en plein flux : la vue ferme le générateur (finally de _reponse_sse),
        ce qui doit solder la réservation (résultat inconnu : le fournisseur a pu facturer)."""
        from .ia.service import generer_section_flux

        flux = _FauxFlux([_evt_texte("a"), _evt_texte("b"), _evt_texte("c")], "abc")
        with mock.patch("anthropic.Anthropic", return_value=faux_client_flux(flux)), override_settings(IA_NOTION_MODELE_ID=self.notion.id):
            evenements = generer_section_flux(self.notion, "sujet_examen")
            self.assertEqual(next(evenements), ("delta", "a"))
            self.assertEqual(OperationIA.objects.get().statut, "reservee")
            evenements.close()  # GeneratorExit
        op = OperationIA.objects.get()
        self.assertEqual(op.statut, "inconnue")
        self.assertEqual(BudgetMensuel.objects.get().reserve_fcfa, Decimal(0))

    def test_budget_epuise_avant_flux_reste_une_erreur_http_json(self):
        BudgetMensuel.objects.create(mois=budget.mois_et_jour()[0], depense_fcfa=Decimal("90000"))
        client = faux_client_flux(_FauxFlux([], ""))
        r = self.post(client, stream=True)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r["Content-Type"], "application/json")
        client.messages.stream.assert_not_called()

    def test_cle_absente_avant_flux_donne_500_json(self):
        with override_settings(ANTHROPIC_API_KEY=""):
            r = self.post(faux_client_flux(_FauxFlux([], "")), stream=True)
        self.assertEqual(r.status_code, 500)

    def test_stream_refuse_aux_non_admins(self):
        eleve = User.objects.create_user(
            "+22790000002", password="Motdepasse-2026", prenom="E", nom="L",
            role=User.Role.ELEVE, statut=User.Statut.ACTIF,
        )
        api = APIClient()
        api.force_authenticate(eleve)
        r = api.post("/api/admin/ia/generer/", {"notion_id": self.notion.id, "section": "cours", "stream": True}, format="json")
        self.assertEqual(r.status_code, 403)
