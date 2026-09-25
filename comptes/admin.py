import csv

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpResponse

from .forms import UserChangeForm, UserCreationForm
from .models import CarteFahimta, User


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
    list_display = ["prenom", "nom", "telephone", "role", "statut", "abonnement_actif_jusqu_au", "date_inscription"]
    list_filter = ["role", "statut"]
    search_fields = ["telephone", "nom", "prenom", "email"]

    fieldsets = (
        (None, {"fields": ("telephone", "password")}),
        ("Informations personnelles", {"fields": ("prenom", "nom", "email")}),
        ("Scolarité (élèves)", {"fields": ("niveau", "serie")}),
        ("Rôle et statut", {"fields": ("role", "statut")}),
        (
            "Abonnement",
            {
                "fields": ("abonnement_actif_jusqu_au",),
                "description": (
                    "Le paiement par carte n'est pas encore automatisé : "
                    "renseigner cette date active manuellement l'abonnement "
                    "de l'élève jusqu'à cette échéance incluse."
                ),
            },
        ),
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


@admin.register(CarteFahimta)
class CarteFahimtaAdmin(admin.ModelAdmin):
    """
    Génération d'un lot : voir la commande `generer_cartes` (plus pratique
    pour produire N codes d'un coup que l'admin, qui reste ici pour la
    CONSULTATION/le SUIVI d'un lot déjà généré et son export).

    Confidentialité des codes NON utilisés : `code_affiche` masque tout sauf
    les 4 derniers caractères tant que la carte est "active" — un code
    encore valide ne doit pas fuiter via une capture d'écran de l'admin. Une
    carte "utilisee" est sans risque à afficher en clair (rejouable nulle
    part) et ça aide le support à vérifier un cas litigieux. La recherche
    (search_fields) porte sur le vrai champ `code`, donc un code complet
    collé dans la recherche retrouve bien la carte malgré le masquage à
    l'affichage.
    """

    list_display = ["code_affiche", "statut", "duree_jours", "lot", "utilisee_par", "date_activation", "date_creation"]
    list_filter = ["statut", "lot", "duree_jours"]
    search_fields = ["code", "utilisee_par__telephone", "utilisee_par__nom", "utilisee_par__prenom"]
    readonly_fields = ["code", "utilisee_par", "date_activation", "date_creation"]
    ordering = ["-date_creation"]
    actions = ["exporter_csv"]

    @admin.display(description="code")
    def code_affiche(self, obj: CarteFahimta) -> str:
        if obj.statut == CarteFahimta.Statut.UTILISEE:
            return obj.code
        return f"FH-••••-••••-{obj.code[-4:]}"

    def has_add_permission(self, request) -> bool:
        # Les cartes se créent uniquement via generer_cartes (codes générés
        # cryptographiquement) — jamais à la main depuis l'admin, où on ne
        # saisirait pas un code conforme au format/à l'unicité voulus.
        return False

    @admin.action(description="Exporter les codes du lot sélectionné (CSV)")
    def exporter_csv(self, request, queryset):
        reponse = HttpResponse(content_type="text/csv")
        reponse["Content-Disposition"] = 'attachment; filename="cartes_fahimta.csv"'
        writer = csv.writer(reponse)
        writer.writerow(["code", "duree_jours", "lot", "date_creation"])
        for carte in queryset.order_by("code"):
            writer.writerow([
                carte.code,
                carte.duree_jours,
                carte.lot,
                carte.date_creation.strftime("%Y-%m-%d %H:%M"),
            ])
        return reponse
