from django.contrib import admin

from .models import Campagne, MessageSms, ParametresCommunication


@admin.register(Campagne)
class CampagneAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "statut", "auteur", "nb_destinataires", "cout_estime", "cree_le"]
    list_filter = ["type", "statut"]
    readonly_fields = [f.name for f in Campagne._meta.fields]


admin.site.register(ParametresCommunication)
admin.site.register(MessageSms)
