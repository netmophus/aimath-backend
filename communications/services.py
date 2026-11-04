"""Logique métier du module de communication administrateur.

Principes :
- Rien ne part sans confirmation explicite d'un administrateur (aperçu -> confirmation).
- Les destinataires sont toujours déterminés ICI, à partir des filtres ou des identifiants de comptes,
  jamais à partir de numéros fournis par le navigateur.
- Un SMS "accepté" par le fournisseur n'est pas un SMS "livré" : aucun statut de livraison n'existe tant
  que le fournisseur n'en fournit pas.
- Après une interruption, un message dont l'issue est inconnue passe en "incertain" et n'est JAMAIS renvoyé
  automatiquement.
"""

import logging
import re
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from comptes.models import User
from comptes.sms import normaliser_telephone_sms

from .fournisseurs import FOURNISSEURS, obtenir_fournisseur
from .models import Campagne, MessageSms, ParametresCommunication, TentativeSms
from .segments import compter

logger = logging.getLogger(__name__)

TEXTE_MAX = 480
SEGMENTS_MAX = 6
IDS_MAX = 5000
LIEN_WHATSAPP_PREFIXE = "https://chat.whatsapp.com/"
VARIABLES = {"prenom", "lien"}

MODELES = [
    {
        "code": "activation",
        "libelle": "Activation du compte",
        "type": "activation",
        "texte": "Bonjour, votre compte FAHIMTA est activé. Connectez-vous sur myfahimta.com pour accéder à votre espace.",
    },
    {
        "code": "information_generale",
        "libelle": "Information générale",
        "type": "sms",
        "texte": "Bonjour {prenom}, FAHIMTA vous informe : ",
    },
    {
        "code": "nouveau_contenu",
        "libelle": "Nouveau contenu",
        "type": "sms",
        "texte": "Bonjour {prenom}, du nouveau contenu est disponible sur FAHIMTA. Connectez-vous sur myfahimta.com pour le découvrir.",
    },
    {
        "code": "invitation_whatsapp",
        "libelle": "Invitation WhatsApp",
        "type": "invitation_whatsapp",
        "texte": ("Bonjour, FAHIMTA vous invite à rejoindre son groupe WhatsApp d'information. "
                  "Rejoignez-nous ici : {lien}. Votre numéro pourra être visible des autres membres."),
    },
]

_SECRET_RE = re.compile(r"eyJ[\w-]{8,}\.[\w-]{8,}|(mot de passe|password|mdp|jeton|token)\s*[:=]", re.IGNORECASE)


class ErreurMetier(Exception):
    def __init__(self, message: str, statut_http: int = 400, code: str = ""):
        super().__init__(message)
        self.message = message
        self.statut_http = statut_http
        self.code = code


# --------------------------------------------------------------------------- numéros, texte

def numero_valide(numero: str) -> bool:
    return bool(re.fullmatch(r"227\d{8}", numero))


def masquer(numero: str) -> str:
    return f"+{numero[:3]}****{numero[-3:]}" if len(numero) >= 8 else "****"


def valider_texte(texte: str, type_: str) -> str:
    texte = (texte or "").strip()
    if not texte:
        raise ErreurMetier("Le message est vide.")
    if len(texte) > TEXTE_MAX:
        raise ErreurMetier(f"Le message dépasse {TEXTE_MAX} caractères.")
    for nom in re.findall(r"\{([^{}]*)\}", texte):
        if nom not in VARIABLES:
            raise ErreurMetier(f"Variable inconnue : {{{nom}}}. Variables autorisées : {{prenom}}, {{lien}}.")
    if re.sub(r"\{[^{}]*\}", "", texte).count("{") or re.sub(r"\{[^{}]*\}", "", texte).count("}"):
        raise ErreurMetier("Accolades mal formées dans le message.")
    if "{lien}" in texte and type_ != Campagne.Type.INVITATION:
        raise ErreurMetier("La variable {lien} est réservée à l'invitation WhatsApp.")
    if type_ == Campagne.Type.INVITATION and "{lien}" not in texte:
        raise ErreurMetier("Le message d'invitation doit contenir {lien}.")
    if _SECRET_RE.search(texte):
        raise ErreurMetier("Un SMS ne doit jamais contenir de mot de passe, de jeton ou de secret.")
    return texte


def rendre(texte: str, utilisateur, lien: str) -> str:
    return texte.replace("{prenom}", (utilisateur.prenom or "").strip()).replace("{lien}", lien)


def valider_lien_whatsapp(lien: str) -> str:
    lien = (lien or "").strip()
    if lien and not (lien.startswith(LIEN_WHATSAPP_PREFIXE) and len(lien) > len(LIEN_WHATSAPP_PREFIXE) + 5):
        raise ErreurMetier(f"Le lien doit commencer par {LIEN_WHATSAPP_PREFIXE}")
    return lien


# --------------------------------------------------------------------------- éligibilité

def _age_connu_majeur(utilisateur) -> bool:
    if utilisateur.role != User.Role.ELEVE:
        return True
    n = utilisateur.date_naissance
    if not n:
        return False   # date inconnue : traité comme mineur, par prudence
    aujourdhui = date.today()
    age = aujourdhui.year - n.year - ((aujourdhui.month, aujourdhui.day) < (n.month, n.day))
    return age >= 18


def _preference(utilisateur):
    try:
        return utilisateur.preference_communication
    except Exception:
        return None


def motif_exclusion(utilisateur, type_: str, categorie: str) -> str | None:
    if utilisateur.statut != User.Statut.ACTIF:
        return "statut_non_actif"
    if not numero_valide(normaliser_telephone_sms(utilisateur.telephone)):
        return "numero_invalide"
    pref = _preference(utilisateur)
    if categorie == Campagne.Categorie.FACULTATIF and pref and pref.opposition_facultatif:
        return "opposition"
    if type_ == Campagne.Type.INVITATION:
        # Opt-in explicite obligatoire : l'absence d'opposition n'est jamais un consentement.
        if not (pref and pref.invitations_whatsapp is True):
            return "consentement_requis"
        if not _age_connu_majeur(utilisateur):
            if not (pref.parental_statut == pref.Parental.VALIDE):
                return "consentement_parental_requis"
    return None


def resoudre_comptes(mode: str, ids, filtres: dict):
    qs = User.objects.select_related("preference_communication").order_by("id")
    if mode == Campagne.Mode.IDS:
        return qs.filter(id__in=list(ids)[:IDS_MAX])
    if mode == Campagne.Mode.FILTRES:
        role, statut, search = filtres.get("role"), filtres.get("statut"), filtres.get("search")
        if role in User.Role.values:
            qs = qs.filter(role=role)
        if statut in User.Statut.values:
            qs = qs.filter(statut=statut)
        if filtres.get("niveau"):
            qs = qs.filter(niveau_id=int(filtres["niveau"]))
        if filtres.get("serie"):
            qs = qs.filter(serie_id=int(filtres["serie"]))
        if search:
            qs = qs.filter(Q(nom__icontains=search) | Q(prenom__icontains=search) | Q(telephone__icontains=search))
        return qs
    return qs   # TOUS : l'éligibilité fait le tri


# --------------------------------------------------------------------------- budget

def _debut_mois():
    return timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def depense_mois() -> Decimal:
    total = Decimal("0")
    en_charge = [MessageSms.Statut.EN_ATTENTE, MessageSms.Statut.EN_COURS, MessageSms.Statut.ACCEPTE,
                 MessageSms.Statut.INCERTAIN]
    for c in Campagne.objects.filter(confirmee_le__gte=_debut_mois()).exclude(cout_segment=None):
        seg = c.messages.filter(statut__in=en_charge).aggregate(s=Sum("segments"))["s"] or 0
        total += seg * c.cout_segment
    return total


def _verifier_budget(parametres: ParametresCommunication, cout: Decimal | None):
    if not parametres.plafond_mensuel_fcfa:
        raise ErreurMetier("Aucun plafond mensuel de dépense SMS n'est défini.", 409, "plafond_absent")
    if parametres.cout_segment_fcfa is None or cout is None:
        raise ErreurMetier("Le coût d'un SMS n'est pas renseigné : impossible de vérifier le budget.", 409, "tarif_absent")
    depense = depense_mois()
    if depense + cout > Decimal(parametres.plafond_mensuel_fcfa):
        restant = max(Decimal(parametres.plafond_mensuel_fcfa) - depense, Decimal("0"))
        raise ErreurMetier(
            f"Plafond mensuel dépassé : coût estimé {cout} FCFA, budget restant {restant} FCFA.", 409, "plafond_depasse")


# --------------------------------------------------------------------------- préparation

def preparer(auteur, cle: str, type_: str, texte: str, mode: str, ids, filtres: dict):
    """Crée (ou retrouve, par clé) une campagne en APERCU. Rien n'est envoyé. Retourne (campagne, creee)."""
    existante = Campagne.objects.filter(auteur=auteur, cle=cle).first()
    if existante:
        return existante, False

    texte = valider_texte(texte, type_)
    categorie = Campagne.Categorie.SERVICE if type_ == Campagne.Type.ACTIVATION else Campagne.Categorie.FACULTATIF
    if type_ == Campagne.Type.ACTIVATION and (mode != Campagne.Mode.IDS or len(set(ids)) != 1):
        raise ErreurMetier("Une notification d'activation concerne un seul compte.")
    if mode == Campagne.Mode.IDS and not ids:
        raise ErreurMetier("Aucun compte sélectionné.")

    parametres = ParametresCommunication.charger()
    lien = parametres.lien_whatsapp
    if type_ == Campagne.Type.INVITATION and not lien:
        raise ErreurMetier("Le lien du groupe WhatsApp n'est pas configuré.", 409, "lien_absent")

    qs = resoudre_comptes(mode, ids, filtres)
    nb_comptes = qs.count()
    exclusions = {"statut_non_actif": 0, "numero_invalide": 0, "opposition": 0, "consentement_requis": 0, "consentement_parental_requis": 0, "doublon": 0}
    vus: set[str] = set()
    retenus: list[tuple[int, str, int]] = []   # (id, numero masqué, segments)
    for u in qs.iterator(chunk_size=500):
        motif = motif_exclusion(u, type_, categorie)
        if motif:
            exclusions[motif] += 1
            continue
        numero = normaliser_telephone_sms(u.telephone)
        if numero in vus:
            exclusions["doublon"] += 1
            continue
        vus.add(numero)
        segments = compter(rendre(texte, u, lien))["segments"]
        if segments > SEGMENTS_MAX:
            raise ErreurMetier(f"Le message final dépasse {SEGMENTS_MAX} segments SMS : raccourcis-le.")
        retenus.append((u.id, masquer(numero), segments))

    segments_total = sum(s for _, _, s in retenus)
    cout_segment = parametres.cout_segment_fcfa
    cout = (cout_segment * segments_total) if cout_segment is not None else None
    try:
        with transaction.atomic():
            camp = Campagne.objects.create(
                auteur=auteur, cle=cle, type=type_, categorie=categorie, texte=texte, mode=mode,
                filtres=filtres if mode == Campagne.Mode.FILTRES else {},
                nb_comptes=nb_comptes, exclusions=exclusions, nb_destinataires=len(retenus),
                segments_total=segments_total, cout_segment=cout_segment, cout_estime=cout)
            MessageSms.objects.bulk_create(
                [MessageSms(campagne=camp, utilisateur_id=i, telephone_masque=m, segments=s) for i, m, s in retenus],
                batch_size=500)
    except IntegrityError:   # deux aperçus simultanés avec la même clé
        return Campagne.objects.get(auteur=auteur, cle=cle), False
    return camp, True


# --------------------------------------------------------------------------- confirmation, arrêt, reprise

def simule_interdit() -> bool:
    """Vrai si le fournisseur simulé est configuré hors développement et tests : il enregistrerait de faux « acceptés »."""
    return (getattr(settings, "COMMUNICATIONS_FOURNISSEUR", "simule") == "simule"
            and not getattr(settings, "COMMUNICATIONS_SIMULE_AUTORISE", False))


def envois_possibles_selon_reglages() -> bool:
    return bool(settings.COMMUNICATIONS_SMS_ACTIVES) and not simule_interdit()


def _exiger_envois_actifs():
    if not settings.COMMUNICATIONS_SMS_ACTIVES:
        raise ErreurMetier("Les envois de SMS sont désactivés sur cet environnement.", 409, "envois_desactives")
    if simule_interdit():
        raise ErreurMetier("Le fournisseur simulé est interdit en production : aucun envoi.", 409, "fournisseur_simule_interdit")


def confirmer(campagne_id: int, auteur, attestation: bool):
    """APERCU -> EN_COURS. Idempotent : une campagne déjà confirmée est renvoyée telle quelle, sans rien relancer."""
    with transaction.atomic():
        parametres = ParametresCommunication.objects.select_for_update().get_or_create(pk=1)[0]   # sérialise les contrôles de budget
        camp = Campagne.objects.select_for_update().filter(id=campagne_id, auteur=auteur).first()
        if camp is None:
            raise ErreurMetier("Campagne introuvable.", 404)
        if camp.statut != Campagne.Statut.APERCU:
            return camp, True
        _exiger_envois_actifs()
        validite = timedelta(minutes=settings.COMMUNICATIONS_APERCU_VALIDITE_MIN)
        if timezone.now() - camp.cree_le > validite:
            raise ErreurMetier("Cet aperçu a expiré : prépare à nouveau le message.", 409, "apercu_expire")
        if camp.nb_destinataires == 0:
            raise ErreurMetier("Aucun destinataire éligible.", 409, "aucun_destinataire")
        if camp.type == Campagne.Type.INVITATION and not attestation:
            raise ErreurMetier("Confirme que les personnes invitées ont consenti à recevoir cette invitation.", 400, "attestation")
        _verifier_budget(parametres, camp.cout_estime)
        camp.statut = Campagne.Statut.EN_COURS
        camp.confirmee_le = timezone.now()
        camp.save(update_fields=["statut", "confirmee_le"])
        return camp, False


def arreter(campagne_id: int):
    with transaction.atomic():
        camp = Campagne.objects.select_for_update().filter(id=campagne_id).first()
        if camp is None:
            raise ErreurMetier("Campagne introuvable.", 404)
        if camp.statut != Campagne.Statut.EN_COURS:
            raise ErreurMetier("Seule une campagne en cours peut être arrêtée.", 409)
        camp.messages.filter(statut=MessageSms.Statut.EN_ATTENTE).update(statut=MessageSms.Statut.ANNULE)
        camp.statut = Campagne.Statut.ARRETEE
        camp.terminee_le = timezone.now()
        camp.save(update_fields=["statut", "terminee_le"])
        return camp


def relancer_echecs(campagne_id: int):
    """Remet en file les messages en ÉCHEC (jamais ceux dont l'issue est incertaine). Le budget est revérifié."""
    with transaction.atomic():
        parametres = ParametresCommunication.objects.select_for_update().get_or_create(pk=1)[0]
        camp = Campagne.objects.select_for_update().filter(id=campagne_id).first()
        if camp is None:
            raise ErreurMetier("Campagne introuvable.", 404)
        if camp.statut != Campagne.Statut.TERMINEE:
            raise ErreurMetier("Seule une campagne terminée peut être relancée.", 409)
        _exiger_envois_actifs()
        echecs = camp.messages.filter(statut=MessageSms.Statut.ECHEC)
        segments = echecs.aggregate(s=Sum("segments"))["s"] or 0
        if segments == 0:
            raise ErreurMetier("Aucun message en échec à relancer.", 409)
        cout = (camp.cout_segment * segments) if camp.cout_segment is not None else None
        _verifier_budget(parametres, cout)
        echecs.update(statut=MessageSms.Statut.EN_ATTENTE)
        camp.statut = Campagne.Statut.EN_COURS
        camp.terminee_le = None
        camp.save(update_fields=["statut", "terminee_le"])
        return camp


# --------------------------------------------------------------------------- traitement par lots (worker)

def recuperer_interrompus() -> int:
    """Un message resté EN_COURS trop longtemps (worker coupé en plein envoi) a une issue inconnue :
    il passe en INCERTAIN et n'est pas renvoyé."""
    seuil = timezone.now() - timedelta(minutes=settings.COMMUNICATIONS_TIMEOUT_REPRISE_MIN)
    n = 0
    for m in MessageSms.objects.filter(statut=MessageSms.Statut.EN_COURS, mis_a_jour_le__lt=seuil):
        m.statut = MessageSms.Statut.INCERTAIN
        m.dernier_code = "interrompu"
        m.save(update_fields=["statut", "dernier_code", "mis_a_jour_le"])
        TentativeSms.objects.create(message=m, resultat="incertain", code="interrompu")
        n += 1
    return n


def _fermer_campagnes_terminees():
    ouvertes = Campagne.objects.filter(statut=Campagne.Statut.EN_COURS)
    for c in ouvertes:
        if not c.messages.filter(statut__in=[MessageSms.Statut.EN_ATTENTE, MessageSms.Statut.EN_COURS]).exists():
            Campagne.objects.filter(id=c.id, statut=Campagne.Statut.EN_COURS).update(
                statut=Campagne.Statut.TERMINEE, terminee_le=timezone.now())


def _traiter_message(message_id: int, fournisseur, parametres) -> None:
    m = MessageSms.objects.select_related("campagne", "utilisateur", "utilisateur__preference_communication").get(id=message_id)
    c = m.campagne
    resultat_final, code = None, ""

    statut_campagne = Campagne.objects.filter(id=c.id).values_list("statut", flat=True).first()
    u = m.utilisateur
    if statut_campagne != Campagne.Statut.EN_COURS:
        resultat_final, code = MessageSms.Statut.ANNULE, "campagne_arretee"
    elif u is None:
        resultat_final, code = MessageSms.Statut.IGNORE, "compte_supprime"
    else:
        motif = motif_exclusion(u, c.type, c.categorie)   # l'état du compte peut avoir changé depuis l'aperçu
        if motif:
            resultat_final, code = MessageSms.Statut.IGNORE, motif
        elif c.type == Campagne.Type.INVITATION and not parametres.lien_whatsapp:
            resultat_final, code = MessageSms.Statut.IGNORE, "lien_absent"

    if resultat_final is None:
        texte = rendre(c.texte, u, parametres.lien_whatsapp)
        try:
            res, code = fournisseur.envoyer(normaliser_telephone_sms(u.telephone), texte)
        except Exception:   # un fournisseur ne doit jamais faire tomber le worker ; issue inconnue
            logger.exception("Erreur inattendue du fournisseur SMS (message %s)", m.id)
            res, code = "incertain", "erreur_fournisseur"
        resultat_final = {
            "accepte": MessageSms.Statut.ACCEPTE,
            "refuse": MessageSms.Statut.ECHEC,
            "non_envoye": MessageSms.Statut.ECHEC,
        }.get(res, MessageSms.Statut.INCERTAIN)
        TentativeSms.objects.create(message=m, resultat=res, code=code)

    m.statut = resultat_final
    m.dernier_code = code
    m.save(update_fields=["statut", "dernier_code", "mis_a_jour_le"])


def _reserver_un() -> int | None:
    """Réserve UN seul message en attente (EN_COURS) : au plus un message est en vol à tout instant, donc une coupure
    brutale du worker ne peut jamais laisser un lot entier dans un état ambigu."""
    with transaction.atomic():
        m = (MessageSms.objects.select_for_update(skip_locked=True, of=("self",))
             .filter(statut=MessageSms.Statut.EN_ATTENTE, campagne__statut=Campagne.Statut.EN_COURS)
             .order_by("id").first())
        if not m:
            return None
        MessageSms.objects.filter(id=m.id).update(
            statut=MessageSms.Statut.EN_COURS, tentatives=F("tentatives") + 1, mis_a_jour_le=timezone.now())
        return m.id


MOTIFS_GARDE = {
    "envois_desactives": "Les envois sont désactivés (COMMUNICATIONS_SMS_ACTIVES est faux).",
    "fournisseur_inconnu": "Le fournisseur configuré (COMMUNICATIONS_FOURNISSEUR) est inconnu : aucun envoi.",
    "fournisseur_simule_interdit": "Le fournisseur simulé est interdit en production : il enregistrerait de faux envois.",
    "plafond_absent": "Aucun plafond mensuel n'est défini.",
    "tarif_absent": "Le coût d'un SMS n'est pas renseigné.",
    "plafond_depasse": "Le plafond mensuel est dépassé.",
}


def garde_envoi() -> str | None:
    """Conditions à réunir AVANT CHAQUE envoi : envois activés, fournisseur connu, plafond et tarif définis, budget
    non dépassé. Retourne le code du premier blocage, ou None. Un blocage laisse les messages EN_ATTENTE (rien n'est perdu)."""
    if not settings.COMMUNICATIONS_SMS_ACTIVES:
        return "envois_desactives"
    if getattr(settings, "COMMUNICATIONS_FOURNISSEUR", "simule") not in FOURNISSEURS:
        return "fournisseur_inconnu"   # jamais de repli silencieux sur le simulé : il « accepterait » sans rien envoyer
    if simule_interdit():
        return "fournisseur_simule_interdit"
    p = ParametresCommunication.charger()
    if not p.plafond_mensuel_fcfa:
        return "plafond_absent"
    if p.cout_segment_fcfa is None:
        return "tarif_absent"
    if depense_mois() > Decimal(p.plafond_mensuel_fcfa):
        return "plafond_depasse"
    return None


def traiter_lot(limite: int | None = None, pause=None, arret=None) -> int:
    """Traite au plus `limite` messages en attente de campagnes EN_COURS, un par un. Avant CHAQUE message, `garde_envoi()`
    est réévaluée ; au premier blocage on s'arrête et les messages restent EN_ATTENTE. `arret()` vrai : arrêt propre après le
    message en cours."""
    if garde_envoi():
        return 0
    limite = limite or settings.COMMUNICATIONS_LOT
    recuperer_interrompus()
    fournisseur = obtenir_fournisseur()
    parametres = ParametresCommunication.charger()
    n = 0
    while n < limite:
        if arret and arret():
            break
        if garde_envoi():
            break
        mid = _reserver_un()
        if mid is None:
            break
        _traiter_message(mid, fournisseur, parametres)
        n += 1
        if pause:
            pause()
    _fermer_campagnes_terminees()
    return n


def file_attente() -> dict:
    """Messages confirmés mais pas encore partis (aucun worker n'a tourné depuis), pour l'affichage administrateur."""
    qs = MessageSms.objects.filter(statut=MessageSms.Statut.EN_ATTENTE, campagne__statut=Campagne.Statut.EN_COURS)
    return {"en_attente": qs.count(), "en_cours": MessageSms.objects.filter(statut=MessageSms.Statut.EN_COURS).count(),
            "incertains": MessageSms.objects.filter(statut=MessageSms.Statut.INCERTAIN).count()}


# --------------------------------------------------------------------------- indicateur d'activation

def statuts_activation(ids) -> dict[int, str]:
    """Dernier état de la notification d'activation par compte : non_envoye / en_attente / envoye / echec / incertain."""
    carte = {
        MessageSms.Statut.EN_ATTENTE: "en_attente", MessageSms.Statut.EN_COURS: "en_attente",
        MessageSms.Statut.ACCEPTE: "envoye", MessageSms.Statut.ECHEC: "echec", MessageSms.Statut.INCERTAIN: "incertain",
    }
    resultat = {int(i): "non_envoye" for i in ids}
    qs = (MessageSms.objects.filter(utilisateur_id__in=resultat.keys(), campagne__type=Campagne.Type.ACTIVATION)
          .exclude(campagne__statut=Campagne.Statut.APERCU).order_by("id"))
    for m in qs:
        resultat[m.utilisateur_id] = carte.get(m.statut, "non_envoye")
    return resultat


# --------------------------------------------------------------------------- préférences et consentements

METHODES_PARENTAL = ("appel", "formulaire", "presence")


def _age(utilisateur):
    n = utilisateur.date_naissance
    if not n:
        return None
    aujourd = date.today()
    return aujourd.year - n.year - ((aujourd.month, aujourd.day) < (n.month, n.day))


def majorite(utilisateur) -> str:
    """'majeur' | 'mineur' | 'inconnue' (un âge inconnu est traité comme un mineur pour les invitations)."""
    age = _age(utilisateur)
    if age is None:
        return "inconnue"
    return "majeur" if age >= 18 else "mineur"


def etat_preferences(utilisateur, admin: bool = False) -> dict:
    utilisateur = User.objects.select_related("preference_communication").get(pk=utilisateur.pk)   # état frais, hors cache
    pref = _preference(utilisateur)
    tel = pref.parental_telephone if pref else ""
    if tel and not admin:
        tel = masquer(normaliser_telephone_sms(tel))
    data = {
        "sms_facultatifs": not bool(pref and pref.opposition_facultatif),
        "invitations_whatsapp": None if not pref else pref.invitations_whatsapp,
        "majorite": majorite(utilisateur),
        "parental_statut": pref.parental_statut if pref else "aucun",
        "parental_telephone": tel,
        "invitation_possible": motif_exclusion(utilisateur, Campagne.Type.INVITATION, Campagne.Categorie.FACULTATIF) is None,
    }
    if admin:
        data.update({
            "parental_methode": pref.parental_methode if pref else "",
            "parental_note": pref.parental_note if pref else "",
            "parental_decide_le": pref.parental_decide_le if pref else None,
        })
    return data


def maj_preferences_eleve(utilisateur, sms_facultatifs=None, invitations_whatsapp=None, parental_telephone=None) -> dict:
    """Seul l'élève, sur son propre compte. Aucune ligne n'est créée tant qu'il n'a rien choisi."""
    from .models import PreferenceCommunication

    pref, _ = PreferenceCommunication.objects.get_or_create(utilisateur=utilisateur)
    maintenant = timezone.now()
    if parental_telephone is not None:
        if majorite(utilisateur) == "majeur":
            raise ErreurMetier("Un accord parental n'est nécessaire que pour les mineurs.")
        numero = normaliser_telephone_sms(parental_telephone)
        if not numero_valide(numero):
            raise ErreurMetier("Numéro du parent ou tuteur invalide (format Niger : 8 chiffres).")
        if numero == normaliser_telephone_sms(utilisateur.telephone):
            raise ErreurMetier("Le numéro du parent ou tuteur doit être différent du tien.")
        if numero != normaliser_telephone_sms(pref.parental_telephone or ""):
            pref.parental_telephone = numero
            pref.parental_statut = pref.Parental.DEMANDE   # tout changement de contact annule une validation passée
            pref.parental_demande_le = maintenant
            pref.parental_methode, pref.parental_note = "", ""
            pref.parental_decide_par, pref.parental_decide_le = None, None
    if sms_facultatifs is not None:
        pref.opposition_facultatif = not sms_facultatifs
    if invitations_whatsapp is not None:
        pref.invitations_whatsapp = invitations_whatsapp
        pref.invitations_whatsapp_le = maintenant
    pref.save()
    return etat_preferences(utilisateur)


def decider_parental(admin_user, utilisateur, decision: str, methode: str = "", note: str = "") -> dict:
    """Validation vérifiable par un administrateur : qui, quand, comment. Jamais déduite ni automatique."""
    from .models import PreferenceCommunication

    pref = PreferenceCommunication.objects.filter(utilisateur=utilisateur).first()
    P = PreferenceCommunication.Parental
    if decision in ("valider", "refuser"):
        if not pref or pref.parental_statut != P.DEMANDE:
            raise ErreurMetier("Aucune demande d'accord parental en attente pour ce compte.", 409, "pas_de_demande")
        if decision == "valider" and methode not in METHODES_PARENTAL:
            raise ErreurMetier("Indique comment l'accord a été vérifié (appel, formulaire signé ou présence).")
        pref.parental_statut = P.VALIDE if decision == "valider" else P.REFUSE
        pref.parental_methode = methode if decision == "valider" else ""
    elif decision == "revoquer":
        if not pref or pref.parental_statut != P.VALIDE:
            raise ErreurMetier("Aucun accord parental validé à révoquer.", 409, "pas_de_validation")
        pref.parental_statut = P.AUCUN
        pref.parental_methode = ""
    else:
        raise ErreurMetier("Décision inconnue.")
    pref.parental_note = (note or "")[:200]
    pref.parental_decide_par = admin_user
    pref.parental_decide_le = timezone.now()
    pref.save()
    return etat_preferences(utilisateur, admin=True)
