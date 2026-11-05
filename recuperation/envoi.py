"""Worker d'envoi des codes de récupération (file persistante PostgreSQL `EnvoiCodeSms`).

Indépendant des workers fahimta ai (`traiter_taches_ia`) et Communications (`traiter_communications`) : autre process
Heroku, autres tables, autre budget, aucune file partagée.

Garanties :
- AU PLUS UN envoi par ligne. La prise en charge (en_attente -> en_cours) est validée en base AVANT l'appel au
  fournisseur, sous verrou de ligne `SELECT ... FOR UPDATE SKIP LOCKED` : deux workers simultanés ne prennent jamais la
  même ligne.
- Un résultat incertain (délai de lecture dépassé, exception inattendue) ou une ligne restée « en cours » trop
  longtemps (worker tué en plein envoi) passe à `incertain` et N'EST JAMAIS RENVOYÉ automatiquement : le SMS est
  peut-être parti. L'élève peut redemander un code (délai et plafonds applicables).
- Un nouvel essai automatique n'a lieu que si RIEN n'a pu partir (fournisseur injoignable, configuration incomplète),
  au plus OTP_MAX_ESSAIS_ENVOI fois, tant que le code est valable.
- Le code est reconstitué au dernier moment (secret dédié + sel de la demande) ; ni le code ni le texte ne sont
  journalisés ni stockés. Les journaux ne portent que des identifiants de ligne et des états.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from comptes.sms import envoyer_sms_detail

from . import services
from .models import BattementWorkerOtp, EnvoiCodeSms

logger = logging.getLogger(__name__)
Etat = EnvoiCodeSms.Etat


def battre() -> None:
    """Signe de vie : sans lui, les demandes de code répondent « service indisponible » (voir services)."""
    BattementWorkerOtp.objects.update_or_create(pk=1, defaults={"dernier_battement": timezone.now()})


def peut_envoyer() -> bool:
    if not settings.OTP_SMS_ACTIFS:
        return False
    try:
        services.cle_code()
    except services.ConfigurationOtpManquante:
        return False
    return True


def nettoyer() -> dict:
    """Interruptions et périmés. À appeler avant chaque lot."""
    maintenant = timezone.now()
    interrompus = EnvoiCodeSms.objects.filter(
        etat=Etat.EN_COURS,
        debut_traitement_le__lt=maintenant - timedelta(seconds=settings.OTP_DELAI_INTERRUPTION_SECONDES),
    ).update(etat=Etat.INCERTAIN, termine_le=maintenant, detail="interrompu")
    expires = EnvoiCodeSms.objects.filter(etat=Etat.EN_ATTENTE, expire_le__lte=maintenant).update(
        etat=Etat.EXPIRE, termine_le=maintenant, detail="expire")
    return {"interrompus": interrompus, "expires": expires}


def _prendre():
    """Réserve la prochaine ligne due. Renvoie (id, telephone, demande) ou None. Les lignes périmées, remplacées ou dont
    la demande est clôturée passent à `expire` sans rien envoyer."""
    with transaction.atomic():
        envoi = (EnvoiCodeSms.objects.select_for_update(skip_locked=True, of=("self",))
                 .select_related("demande")
                 .filter(etat=Etat.EN_ATTENTE, disponible_le__lte=timezone.now())
                 .order_by("id").first())
        if envoi is None:
            return None
        maintenant = timezone.now()
        if envoi.expire_le <= maintenant or envoi.demande.cloturee_le is not None:
            envoi.etat, envoi.termine_le, envoi.detail = Etat.EXPIRE, maintenant, "perime"
            envoi.save(update_fields=["etat", "termine_le", "detail"])
            return "ignore"
        envoi.etat = Etat.EN_COURS
        envoi.debut_traitement_le = maintenant
        envoi.tentatives += 1
        envoi.save(update_fields=["etat", "debut_traitement_le", "tentatives"])
        return envoi


def _conclure(envoi, resultat: str, detail: str) -> None:
    """Enregistre l'issue, uniquement si la ligne est encore « en cours » (jamais d'écrasement après interruption)."""
    maintenant = timezone.now()
    base = EnvoiCodeSms.objects.filter(pk=envoi.pk, etat=Etat.EN_COURS)
    if resultat == "accepte":
        base.update(etat=Etat.ACCEPTE, termine_le=maintenant, detail=detail[:40])
    elif resultat == "incertain":
        base.update(etat=Etat.INCERTAIN, termine_le=maintenant, detail=detail[:40])
    elif resultat == "non_envoye":
        # Rien n'est parti : nouvel essai différé, borné en nombre et par la validité du code.
        prochain = maintenant + timedelta(seconds=5 * envoi.tentatives)
        if envoi.tentatives < settings.OTP_MAX_ESSAIS_ENVOI and prochain < envoi.expire_le:
            base.update(etat=Etat.EN_ATTENTE, disponible_le=prochain, debut_traitement_le=None, detail=detail[:40])
        else:
            base.update(etat=Etat.ECHEC, termine_le=maintenant, detail=detail[:40])
    else:   # "refuse" : refus définitif du fournisseur
        base.update(etat=Etat.ECHEC, termine_le=maintenant, detail=detail[:40])


def traiter_un() -> bool:
    """Traite au plus une ligne. Faux quand il n'y a plus rien à faire maintenant."""
    envoi = _prendre()
    if envoi is None:
        return False
    if envoi == "ignore":
        return True
    try:
        code = services.code_pour(envoi.demande)
        resultat, detail = envoyer_sms_detail(envoi.telephone, services.texte_sms(code))
        del code
    except Exception:   # noqa: BLE001 - aucune trace contenant le code ou le texte
        resultat, detail = "incertain", "exception"
    logger.info("Envoi code récupération #%s : %s (%s)", envoi.pk, resultat, detail)
    _conclure(envoi, resultat, detail)
    battre()
    return True


def passage_envoi_otp(maximum: int = 50) -> int:
    """Un passage : nettoyage, signe de vie, puis jusqu'à `maximum` envois. Ne fait rien si le service n'est pas activé
    ou si le secret manque (les lignes restent en attente, puis expirent)."""
    if not peut_envoyer():
        return 0
    nettoyer()
    battre()
    traites = 0
    while traites < maximum and traiter_un():
        traites += 1
    return traites


def etat_file() -> dict:
    lignes = {e.value: 0 for e in Etat}
    for etat in EnvoiCodeSms.objects.values_list("etat", flat=True):
        lignes[etat] += 1
    return lignes
