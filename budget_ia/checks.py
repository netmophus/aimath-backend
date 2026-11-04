"""Contrôle de configuration (python manage.py check, démarrage, phase release) : liste blanche IA mal formée."""

from django.core.checks import Warning, register


@register()
def verifier_liste_blanche(app_configs, **kwargs):
    from . import acces

    invalides = acces.entrees_invalides()
    if not invalides:
        return []
    return [
        Warning(
            f"IA_COMPTES_AUTORISES contient {invalides} entrée(s) qui ne sont pas au format +227 suivi de 8 chiffres : "
            "elles sont ignorées (aucun numéro n'est affiché ici).",
            hint="Corriger la variable ; tant qu'elle n'est pas vide, le mode pilote reste actif et fermé aux autres comptes.",
            id="budget_ia.W001",
        )
    ]
