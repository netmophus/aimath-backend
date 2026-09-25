"""
Utilitaires pour les cartes Fahimta (codes prépayés) : génération
cryptographiquement sûre des codes, normalisation de la saisie élève à
l'activation, formatage de date FR, et anti-brute-force sur les tentatives
d'activation ratées.

Regroupés ici (plutôt qu'éclatés dans models.py/views.py) parce que ce sont
des fonctions pures ou quasi-pures, réutilisées à la fois par la commande de
management (génération de lot), la vue d'activation (élève), l'admin Django
ET les endpoints admin du back-office custom (comptes/admin_cartes_*.py) —
JAMAIS dupliquées entre ces quatre appelants.
"""

import csv
import re
import secrets
from datetime import date
from typing import TYPE_CHECKING

from django.core.cache import cache
from django.http import HttpResponse
from django.utils import timezone

if TYPE_CHECKING:
    from .models import CarteFahimta

# Alphabet SANS caractères ambigus à l'impression/lecture : pas de 0/O, pas
# de 1/I/L. 31 caractères → un code à 12 caractères (3 groupes de 4) offre
# log2(31^12) ≈ 59 bits d'entropie, largement suffisant pour un code à usage
# unique qu'on ne peut de toute façon essayer que par l'API (voir
# anti-brute-force plus bas).
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
LONGUEUR_SEGMENT = 4
NB_SEGMENTS = 3


def _segment() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LONGUEUR_SEGMENT))


def generer_code() -> str:
    """Un code candidat "FH-XXXX-XXXX-XXXX" — SANS vérifier son unicité en
    base (voir generer_code_unique, qui l'appelle en boucle)."""
    segments = "-".join(_segment() for _ in range(NB_SEGMENTS))
    return f"FH-{segments}"


def generer_code_unique(exclure: set[str] | None = None) -> str:
    """Génère un code garanti UNIQUE en base (et absent de `exclure`, pour la
    génération d'un lot entier — voir la commande generer_cartes, qui évite
    ainsi une collision entre deux codes du MÊME lot avant leur écriture en
    base). Collision quasi impossible vu l'espace de codes (~2^59) : la
    boucle n'est qu'un filet de sécurité, jamais censée aller loin."""
    from .models import CarteFahimta  # import différé : évite un cycle avec models.py

    exclure = exclure or set()
    for _ in range(20):
        code = generer_code()
        if code in exclure:
            continue
        if not CarteFahimta.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Impossible de générer un code de carte unique après 20 tentatives.")


def generer_lot(quantite: int, duree_jours: int, lot: str | None = None) -> list["CarteFahimta"]:
    """Génère et enregistre un lot de `quantite` cartes, toutes taguées du
    même `lot` (déduit de l'horodatage si omis). SEULE fonction qui crée des
    cartes — appelée à la fois par la commande `generer_cartes` et par
    l'endpoint admin POST /api/admin/cartes/generer/, jamais dupliquée.

    Exclusion locale (`codes_du_lot`) en plus de la vérification en base
    (voir generer_code_unique) : évite qu'un même code candidat, généré deux
    fois dans CE lot avant que le premier soit écrit en base, ne passe la
    vérification d'existence deux fois de suite — quasi impossible vu
    l'espace de codes, mais gratuit à garantir ici.
    """
    from .models import CarteFahimta  # import différé : évite un cycle avec models.py

    lot = lot or f"lot-{timezone.now():%Y%m%d-%H%M%S}"
    codes_du_lot: set[str] = set()
    cartes = []
    for _ in range(quantite):
        code = generer_code_unique(exclure=codes_du_lot)
        codes_du_lot.add(code)
        cartes.append(CarteFahimta(code=code, duree_jours=duree_jours, lot=lot))

    CarteFahimta.objects.bulk_create(cartes)
    return cartes


def code_masque(carte: "CarteFahimta") -> str:
    """Code en clair si la carte est déjà utilisée (rejouable nulle part,
    donc sans risque à afficher) ; masqué sauf les 4 derniers caractères
    sinon — un code encore ACTIF ne doit jamais fuiter via une capture
    d'écran ou un export non prévu pour ça. Utilisé par l'admin Django
    (CarteFahimtaAdmin.code_affiche) ET par le serializer du back-office
    custom (CarteFahimtaAdminSerializer) — jamais dupliqué."""
    from .models import CarteFahimta

    if carte.statut == CarteFahimta.Statut.UTILISEE:
        return carte.code
    return f"FH-••••-••••-{carte.code[-4:]}"


def lignes_csv_cartes(cartes) -> list[list[str]]:
    """En-tête + une ligne par carte, codes TOUJOURS en clair (l'export est
    justement le moyen prévu de sortir les codes en masse pour impression/
    distribution — voir code_masque pour la confidentialité à l'écran).
    Utilisé par l'action d'export de l'admin Django ET l'endpoint
    GET /api/admin/cartes/export/, jamais dupliqué."""
    lignes = [["code", "duree_jours", "lot", "date_creation"]]
    for carte in cartes:
        lignes.append([
            carte.code,
            str(carte.duree_jours),
            carte.lot,
            carte.date_creation.strftime("%Y-%m-%d %H:%M"),
        ])
    return lignes


def reponse_csv_cartes(cartes, nom_fichier: str = "cartes_fahimta.csv") -> HttpResponse:
    """HttpResponse CSV prête à renvoyer telle quelle — wrapper autour de
    lignes_csv_cartes pour les deux appelants (admin Django, endpoint DRF)
    qui ont tous deux besoin d'un objet HttpResponse, pas juste des lignes."""
    reponse = HttpResponse(content_type="text/csv")
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}"'
    csv.writer(reponse).writerows(lignes_csv_cartes(cartes))
    return reponse


def normaliser_code(saisie: str) -> str:
    """Reconstruit la forme canonique "FH-XXXX-XXXX-XXXX" depuis une saisie
    élève quelconque : majuscules, espaces/tirets retirés puis réinsérés à
    la bonne place — accepte donc "fh1234abcd5678", "FH-1234-ABCD-5678",
    "fh 1234 abcd 5678", etc. Une saisie qui ne correspond pas à ce gabarit
    (mauvaise longueur, ne commence pas par FH) est renvoyée "aplatie" telle
    quelle : elle ne matchera simplement aucune carte, et l'appelant traite
    ça comme un code introuvable — jamais une erreur à part."""
    aplati = re.sub(r"[\s-]", "", (saisie or "").upper())
    if len(aplati) != 14 or not aplati.startswith("FH"):
        return aplati
    reste = aplati[2:]
    return f"FH-{reste[0:4]}-{reste[4:8]}-{reste[8:12]}"


_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def formater_date_fr(valeur: date) -> str:
    """"25 octobre 2026" — pas de dépendance à babel/locale système,
    volontairement minimal (un seul format, jamais réutilisé ailleurs)."""
    return f"{valeur.day} {_MOIS_FR[valeur.month - 1]} {valeur.year}"


# ============================================================
#  Anti-brute-force sur l'activation : compteur d'ÉCHECS (pas de toute
#  requête) par élève, fenêtre glissante simple via le cache Django.
#
#  Pourquoi pas DRF ScopedRateThrottle : il compte TOUTES les requêtes
#  (succès compris) par IP/utilisateur, alors que la consigne porte
#  spécifiquement sur les tentatives RATÉES — un élève qui active sa carte
#  du premier coup ne doit jamais être pénalisé par ses lectures de page.
#  Un compteur dédié, incrémenté uniquement sur échec, colle exactement à
#  ce besoin sans tirer une dépendance supplémentaire.
#
#  Cache Django par défaut (LocMemCache, aucune config CACHES dans ce
#  projet) : suffisant pour un déploiement mono-process comme aujourd'hui.
#  À noter pour plus tard : passer à un backend partagé (Redis) le jour où
#  plusieurs workers tournent, sinon le compteur n'est plus fiable entre eux.
# ============================================================

SEUIL_ECHECS = 5
FENETRE_SECONDES = 3600  # 1 heure


def _cle_echecs(user) -> str:
    return f"carte_fahimta_echecs_{user.id}"


def trop_de_tentatives(user) -> bool:
    return cache.get(_cle_echecs(user), 0) >= SEUIL_ECHECS


def enregistrer_echec(user) -> None:
    cle = _cle_echecs(user)
    # cache.get puis cache.set (pas incr()) : incr() lève une exception si
    # la clé n'existe pas encore (premier échec), il faudrait de toute façon
    # un cache.add() préalable — get+set reste plus simple à lire ici, et le
    # volume d'appels (un élève qui échoue son code) ne justifie pas
    # l'atomicité stricte d'incr() sur ce compteur.
    valeur = cache.get(cle, 0) + 1
    cache.set(cle, valeur, FENETRE_SECONDES)


def reinitialiser_echecs(user) -> None:
    cache.delete(_cle_echecs(user))


# ============================================================
#  ÉTATS DE SUIVI ADMIN (traçabilité, voir comptes/admin_cartes_views.py) —
#  vocabulaire respecté PARTOUT (calcul par carte, filtre ORM du endpoint de
#  liste, agrégats de /api/admin/cartes/stats/) via les DEUX fonctions
#  ci-dessous, jamais réécrit ailleurs :
#    - "stock_central" : active, vendeur IS NULL, attribuee_a IS NULL.
#    - "assignee"       : active, vendeur défini, attribuee_a IS NULL (chez
#                          le vendeur, pas encore donnée à un élève).
#    - "vendue"          : attribuee_a défini ET statut encore active (donnée
#                          à un élève, pas encore activée par lui).
#    - "utilisee"        : statut utilisee (l'élève a activé son abonnement).
# ============================================================

ETAT_STOCK_CENTRAL = "stock_central"
ETAT_ASSIGNEE = "assignee"
ETAT_VENDUE = "vendue"
ETAT_UTILISEE = "utilisee"

ETATS_CARTE = [ETAT_STOCK_CENTRAL, ETAT_ASSIGNEE, ETAT_VENDUE, ETAT_UTILISEE]


def etat_carte(carte: "CarteFahimta") -> str:
    """État métier d'UNE carte déjà chargée (utilisé par le serializer de
    liste) — voir filtre_etat() ci-dessous pour l'équivalent en filtre ORM
    (utilisé par la vue et les stats), les deux DOIVENT rester cohérents."""
    from .models import CarteFahimta

    if carte.statut == CarteFahimta.Statut.UTILISEE:
        return ETAT_UTILISEE
    if carte.attribuee_a_id:
        return ETAT_VENDUE
    if carte.vendeur_id:
        return ETAT_ASSIGNEE
    return ETAT_STOCK_CENTRAL


def filtre_etat(etat: str):
    """Q() ORM équivalent à etat_carte() ci-dessus, pour filtrer un queryset
    (?etat= de CarteFahimtaAdminViewSet) ou agréger des compteurs (Count avec
    filter=, voir l'action `stats`). Q() vide (tout) si `etat` ne correspond
    à aucun état connu — l'appelant choisit alors de l'ignorer ou pas."""
    from django.db.models import Q

    from .models import CarteFahimta

    if etat == ETAT_STOCK_CENTRAL:
        return Q(statut=CarteFahimta.Statut.ACTIVE, vendeur__isnull=True, attribuee_a__isnull=True)
    if etat == ETAT_ASSIGNEE:
        return Q(statut=CarteFahimta.Statut.ACTIVE, vendeur__isnull=False, attribuee_a__isnull=True)
    if etat == ETAT_VENDUE:
        return Q(statut=CarteFahimta.Statut.ACTIVE, attribuee_a__isnull=False)
    if etat == ETAT_UTILISEE:
        return Q(statut=CarteFahimta.Statut.UTILISEE)
    return Q()
