from django.apps import AppConfig


class BudgetIaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "budget_ia"
    verbose_name = "Budget IA"

    def ready(self):
        from . import checks  # noqa: F401  (enregistre le contrôle de configuration)
