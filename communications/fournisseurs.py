"""Couche d'isolation du fournisseur SMS.

Interface : envoyer(numero, texte) -> (resultat, code), resultat parmi
"accepte" / "refuse" / "non_envoye" / "incertain" (voir comptes.sms.envoyer_sms_detail).

- `simule` (défaut) : aucun appel réseau, rien n'est envoyé. Sert au développement et aux tests.
- `lam` : adaptateur vers LAM (L'Africa Mobile), le fournisseur déjà intégré au projet (comptes/sms.py).
  Il ne donne aucun accusé de livraison exploité : un message "accepte" signifie seulement "accepté par LAM".

Aucune clé n'est lue ici : elles restent dans les réglages Django (variables d'environnement LAM_*).
Pour raccorder un autre fournisseur (KIBIYA, par exemple), ajouter une classe ici et un nom dans FOURNISSEURS.
"""

import logging

from django.conf import settings

from comptes.sms import envoyer_sms_detail

logger = logging.getLogger(__name__)


class FournisseurSimule:
    nom = "simule"
    livraison_confirmee = False

    def envoyer(self, numero: str, texte: str) -> tuple[str, str]:
        logger.info("[communications simulé] message de %d caractères", len(texte))
        return "accepte", "simule"


class FournisseurLam:
    nom = "lam"
    livraison_confirmee = False   # pas d'accusé de réception exploité (aucun endpoint DLR dans le projet)

    def envoyer(self, numero: str, texte: str) -> tuple[str, str]:
        return envoyer_sms_detail(numero, texte)


FOURNISSEURS = {"simule": FournisseurSimule, "lam": FournisseurLam}


def obtenir_fournisseur():
    nom = getattr(settings, "COMMUNICATIONS_FOURNISSEUR", "simule")
    return FOURNISSEURS.get(nom, FournisseurSimule)()
