"""
Cycle de vie des tâches IA : mise en file, réclamation atomique par un worker, exécution, résultat, purge.

Sécurité financière : une tâche ne contourne AUCUN contrôle. Les quotas, la réservation du coût et le plafond mensuel
sont appliqués par `budget_ia.service.ouvrir()` au moment de l'appel au fournisseur, donc dans le worker, comme dans
le mode synchrone. Une reprise après interruption passe par les mêmes contrôles ; au plus `IA_TACHE_TENTATIVES_MAX`
essais, et une réservation laissée ouverte par le worker interrompu reste comptée comme dépense (voir budget_ia).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from django.utils.module_loading import import_string
from rest_framework.exceptions import APIException

from budget_ia import service as budget
from programme.ia.exceptions import RefusBudget

from .models import FichierTacheIA, TacheIA

logger = logging.getLogger(__name__)
S = TacheIA.Statut
ACTIVES = (S.EN_ATTENTE, S.EN_COURS)
MESSAGE_INDISPONIBLE = "Service temporairement indisponible. Réessaie plus tard."


class TropDeTaches(RefusBudget):
    code = "trop_de_taches"
    message = "Une analyse est déjà en cours. Patiente avant d'en lancer une autre."


class DemandeTache:
    """Ce que `preparer()` d'une vue demande de mettre en file."""

    def __init__(self, *, type_tache: str, cle_requete: str, donnees: dict, fichiers: list | None = None):
        self.type_tache, self.cle_requete, self.donnees, self.fichiers = type_tache, cle_requete, donnees, fichiers or []


def _json(valeur):
    return json.loads(json.dumps(valeur, cls=DjangoJSONEncoder))


def mettre_en_file(*, utilisateur, vue, kwargs: dict, demande: DemandeTache) -> TacheIA:
    """Idempotent : un double clic ou un renvoi pendant qu'une tâche identique est active renvoie CETTE tâche."""
    maintenant = timezone.now()
    try:
        with transaction.atomic():
            actives = TacheIA.objects.filter(utilisateur=utilisateur, statut__in=ACTIVES).count()
            if actives >= int(settings.IA_TACHES_ACTIVES_MAX_PAR_ELEVE):
                raise TropDeTaches()
            tache = TacheIA.objects.create(
                utilisateur=utilisateur, type=demande.type_tache, vue=f"{vue.__class__.__module__}.{vue.__class__.__name__}",
                kwargs=_json(kwargs), donnees=_json(demande.donnees), cle_requete=demande.cle_requete[:64], disponible_le=maintenant,
            )
            FichierTacheIA.objects.bulk_create([
                FichierTacheIA(tache=tache, ordre=i, champ=champ, nom=nom, type_mime=type_mime, octets=octets)
                for i, (champ, nom, type_mime, octets) in enumerate(demande.fichiers)
            ])
        return tache
    except IntegrityError:
        existante = TacheIA.objects.filter(
            utilisateur=utilisateur, type=demande.type_tache, cle_requete=demande.cle_requete[:64], statut__in=ACTIVES
        ).first()
        if existante is None:  # terminée entre-temps : on réessaie une fois
            return mettre_en_file(utilisateur=utilisateur, vue=vue, kwargs=kwargs, demande=demande)
        return existante


def reclamer(travailleur: str) -> TacheIA | None:
    """Prend UNE tâche (SKIP LOCKED : deux workers ne prennent jamais la même). Reprend aussi une tâche dont le bail a
    expiré (worker interrompu), dans la limite des tentatives."""
    maintenant = timezone.now()
    bail = timedelta(seconds=int(settings.IA_TACHE_BAIL_SECONDES))
    while True:
        with transaction.atomic():
            tache = (
                TacheIA.objects.select_for_update(skip_locked=True)
                .filter(Q(statut=S.EN_ATTENTE, disponible_le__lte=maintenant) | Q(statut=S.EN_COURS, verrou_jusqua__lt=maintenant))
                .order_by("cree_le").first()
            )
            if tache is None:
                return None
            if tache.tentatives >= int(settings.IA_TACHE_TENTATIVES_MAX):
                _clore(tache, S.ECHOUEE, 503, {"detail": MESSAGE_INDISPONIBLE, "code": "tache_abandonnee"}, "abandonnee")
                continue
            tache.statut, tache.tentatives = S.EN_COURS, tache.tentatives + 1
            tache.verrou_jusqua, tache.travailleur, tache.demarre_le = maintenant + bail, travailleur[:60], maintenant
            tache.save(update_fields=["statut", "tentatives", "verrou_jusqua", "travailleur", "demarre_le"])
            return tache


def _clore(tache: TacheIA, statut: str, http: int, corps, code: str = "") -> None:
    tache.statut, tache.resultat_http, tache.resultat, tache.code_erreur = statut, http, _json(corps), code
    tache.termine_le = timezone.now()
    tache.expire_le = tache.termine_le + timedelta(seconds=int(settings.IA_TACHE_RESULTAT_SECONDES))
    tache.verrou_jusqua = None
    tache.save()
    FichierTacheIA.objects.filter(tache=tache).delete()  # les fichiers de l'élève ne survivent pas à la tâche


def _requete(tache: TacheIA):
    """Reconstruit la requête d'origine (mêmes champs, mêmes fichiers) pour que la VRAIE vue la valide et l'exécute."""
    donnees = tache.donnees or {}
    fichiers = list(FichierTacheIA.objects.filter(tache=tache))
    if fichiers:
        multi = MultiValueDict({k: [str(v)] for k, v in donnees.items()})
        for f in fichiers:
            multi.appendlist(f.champ, SimpleUploadedFile(f.nom, bytes(f.octets), content_type=f.type_mime))
        data = multi
    else:
        data = donnees
    return SimpleNamespace(user=tache.utilisateur, data=data, execution_tache=True, method="POST", query_params={})


def executer(tache: TacheIA) -> TacheIA:
    """Exécute la tâche réclamée et enregistre le résultat HTTP EXACT que la requête synchrone aurait produit."""
    from comptes.models import User

    utilisateur = tache.utilisateur
    if utilisateur.role != User.Role.ELEVE or utilisateur.statut != User.Statut.ACTIF:
        _clore(tache, S.TERMINEE, 403, {"detail": "Accès refusé."}, "non_autorise")
        return tache
    try:
        vue = import_string(tache.vue)()
        requete = _requete(tache)
        vue.request, vue.kwargs, vue.args = requete, dict(tache.kwargs), ()
        with budget.tache(tache.id, reprise=tache.tentatives > 1):
            reponse = vue.executer(requete, **tache.kwargs)
        http, corps = reponse.status_code, getattr(reponse, "data", None)
    except Http404:
        http, corps = 404, {"detail": "Introuvable."}
    except APIException as exc:
        http, corps = exc.status_code, exc.detail
    except RefusBudget as exc:
        http, corps = exc.statut_http, {"detail": exc.args[0], "code": exc.code}
    except Exception:  # noqa: BLE001 : jamais de contenu ni de trace côté élève
        logger.exception("tâche IA %s : erreur inattendue", tache.id)
        http, corps = 500, {"detail": MESSAGE_INDISPONIBLE}

    # Un verrou « déjà en cours » laissé par un worker interrompu : on réessaie un peu plus tard (tentatives bornées).
    code = corps.get("code") if isinstance(corps, dict) else None
    if http == 409 and code in (None, "deja_en_cours") and tache.tentatives < int(settings.IA_TACHE_TENTATIVES_MAX):
        tache.statut, tache.disponible_le, tache.verrou_jusqua = S.EN_ATTENTE, timezone.now() + timedelta(seconds=45), None
        tache.save(update_fields=["statut", "disponible_le", "verrou_jusqua"])
        return tache
    _clore(tache, S.TERMINEE, http, corps)
    return tache


def _expiree(tache: TacheIA) -> bool:
    return tache.statut in (S.TERMINEE, S.ECHOUEE) and tache.expire_le is not None and tache.expire_le < timezone.now()


def etat_public(tache: TacheIA) -> dict:
    """Ce que le navigateur reçoit : état, puis (une fois terminée) le statut HTTP et le corps de la réponse.
    Passé le délai de conservation, le résultat n'est JAMAIS renvoyé, même si la purge n'a pas encore tourné."""
    if _expiree(tache):
        return {"id": str(tache.id), "statut": "expiree"}
    corps = {"id": str(tache.id), "statut": tache.statut}
    if tache.statut in (S.TERMINEE, S.ECHOUEE):
        corps.update({"http": tache.resultat_http, "corps": tache.resultat})
    return corps


def _descriptif(t: TacheIA) -> dict:
    return {**etat_public(t), "type": t.type, "cree_le": t.cree_le.isoformat(), "programme": (t.donnees or {}).get("programme")}


def taches_de(utilisateur, limite: int = 20) -> list[dict]:
    """Tâches RÉCENTES de l'élève connecté (jamais celles d'un autre) : actives, terminées et non expirées, ou expirées
    depuis moins de IA_TACHE_TRACE_SECONDES (trace sans contenu : l'élève lit « résultat expiré »)."""
    limite_trace = timezone.now() - timedelta(seconds=int(settings.IA_TACHE_TRACE_SECONDES))
    qs = TacheIA.objects.filter(utilisateur=utilisateur).filter(
        Q(statut__in=ACTIVES) | Q(expire_le__gte=limite_trace)
    ).order_by("-cree_le")[:limite]
    return [_descriptif(t) for t in qs]


def reprise(utilisateur, programme_id: int) -> dict:
    """Tout ce qu'il faut pour reprendre après actualisation, pour UN programme de l'élève : dernière analyse (énoncé lu),
    dernière lecture, dernière correction, séance fahimta ai en cours. Lecture seule : AUCUN appel au fournisseur."""
    from programme.professeur import seance as seance_mod

    limite_trace = timezone.now() - timedelta(seconds=int(settings.IA_TACHE_TRACE_SECONDES))
    base = TacheIA.objects.filter(utilisateur=utilisateur).filter(Q(statut__in=ACTIVES) | Q(expire_le__gte=limite_trace)).order_by("-cree_le")
    taches = [t for t in base[:60] if str((t.donnees or {}).get("programme")) == str(programme_id)]

    def dernier(type_):
        return next((t for t in taches if t.type == type_), None)

    analyse = None
    for t in taches:
        if _expiree(t):
            continue
        if t.type == "lecture" and t.statut == S.TERMINEE and t.resultat_http == 200 and isinstance(t.resultat, dict) and t.resultat.get("analyse"):
            analyse = t.resultat["analyse"]
        elif t.type in ("correction", "seance_demarrer") and isinstance((t.donnees or {}).get("analyse"), dict):
            analyse = t.donnees["analyse"]
        if analyse:
            break
    lecture, correction = dernier("lecture"), dernier("correction")
    etat_seance = seance_mod.courante_de(utilisateur.id, programme_id)
    return {
        "analyse": analyse,
        "lecture": _descriptif(lecture) if lecture else None,
        "correction": _descriptif(correction) if correction else None,
        "seance": seance_mod.vue_publique(etat_seance) if etat_seance else None,
    }


def purger() -> int:
    """Deux temps : à l'expiration le CONTENU est effacé (énoncé, correction, analyse), la trace reste IA_TACHE_TRACE_SECONDES ;
    ensuite la ligne disparaît."""
    maintenant = timezone.now()
    for t in TacheIA.objects.filter(expire_le__lt=maintenant):   # idempotent ; quelques lignes seulement (fenêtre de 24 h)
        t.resultat, t.donnees, t.kwargs = None, {"programme": (t.donnees or {}).get("programme")}, {}
        t.save(update_fields=["resultat", "donnees", "kwargs"])
    n, _ = TacheIA.objects.filter(expire_le__lt=maintenant - timedelta(seconds=int(settings.IA_TACHE_TRACE_SECONDES))).delete()
    return n


def identifiant_travailleur() -> str:
    return uuid.uuid4().hex[:8]
