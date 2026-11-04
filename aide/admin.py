from django.contrib import admin

from .models import DemandeAide


@admin.register(DemandeAide)
class DemandeAideAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "eleve", "statut", "cree_le", "traitee_le"]
    list_filter = ["type", "statut"]
    search_fields = ["message", "reponse", "eleve__nom", "eleve__prenom", "eleve__telephone"]
    readonly_fields = ["eleve", "cle", "type", "programme", "lecon", "message", "piece_jointe_type", "piece_jointe_taille",
                       "reponse_par", "reponse_le", "cree_le", "mis_a_jour_le"]
    exclude = ["piece_jointe"]
