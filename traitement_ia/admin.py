from django.contrib import admin

from .models import TacheIA


@admin.register(TacheIA)
class TacheIAAdmin(admin.ModelAdmin):
    """Lecture seule : ni contenu d'exercice ni résultat affichés (suivi opérationnel uniquement)."""

    list_display = ("cree_le", "type", "statut", "utilisateur", "tentatives", "resultat_http", "termine_le")
    list_filter = ("type", "statut")
    exclude = ("donnees", "resultat", "kwargs")
    readonly_fields = [f.name for f in TacheIA._meta.fields if f.name not in ("donnees", "resultat", "kwargs")]

    def has_add_permission(self, request):
        return False
