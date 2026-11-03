"""Aides de test : tarifs fictifs, élève de test, faux client Anthropic. AUCUN appel réseau."""

from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from comptes.models import User

TARIF_TEST = {"entree": "2", "sortie": "10", "cache_ecriture_5m": "2.5", "cache_ecriture_1h": "4", "cache_lecture": "0.2"}
MODELES_DE_TEST = ("m", "modele-de-base", "modele-de-correction", "modele-test")
TARIFS_TEST = {nom: dict(TARIF_TEST) for nom in MODELES_DE_TEST}


def creer_eleve(telephone="+22790000099", **extra):
    return User.objects.create_user(
        telephone, password="Motdepasse-2026", prenom="E", nom="L",
        role=User.Role.ELEVE, statut=User.Statut.ACTIF, **extra,
    )


def faux_client(*, entree=1000, sortie=500, effets=None, outil="enregistrer_analyse", entree_outil=None, stop_reason="tool_use", usage=True):
    """Faux client `anthropic.Anthropic` : compte les appels, renvoie une réponse à outil (ou lève `effets`)."""
    reponse = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name=outil, input=entree_outil if entree_outil is not None else {"ok": True})],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=entree, output_tokens=sortie) if usage else None,
    )
    client = mock.Mock()
    if effets is not None:
        client.messages.create.side_effect = effets
    else:
        client.messages.create.return_value = reponse
    return client


def fcfa(usd_par_million_entree, entree, usd_par_million_sortie, sortie, taux=600, marge="0.10"):
    usd = (Decimal(entree) * Decimal(str(usd_par_million_entree)) + Decimal(sortie) * Decimal(str(usd_par_million_sortie))) / Decimal(1_000_000)
    return (usd * Decimal(taux) * (1 + Decimal(marge))).quantize(Decimal("0.0001"))


def creer_programme_maths():
    """(élève, programme de maths Terminale C) : ce qu'il faut pour appeler les vraies vues."""
    from programme.models import Cycle, Matiere, Niveau, Programme, Serie

    cycle = Cycle.objects.create(nom="Second cycle", ordre=2)
    tle = Niveau.objects.create(cycle=cycle, nom="Terminale", ordre=7)
    serie = Serie.objects.create(niveau=tle, nom="C")
    maths = Matiere.objects.create(nom="Mathématiques")
    prog = Programme.objects.create(matiere=maths, niveau=tle, serie=serie)
    eleve = creer_eleve("+22790000055", niveau=tle, serie=serie)
    return eleve, prog
