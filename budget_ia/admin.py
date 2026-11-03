"""Administration Django : lecture seule (aucune saisie manuelle des compteurs). Pas de clé, pas de contenu d'exercice."""

from django.contrib import admin

from .models import AlerteBudgetIA, BudgetMensuel, OperationIA


class LectureSeule(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BudgetMensuel)
class BudgetMensuelAdmin(LectureSeule):
    list_display = ("mois", "depense_fcfa", "reserve_fcfa", "maj_le")
    readonly_fields = ("mois", "depense_fcfa", "reserve_fcfa", "cree_le", "maj_le")
    change_list_template = None

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OperationIA)
class OperationIAAdmin(LectureSeule):
    list_display = ("cree_le", "fonctionnalite", "modele", "statut", "utilisateur", "cout_fcfa", "tokens_entree", "tokens_sortie", "consommation_connue")
    list_filter = ("fonctionnalite", "modele", "statut", "mois", "consommation_connue")
    search_fields = ("utilisateur__telephone", "cle_operation")
    date_hierarchy = "cree_le"

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AlerteBudgetIA)
class AlerteBudgetIAAdmin(LectureSeule):
    list_display = ("mois", "seuil", "message", "cree_le", "acquittee")
    list_editable = ("acquittee",)
    list_filter = ("mois", "seuil", "acquittee")

    def has_change_permission(self, request, obj=None):
        return True
