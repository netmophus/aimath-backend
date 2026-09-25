"""
Utilitaires pour les cartes Fahimta (codes prépayés) : génération
cryptographiquement sûre des codes, normalisation de la saisie élève à
l'activation, formatage de date FR, et anti-brute-force sur les tentatives
d'activation ratées.

Regroupés ici (plutôt qu'éclatés dans models.py/views.py) parce que ce sont
des fonctions pures ou quasi-pures, réutilisées à la fois par la commande de
management (génération de lot) et par la vue d'activation (élève).
"""

import re
import secrets
from datetime import date

from django.core.cache import cache

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
