from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import UserChangeForm, UserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Admin du User custom. Permet notamment à un administrateur de valider
    (ou rejeter) les comptes élèves inscrits en_attente.
    """

    model = User
    form = UserChangeForm
    add_form = UserCreationForm

    ordering = ["-date_inscription"]
    list_display = ["prenom", "nom", "telephone", "role", "statut", "date_inscription"]
    list_filter = ["role", "statut"]
    search_fields = ["telephone", "nom", "prenom", "email"]

    fieldsets = (
        (None, {"fields": ("telephone", "password")}),
        ("Informations personnelles", {"fields": ("prenom", "nom", "email")}),
        ("Scolarité (élèves)", {"fields": ("niveau", "serie")}),
        ("Rôle et statut", {"fields": ("role", "statut")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_inscription")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "telephone",
                    "prenom",
                    "nom",
                    "email",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = ["date_inscription", "last_login"]

    actions = ["approuver_comptes", "rejeter_comptes"]

    @admin.action(description="Approuver les comptes sélectionnés")
    def approuver_comptes(self, request, queryset):
        nb = queryset.update(statut=User.Statut.ACTIF)
        self.message_user(request, f"{nb} compte(s) approuvé(s).")

    @admin.action(description="Rejeter les comptes sélectionnés")
    def rejeter_comptes(self, request, queryset):
        nb = queryset.update(statut=User.Statut.REJETE)
        self.message_user(request, f"{nb} compte(s) rejeté(s).")
