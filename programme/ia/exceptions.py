"""Exceptions du module IA — toujours un message FR prêt à renvoyer tel quel
dans une réponse API (voir programme/ia_views.py), jamais de détail technique
sensible (clé API, trace du SDK) dans le message."""


class IAErreur(Exception):
    """Base commune : toute erreur remontée depuis programme.ia."""


class IAConfigurationInvalide(IAErreur):
    """Clé manquante, fournisseur inconnu… — erreur de réglage serveur, pas
    de la faute de l'appelant."""


class IAQuotaDepasse(IAErreur):
    """429 / quota atteint côté fournisseur."""


class IATimeout(IAErreur):
    """Le fournisseur n'a pas répondu dans le délai imparti."""


class IAReponseVide(IAErreur):
    """Réponse reçue mais sans contenu exploitable."""


class IAErreurFournisseur(IAErreur):
    """Toute autre erreur réseau/API côté fournisseur."""


class SectionInconnue(IAErreur):
    """Section demandée absente du registre programme.ia.prompts.SECTIONS."""
