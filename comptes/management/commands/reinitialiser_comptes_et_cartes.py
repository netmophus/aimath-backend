"""
Réinitialisation SÉLECTIVE : supprime TOUS les comptes (élèves, enseignants,
admins, partenaires, vendeurs — y compris les superusers), TOUTES les cartes
Fahimta, TOUS les paiements NITA et TOUS les rappels d'abonnement — GARDE
INTÉGRALEMENT le contenu pédagogique (Cycle, Niveau, Serie, Matiere,
Programme, Theme, Chapitre, Notion, Lecon, Exercice, Video, Ressource,
TermeGlossaire, CharteNotation, PromptSectionNotion).

VÉRIFICATION PRÉALABLE (faite avant d'écrire cette commande, pas supposée) :
tout le code de programme/models.py a été relu, et une recherche exhaustive
de ForeignKey/OneToOneField a été faite sur TOUT le backend (source ET
migrations, comptes ET programme). Résultat : AUCUN modèle de contenu
pédagogique n'a de ForeignKey vers User — toutes les FK vers User vivent
exclusivement dans comptes/models.py (CarteFahimta.vendeur/utilisee_par/
attribuee_a en SET_NULL, PaiementNita.user et RappelAbonnementEnvoye.user en
CASCADE). Supprimer tous les User ne peut donc JAMAIS endommager ou
supprimer de contenu pédagogique — rien à mettre à NULL au préalable.

Usage :
    python manage.py reinitialiser_comptes_et_cartes              # DRY-RUN (rien supprimé)
    python manage.py reinitialiser_comptes_et_cartes --confirmer  # suppression RÉELLE

ORDRE DE SUPPRESSION (respecte les FK, voir ci-dessus) :
    1. RappelAbonnementEnvoye (FK → User, CASCADE)
    2. PaiementNita            (FK → User, CASCADE)
    3. CarteFahimta            (FK → User ×3, SET_NULL — supprimée
       explicitement ici : une suppression des User seule ne l'aurait que
       "détachée", jamais effacée, ces 3 FK n'étant pas en CASCADE)
    4. User                    (TOUS, y compris admin/superuser)

Transaction atomique : soit les 4 étapes réussissent ensemble, soit aucune
n'est appliquée (une erreur en cours de route annule tout, rien n'est
supprimé à moitié).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from comptes.models import CarteFahimta, PaiementNita, RappelAbonnementEnvoye, User
from programme.models import (
    Chapitre,
    CharteNotation,
    Cycle,
    Exercice,
    Lecon,
    Matiere,
    Niveau,
    Notion,
    Programme,
    PromptSectionNotion,
    Ressource,
    Serie,
    TermeGlossaire,
    Theme,
    Video,
)

# Ordre d'affichage volontairement proche de la hiérarchie pédagogique
# (Cycle → ... → Lecon → ses enfants), puis les modèles transverses.
MODELES_CONTENU = [
    Cycle, Niveau, Serie, Matiere, Programme, Theme, Chapitre, Notion,
    Lecon, Exercice, Video, Ressource, TermeGlossaire, CharteNotation,
    PromptSectionNotion,
]


class Command(BaseCommand):
    help = (
        "Supprime TOUS les comptes/cartes Fahimta/paiements NITA/rappels "
        "d'abonnement — garde INTÉGRALEMENT le contenu pédagogique. "
        "Dry-run par défaut (rien n'est supprimé) ; passer --confirmer pour "
        "exécuter réellement la suppression."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmer",
            action="store_true",
            help="Exécute réellement la suppression. Sans ce drapeau : dry-run, rien n'est supprimé.",
        )

    def handle(self, *args, **options):
        confirmer = options["confirmer"]

        nb_rappels = RappelAbonnementEnvoye.objects.count()
        nb_paiements = PaiementNita.objects.count()
        nb_cartes = CarteFahimta.objects.count()
        nb_users = User.objects.count()
        nb_admins = User.objects.filter(role=User.Role.ADMIN).count()

        self.stdout.write(self.style.WARNING("\n=== SERA SUPPRIMÉ ==="))
        self.stdout.write(f"  RappelAbonnementEnvoye : {nb_rappels}")
        self.stdout.write(f"  PaiementNita           : {nb_paiements}")
        self.stdout.write(f"  CarteFahimta           : {nb_cartes}")
        self.stdout.write(f"  User (tous rôles)      : {nb_users}  (dont {nb_admins} admin(s))")

        self.stdout.write(self.style.SUCCESS("\n=== GARDÉ INTÉGRALEMENT (contenu pédagogique) ==="))
        for modele in MODELES_CONTENU:
            self.stdout.write(f"  {modele.__name__:22s}: {modele.objects.count()}")

        if not confirmer:
            self.stdout.write(self.style.WARNING(
                "\nDRY-RUN — rien n'a été supprimé.\n"
                "Relance avec --confirmer pour exécuter réellement la suppression."
            ))
            return

        self.stdout.write(self.style.ERROR(
            "\n--confirmer détecté : suppression RÉELLE en cours (transaction atomique)…"
        ))

        with transaction.atomic():
            RappelAbonnementEnvoye.objects.all().delete()
            PaiementNita.objects.all().delete()
            CarteFahimta.objects.all().delete()
            User.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Terminé — {nb_rappels} rappel(s), {nb_paiements} paiement(s) NITA, "
            f"{nb_cartes} carte(s), {nb_users} compte(s) supprimés.\n"
            "Contenu pédagogique intact (voir décompte ci-dessus, inchangé)."
        ))
