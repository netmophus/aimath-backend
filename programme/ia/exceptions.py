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


class RefusBudget(IAErreur):
    """Refus décidé AVANT tout appel au fournisseur (quota élève, budget, interrupteur). Rien n'a été facturé.
    `message` est destiné à l'élève : court, sans détail interne, sans prix."""

    statut_http = 429
    code = "limite"
    message = "Limite atteinte."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)


class LimiteJourAtteinte(RefusBudget):
    code = "limite_jour"
    message = "Limite du jour atteinte."


class LimiteExerciceAtteinte(RefusBudget):
    code = "limite_exercice"
    message = "Limite atteinte pour cet exercice."


class LimiteInteractionsAtteinte(RefusBudget):
    code = "limite_interactions"
    message = "Limite de questions atteinte pour cet exercice."


class BudgetEpuise(RefusBudget):
    statut_http = 503
    code = "budget_epuise"
    message = "Service temporairement indisponible. Réessaie plus tard."


class IADesactivee(RefusBudget):
    statut_http = 503
    code = "ia_desactivee"
    message = "Service temporairement indisponible. Réessaie plus tard."


class OperationDejaEnCours(RefusBudget):
    statut_http = 409
    code = "deja_en_cours"
    message = "Analyse déjà en cours. Patiente quelques secondes."


class ResultatPrecedentInconnu(RefusBudget):
    """Une tentative précédente de la même tâche a ouvert un appel payant dont l'issue est inconnue : on ne paie jamais
    deux fois. L'élève relance lui-même (quotas et budget s'appliquent alors normalement)."""

    statut_http = 503
    code = "resultat_inconnu"
    message = "Le traitement a été interrompu. Relance l'analyse."
