from django.conf import settings
from django.db.models import Count
from rest_framework import serializers

from . import services
from .models import Campagne, MessageSms, ParametresCommunication


class ApercuSerializer(serializers.Serializer):
    cle = serializers.CharField(min_length=8, max_length=64)
    type = serializers.ChoiceField(choices=Campagne.Type.choices)
    texte = serializers.CharField(max_length=2000)
    mode = serializers.ChoiceField(choices=Campagne.Mode.choices)
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list,
                                max_length=services.IDS_MAX)
    filtres = serializers.DictField(required=False, default=dict)

    def validate_filtres(self, valeur):
        propres = {}
        for cle in ("role", "statut", "search", "niveau", "serie"):
            v = valeur.get(cle)
            if v in (None, ""):
                continue
            if cle in ("niveau", "serie"):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    raise serializers.ValidationError(f"{cle} invalide.")
            propres[cle] = v if cle != "search" else str(v)[:100]
        return propres


class ParametresSerializer(serializers.Serializer):
    lien_whatsapp = serializers.CharField(required=False, allow_blank=True, max_length=200)
    plafond_mensuel_fcfa = serializers.IntegerField(required=False, min_value=0, max_value=100_000_000)
    cout_segment_fcfa = serializers.DecimalField(required=False, allow_null=True, max_digits=8, decimal_places=2,
                                                 min_value=0)


class PreferenceSerializer(serializers.Serializer):
    """Côté administrateur : seule l'opposition est modifiable (le consentement appartient à la personne)."""
    opposition_facultatif = serializers.BooleanField(required=False)


class PreferenceEleveSerializer(serializers.Serializer):
    sms_facultatifs = serializers.BooleanField(required=False)
    invitations_whatsapp = serializers.BooleanField(required=False)
    parental_telephone = serializers.CharField(required=False, max_length=20)


class DecisionParentaleSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["valider", "refuser", "revoquer"])
    methode = serializers.CharField(required=False, allow_blank=True, max_length=12)
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)


def budget() -> dict:
    p = ParametresCommunication.charger()
    depense = services.depense_mois()
    return {
        "plafond_mensuel_fcfa": p.plafond_mensuel_fcfa,
        "cout_segment_fcfa": p.cout_segment_fcfa,
        "tarif_connu": p.cout_segment_fcfa is not None,
        "depense_mois_fcfa": depense,
        "restant_fcfa": max(p.plafond_mensuel_fcfa - depense, 0),
    }


def parametres_dict() -> dict:
    p = ParametresCommunication.charger()
    return {
        "lien_whatsapp": p.lien_whatsapp,
        "envois_actifs": bool(settings.COMMUNICATIONS_SMS_ACTIVES),
        "fournisseur": getattr(settings, "COMMUNICATIONS_FOURNISSEUR", "simule"),
        "livraison_confirmee": False,
        "file_attente": services.file_attente(),
        **budget(),
    }


def campagne_dict(c: Campagne, avec_apercu: bool = False) -> dict:
    comptes = {s: 0 for s in MessageSms.Statut.values}
    for ligne in c.messages.values("statut").annotate(n=Count("id")):
        comptes[ligne["statut"]] = ligne["n"]
    data = {
        "id": c.id, "type": c.type, "categorie": c.categorie, "statut": c.statut, "texte": c.texte, "mode": c.mode,
        "auteur": f"{c.auteur.prenom} {c.auteur.nom}" if c.auteur else None,
        "cree_le": c.cree_le, "confirmee_le": c.confirmee_le, "terminee_le": c.terminee_le,
        "nb_comptes": c.nb_comptes, "exclusions": c.exclusions, "nb_destinataires": c.nb_destinataires,
        "segments_total": c.segments_total, "cout_segment": c.cout_segment, "cout_estime": c.cout_estime,
        "messages": comptes,
        # Aucun accusé de livraison n'est exploité : on ne prétend jamais qu'un message est "livré".
        "livres": None,
    }
    if avec_apercu:
        premier = c.messages.select_related("utilisateur").first()
        lien = ParametresCommunication.charger().lien_whatsapp
        data["texte_exemple"] = (services.rendre(c.texte, premier.utilisateur, lien)
                                 if premier and premier.utilisateur else c.texte)
        data["budget"] = budget()
        data["envois_actifs"] = bool(settings.COMMUNICATIONS_SMS_ACTIVES)
    return data


def message_dict(m: MessageSms) -> dict:
    u = m.utilisateur
    return {
        "id": m.id, "campagne": m.campagne_id, "utilisateur_id": m.utilisateur_id,
        "nom": f"{u.prenom} {u.nom}" if u else None, "telephone": m.telephone_masque,
        "statut": m.statut, "segments": m.segments, "tentatives": m.tentatives, "code": m.dernier_code,
        "mis_a_jour_le": m.mis_a_jour_le,
    }
