"""Récupération de mot de passe par code SMS (OTP) et limites de débit partagées.

Principes :
- Réponse NEUTRE : la demande de code répond pareil que le numéro ait un compte ou non, et les limites s'appliquent
  identiquement (une ligne d'événement est écrite dans tous les cas). L'envoi du SMS n'a pas lieu ici : une ligne de la
  file persistante `EnvoiCodeSms` est écrite dans la même transaction, et le worker dédié `traiter_envoi_codes_otp`
  l'envoie (voir envoi.py). La durée de la réponse ne dépend donc ni du fournisseur SMS ni de l'existence du compte.
- Le code (6 chiffres) n'est JAMAIS stocké : il se reconstitue par HMAC-SHA256 d'un secret dédié (OTP_CLE_SECRETE,
  absent de la base) sur l'identifiant de la demande et un sel aléatoire propre à la demande. L'autorisation (jeton
  aléatoire) n'est stockée que sous forme de HMAC. Comparaisons en temps constant ; ni l'un ni l'autre n'est journalisé.
- Limites en PostgreSQL (tables), pas en mémoire locale : valables pour tous les dynos et après redémarrage. Un verrou
  consultatif transactionnel par numéro sérialise les demandes simultanées.
- Service d'authentification : aucune dépendance au module Communications (campagnes, plafond de 15 000 FCFA, worker).
"""

import hashlib
import hmac
import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from communications.segments import compter as compter_segments   # fonction pure, en lecture seule
from comptes.sms import normaliser_telephone_sms

from .models import BattementWorkerOtp, DemandeReinitialisation, EnvoiCodeSms, EvenementRecuperation

logger = logging.getLogger(__name__)
User = get_user_model()

E = EvenementRecuperation.Type
MESSAGE_NEUTRE = "Si ce numéro est associé à un compte, un code sera envoyé."
MESSAGE_CODE_INVALIDE = "Code invalide ou expiré."
MESSAGE_AUTORISATION_INVALIDE = "Autorisation invalide ou expirée. Recommence la récupération."
MESSAGE_INDISPONIBLE = "Le service d'envoi du code est temporairement indisponible. Réessaie dans quelques minutes."


class ErreurRecuperation(Exception):
    def __init__(self, message: str, statut_http: int = 400, code: str = "", retry_after: int | None = None, details=None):
        super().__init__(message)
        self.message, self.statut_http, self.code, self.retry_after, self.details = message, statut_http, code, retry_after, details


# --------------------------------------------------------------------------- outils

def _cle_hmac() -> bytes:
    return hashlib.sha256(b"fahimta-recuperation|" + settings.SECRET_KEY.encode()).digest()


def hmac_hex(valeur: str) -> str:
    return hmac.new(_cle_hmac(), valeur.encode(), hashlib.sha256).hexdigest()


def cle_numero(numero: str) -> str:
    return hmac_hex("tel|" + numero)


def ip_client(request) -> str | None:
    """Adresse réelle du client derrière le routeur Heroku : le routeur AJOUTE l'adresse qui l'a contacté à la FIN de
    X-Forwarded-For ; les entrées précédentes sont fournies par le client (falsifiables) et sont donc ignorées."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        dernier = xff.split(",")[-1].strip()
        if dernier:
            return dernier
    return request.META.get("REMOTE_ADDR") or None


def normaliser_numero(brut: str) -> str:
    numero = normaliser_telephone_sms(brut or "")
    if not re.fullmatch(r"227\d{8}", numero):
        raise ErreurRecuperation("Numéro de téléphone invalide : saisis les 8 chiffres du numéro.", 400, "numero_invalide")
    return numero


def _trouver_utilisateur(numero: str):
    national = numero[3:]
    candidats = [f"+{numero}", numero, national, f"0{national}", f"+227 {national}"]
    return User.objects.filter(telephone__in=candidats).order_by("id").first()


def _verrou(cle: str) -> None:
    """Verrou consultatif transactionnel par clé : deux demandes simultanées pour le même numéro s'exécutent à la suite."""
    if connection.vendor == "postgresql":
        with connection.cursor() as c:
            c.execute("SELECT pg_advisory_xact_lock(%s)", [int(cle[:15], 16)])


def _depuis(delta):
    return timezone.now() - delta


def _compter(type_, delta, **filtres) -> int:
    return EvenementRecuperation.objects.filter(type=type_, cree_le__gte=_depuis(delta), **filtres).count()


def _retry_apres(type_, delta, **filtres) -> int:
    plus_ancien = (EvenementRecuperation.objects.filter(type=type_, cree_le__gte=_depuis(delta), **filtres)
                   .order_by("cree_le").first())
    if not plus_ancien:
        return 1
    return max(1, int((plus_ancien.cree_le + delta - timezone.now()).total_seconds()) + 1)


def _purger() -> None:
    EvenementRecuperation.objects.filter(cree_le__lt=_depuis(timedelta(days=35))).delete()
    DemandeReinitialisation.objects.filter(cree_le__lt=_depuis(timedelta(days=2)), envoi__isnull=True).delete()
    EnvoiCodeSms.objects.filter(cree_le__lt=_depuis(timedelta(days=35))).delete()


def enregistrer_echec(type_: str, cle: str = "", ip: str | None = None) -> None:
    EvenementRecuperation.objects.create(type=type_, cle=cle, ip=ip)


# --------------------------------------------------------------------------- limites des changements volontaires

def verifier_blocage_changement(utilisateur, ip: str | None) -> None:
    """5 mots de passe actuels erronés en 15 minutes verrouillent le changement volontaire de CE compte (429)."""
    cle = hmac_hex(f"chg|{utilisateur.pk}")
    fenetre = timedelta(minutes=15)
    if _compter(E.CHANGEMENT_ECHEC, fenetre, cle=cle) >= settings.OTP_MAX_TENTATIVES:
        raise ErreurRecuperation("Trop de tentatives. Réessaie dans quelques minutes.", 429, "trop_de_tentatives",
                                 _retry_apres(E.CHANGEMENT_ECHEC, fenetre, cle=cle))
    if ip and _compter(E.CHANGEMENT_ECHEC, timedelta(hours=1), ip=ip) >= 3 * settings.OTP_MAX_TENTATIVES:
        raise ErreurRecuperation("Trop de tentatives. Réessaie plus tard.", 429, "trop_de_tentatives",
                                 _retry_apres(E.CHANGEMENT_ECHEC, timedelta(hours=1), ip=ip))


def enregistrer_echec_changement(utilisateur, ip: str | None) -> None:
    enregistrer_echec(E.CHANGEMENT_ECHEC, hmac_hex(f"chg|{utilisateur.pk}"), ip)


def effacer_echecs_changement(utilisateur) -> None:
    EvenementRecuperation.objects.filter(type=E.CHANGEMENT_ECHEC, cle=hmac_hex(f"chg|{utilisateur.pk}")).delete()


# --------------------------------------------------------------------------- étape 1 : demander un code

class ConfigurationOtpManquante(Exception):
    pass


def cle_code() -> bytes:
    """Secret dédié aux codes (OTP_CLE_SECRETE, variable d'environnement, jamais dans le dépôt). Une clé absente ou
    trop courte (< 32 caractères) interdit la génération et l'envoi quand le service est activé. Hors activation
    (développement, tests de lecture), on dérive une clé locale de SECRET_KEY pour que rien ne plante."""
    secret = getattr(settings, "OTP_CLE_SECRETE", "") or ""
    if len(secret) >= 32:
        return hashlib.sha256(b"fahimta-otp-code|" + secret.encode()).digest()
    if settings.OTP_SMS_ACTIFS:
        raise ConfigurationOtpManquante("OTP_CLE_SECRETE absente ou trop courte (32 caractères minimum).")
    return hashlib.sha256(b"fahimta-otp-code-local|" + settings.SECRET_KEY.encode()).digest()


def code_pour(demande: DemandeReinitialisation) -> str:
    """Reconstitue le code à 6 chiffres de CETTE demande : HMAC(secret dédié, identifiant | sel de la demande). Les 64
    premiers bits donnent un biais inférieur à 10^-13 une fois réduits modulo 10^6."""
    digest = hmac.new(cle_code(), f"code|{demande.pk}|{demande.sel}".encode(), hashlib.sha256).digest()
    return f"{int.from_bytes(digest[:8], 'big') % 10 ** 6:06d}"


def texte_sms(code: str) -> str:
    return (f"FAHIMTA : votre code de vérification est {code}. Valable {settings.OTP_VALIDITE_MINUTES} minutes. "
            "Ne le partagez avec personne.")


def verifier_disponibilite() -> None:
    """Le service est-il capable d'envoyer un SMS ? La réponse est la MÊME pour tous les numéros : elle ne dépend jamais
    de l'existence d'un compte, et elle n'écrit rien (une indisponibilité ne consomme aucune limite)."""
    if not settings.OTP_SMS_ACTIFS:
        raise ErreurRecuperation(MESSAGE_INDISPONIBLE, 503, "indisponible")
    try:
        cle_code()
    except ConfigurationOtpManquante:
        logger.error("Récupération de mot de passe : secret OTP_CLE_SECRETE manquant, service indisponible.")
        raise ErreurRecuperation(MESSAGE_INDISPONIBLE, 503, "indisponible")
    battement = BattementWorkerOtp.objects.filter(pk=1).values_list("dernier_battement", flat=True).first()
    if battement is None or (timezone.now() - battement).total_seconds() > settings.OTP_BATTEMENT_MAX_SECONDES:
        raise ErreurRecuperation(MESSAGE_INDISPONIBLE, 503, "worker_arrete")
    en_retard = EnvoiCodeSms.objects.filter(
        etat=EnvoiCodeSms.Etat.EN_ATTENTE,
        cree_le__lt=timezone.now() - timedelta(seconds=settings.OTP_ATTENTE_MAX_SECONDES))
    if en_retard.exists():
        raise ErreurRecuperation(MESSAGE_INDISPONIBLE, 503, "file_bloquee")


def segments_consommes(depuis) -> int:
    """Segments réservés depuis `depuis` : tout envoi programmé compte (accepté, échec, incertain, en cours, en attente) ;
    seul un envoi ABANDONNÉ AVANT TOUTE TENTATIVE (expiré) est rendu au budget."""
    return (EnvoiCodeSms.objects.filter(cree_le__gte=depuis).exclude(etat=EnvoiCodeSms.Etat.EXPIRE)
            .aggregate(s=Sum("segments"))["s"] or 0)


def demander_code(telephone_brut: str, ip: str | None) -> dict:
    numero = normaliser_numero(telephone_brut)
    verifier_disponibilite()
    cle = cle_numero(numero)
    delai = settings.OTP_DELAI_RENVOI_SECONDES
    heure = timedelta(hours=1)

    with transaction.atomic():
        _verrou(cle)
        _purger()
        # Budget SMS indépendant des campagnes Communications : plafonds journalier et mensuel en SEGMENTS, quel que
        # soit le numéro (compte existant ou non : la réponse est identique).
        debut_mois = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        debut_jour = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        # Le code a toujours 6 chiffres : la longueur du texte, donc le nombre de segments, ne dépend pas du code.
        besoin = max(1, compter_segments(texte_sms("000000"))["segments"])
        if (segments_consommes(debut_jour) + besoin > settings.OTP_PLAFOND_SMS_JOUR
                or segments_consommes(debut_mois) + besoin > settings.OTP_PLAFOND_SMS_MOIS):
            raise ErreurRecuperation(MESSAGE_INDISPONIBLE, 503, "budget_epuise")
        if _compter(E.DEMANDE, heure) >= settings.OTP_MAX_DEMANDES_GLOBAL_HEURE:
            raise ErreurRecuperation("Trop de demandes en ce moment. Réessaie dans quelques minutes.", 429, "limite_globale",
                                     _retry_apres(E.DEMANDE, heure))
        if ip and _compter(E.DEMANDE, heure, ip=ip) >= settings.OTP_MAX_DEMANDES_PAR_IP_HEURE:
            raise ErreurRecuperation("Trop de demandes depuis cette connexion. Réessaie plus tard.", 429, "limite_ip",
                                     _retry_apres(E.DEMANDE, heure, ip=ip))
        derniere = (EvenementRecuperation.objects.filter(type=E.DEMANDE, cle=cle).order_by("-cree_le").first())
        if derniere and (timezone.now() - derniere.cree_le).total_seconds() < delai:
            reste = int(delai - (timezone.now() - derniere.cree_le).total_seconds()) + 1
            raise ErreurRecuperation("Attends un peu avant de demander un nouveau code.", 429, "delai_renvoi", reste)
        if _compter(E.DEMANDE, heure, cle=cle) >= settings.OTP_MAX_DEMANDES_PAR_NUMERO_HEURE:
            raise ErreurRecuperation("Trop de demandes pour ce numéro. Réessaie plus tard.", 429, "limite_numero",
                                     _retry_apres(E.DEMANDE, heure, cle=cle))

        EvenementRecuperation.objects.create(type=E.DEMANDE, cle=cle, ip=ip)   # pour TOUS les numéros (neutralité)

        utilisateur = _trouver_utilisateur(numero)
        if utilisateur is not None and utilisateur.statut == User.Statut.ACTIF:
            maintenant = timezone.now()
            DemandeReinitialisation.objects.filter(utilisateur=utilisateur, cloturee_le__isnull=True).update(
                cloturee_le=maintenant, cloture_motif="remplacee")   # l'ancien code et l'ancienne autorisation meurent
            EnvoiCodeSms.objects.filter(demande__utilisateur=utilisateur, etat=EnvoiCodeSms.Etat.EN_ATTENTE).update(
                etat=EnvoiCodeSms.Etat.EXPIRE, termine_le=maintenant, detail="remplace")   # ne jamais envoyer un code périmé
            demande = DemandeReinitialisation.objects.create(
                utilisateur=utilisateur, sel=secrets.token_hex(16),
                expire_le=maintenant + timedelta(minutes=settings.OTP_VALIDITE_MINUTES))
            # Programmé dans la MÊME transaction que la demande : file persistante, traitée par le worker dédié.
            EnvoiCodeSms.objects.create(demande=demande, telephone=utilisateur.telephone, segments=besoin,
                                        expire_le=demande.expire_le)
    return {"message": MESSAGE_NEUTRE, "delai_renvoi_secondes": delai}


# --------------------------------------------------------------------------- étape 2 : vérifier le code

def _demande_ouverte(utilisateur, **extra):
    return (DemandeReinitialisation.objects.select_for_update()
            .filter(utilisateur=utilisateur, cloturee_le__isnull=True, **extra).order_by("-id").first())


def verifier_code(telephone_brut: str, code: str, ip: str | None) -> dict:
    numero = normaliser_numero(telephone_brut)
    cle = cle_numero(numero)
    if not re.fullmatch(r"\d{6}", code or ""):
        raise ErreurRecuperation(MESSAGE_CODE_INVALIDE, 400, "code_invalide")
    try:
        cle_code()
    except ConfigurationOtpManquante:
        raise ErreurRecuperation(MESSAGE_INDISPONIBLE, 503, "indisponible")
    if ip and _compter(E.VERIF_ECHEC, timedelta(hours=1), ip=ip) >= settings.OTP_MAX_ECHECS_PAR_IP_HEURE:
        raise ErreurRecuperation("Trop de tentatives depuis cette connexion. Réessaie plus tard.", 429, "limite_ip",
                                 _retry_apres(E.VERIF_ECHEC, timedelta(hours=1), ip=ip))
    utilisateur = _trouver_utilisateur(numero)

    erreur = None
    with transaction.atomic():
        _verrou(cle)
        demande = _demande_ouverte(utilisateur, verifiee_le__isnull=True) if utilisateur else None
        valide = bool(demande) and demande.expire_le > timezone.now()
        if not valide:
            hmac_hex(f"code|0|{code}")   # même travail qu'un vrai contrôle : pas de différence de durée exploitable
            enregistrer_echec(E.VERIF_ECHEC, cle, ip)
            if demande and demande.expire_le <= timezone.now():
                demande.cloturee_le, demande.cloture_motif = timezone.now(), "epuisee"
                demande.save(update_fields=["cloturee_le", "cloture_motif"])
            erreur = ErreurRecuperation(MESSAGE_CODE_INVALIDE, 400, "code_invalide")
        elif not hmac.compare_digest(code_pour(demande), code):
            demande.tentatives += 1
            champs = ["tentatives"]
            if demande.tentatives >= settings.OTP_MAX_TENTATIVES:
                demande.cloturee_le, demande.cloture_motif = timezone.now(), "epuisee"
                champs += ["cloturee_le", "cloture_motif"]
            demande.save(update_fields=champs)
            enregistrer_echec(E.VERIF_ECHEC, cle, ip)
            erreur = ErreurRecuperation(MESSAGE_CODE_INVALIDE, 400, "code_invalide")
        else:
            autorisation = secrets.token_urlsafe(32)
            maintenant = timezone.now()
            demande.verifiee_le = maintenant   # le code est consommé : impossible de le rejouer
            demande.autorisation_hmac = hmac_hex(f"auth|{demande.pk}|{autorisation}")
            demande.autorisation_expire_le = maintenant + timedelta(minutes=settings.OTP_AUTORISATION_VALIDITE_MINUTES)
            demande.save(update_fields=["verifiee_le", "autorisation_hmac", "autorisation_expire_le"])
    if erreur:   # levée APRÈS la transaction : sinon le compteur d'essais serait annulé avec elle
        raise erreur
    return {"autorisation": autorisation, "expire_dans_secondes": settings.OTP_AUTORISATION_VALIDITE_MINUTES * 60}


# --------------------------------------------------------------------------- étape 3 : nouveau mot de passe

def reinitialiser(telephone_brut: str, autorisation: str, nouveau: str, confirmation: str, ip: str | None) -> dict:
    numero = normaliser_numero(telephone_brut)
    cle = cle_numero(numero)
    if ip and _compter(E.VERIF_ECHEC, timedelta(hours=1), ip=ip) >= settings.OTP_MAX_ECHECS_PAR_IP_HEURE:
        raise ErreurRecuperation("Trop de tentatives depuis cette connexion. Réessaie plus tard.", 429, "limite_ip",
                                 _retry_apres(E.VERIF_ECHEC, timedelta(hours=1), ip=ip))
    utilisateur = _trouver_utilisateur(numero)

    erreur = None
    with transaction.atomic():
        _verrou(cle)
        demande = _demande_ouverte(utilisateur, verifiee_le__isnull=False) if utilisateur else None
        if not demande or not demande.autorisation_expire_le or demande.autorisation_expire_le <= timezone.now():
            hmac_hex("auth|0|x")
            enregistrer_echec(E.VERIF_ECHEC, cle, ip)
            erreur = ErreurRecuperation(MESSAGE_AUTORISATION_INVALIDE, 400, "autorisation_invalide")
        elif not hmac.compare_digest(demande.autorisation_hmac, hmac_hex(f"auth|{demande.pk}|{autorisation or ''}")):
            demande.echecs_autorisation += 1
            champs = ["echecs_autorisation"]
            if demande.echecs_autorisation >= settings.OTP_MAX_TENTATIVES:
                demande.cloturee_le, demande.cloture_motif = timezone.now(), "epuisee"
                champs += ["cloturee_le", "cloture_motif"]
            demande.save(update_fields=champs)
            enregistrer_echec(E.VERIF_ECHEC, cle, ip)
            erreur = ErreurRecuperation(MESSAGE_AUTORISATION_INVALIDE, 400, "autorisation_invalide")
        elif nouveau != confirmation:
            erreur = ErreurRecuperation("Les deux mots de passe ne correspondent pas.", 400, "confirmation")
        else:
            try:
                validate_password(nouveau, user=utilisateur)
            except DjangoValidationError as exc:
                erreur = ErreurRecuperation("Mot de passe refusé.", 400, "mot_de_passe_faible", details=list(exc.messages))
            else:
                utilisateur.set_password(nouveau)   # hachage Django ; la date de changement refuse tous les jetons existants
                utilisateur.doit_changer_mdp = False
                utilisateur.save(update_fields=["password", "doit_changer_mdp"])
                maintenant = timezone.now()
                demande.cloturee_le, demande.cloture_motif = maintenant, "consommee"
                demande.save(update_fields=["cloturee_le", "cloture_motif"])
                DemandeReinitialisation.objects.filter(utilisateur=utilisateur, cloturee_le__isnull=True).update(
                    cloturee_le=maintenant, cloture_motif="remplacee")
                EvenementRecuperation.objects.filter(type=E.VERIF_ECHEC, cle=cle).delete()
    if erreur:
        raise erreur
    return {"message": "Mot de passe modifié."}
