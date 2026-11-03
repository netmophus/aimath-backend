"""
Test d'intégration RÉEL (payant) : lecture, correction, plan + une interaction fahimta ai sur UN petit exercice texte.

PAR DÉFAUT : aucun appel. La commande affiche seulement le coût MAXIMAL prévu (réservations). Pour lancer les vrais
appels il faut l'accord explicite de l'équipe ET le drapeau --j-autorise-le-cout, sur un compte de développement :

    python manage.py test_integration_ia --telephone +22790000000 --j-autorise-le-cout

Les appels passent par le MÊME chemin que la production (réservation, quotas, décompte) : le test vérifie donc aussi
que la consommation est bien enregistrée. Aucun contenu n'est affiché ni stocké en base.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from budget_ia import service as budget
from budget_ia import tarifs
from budget_ia.models import OperationIA

ENONCE = "Résoudre dans R l'équation x^2 - 5x + 6 = 0."


class Command(BaseCommand):
    help = "Test d'intégration réel (payant) de la chaîne IA. Sans --j-autorise-le-cout : simple estimation du coût maximal."

    def add_arguments(self, parser):
        parser.add_argument("--telephone", help="Téléphone d'un élève de DÉVELOPPEMENT (compte de test)")
        parser.add_argument("--j-autorise-le-cout", action="store_true", dest="autorise")

    def handle(self, *args, **options):
        modele = settings.IA_MODELE
        etapes = [
            ("lecture", settings.IA_LECTURE_MODELE or modele, settings.IA_LECTURE_MAX_TOKENS, 4000),
            ("correction", settings.IA_CORRECTION_MODELE or modele, settings.IA_CORRECTION_MAX_TOKENS, 4000),
            ("professeur_plan", settings.IA_PROF_MODELE or modele, settings.IA_PROF_MAX_TOKENS_PLAN, 4000),
            ("professeur_tour", settings.IA_PROF_MODELE or modele, min(settings.IA_PROF_MAX_TOKENS_TOUR, settings.IA_MAX_TOKENS_SORTIE_PAR_REPONSE), 4000),
        ]
        total = 0
        self.stdout.write("Coût MAXIMAL prévu par étape (tous les tokens de sortie autorisés produits), en FCFA estimés :")
        for nom, mod, sortie_max, entree in etapes:
            cout = tarifs.usd_vers_fcfa(tarifs.cout_usd(mod, entree=entree, sortie=sortie_max))
            total += cout
            self.stdout.write(f"  {nom:<16} modèle={mod} sortie_max={sortie_max} -> {cout} FCFA")
        self.stdout.write(f"TOTAL MAXIMAL : {total} FCFA (taux {settings.IA_TAUX_USD_FCFA} du {settings.IA_TAUX_USD_FCFA_DATE}, marge {settings.IA_MARGE_SECURITE}).")
        self.stdout.write("Le coût réel est en pratique bien inférieur : la plupart des réponses n'utilisent pas tout le plafond.")
        if not options["autorise"]:
            self.stdout.write("Aucun appel effectué (mode estimation). Ajouter --j-autorise-le-cout après accord explicite.")
            return
        if not options["telephone"]:
            raise CommandError("--telephone obligatoire avec --j-autorise-le-cout.")
        self._lancer(options["telephone"])

    def _lancer(self, telephone: str):
        from comptes.models import User
        from programme.correction import resolution
        from programme.lecture_exercice import ContexteProgramme, PageExercice, lire_exercice
        from programme.professeur import seance

        eleve = User.objects.filter(telephone=telephone, role=User.Role.ELEVE).first()
        if not eleve:
            raise CommandError("Élève de développement introuvable.")
        contexte = ContexteProgramme(matiere="Mathématiques", classe="Terminale C")
        avant = set(OperationIA.objects.values_list("pk", flat=True))
        lu = lire_exercice(utilisateur_id=eleve.id, programme_id=0, contexte=contexte, pages=[], enonce=ENONCE)
        self.stdout.write(f"lecture : {'cache' if lu.depuis_cache else 'appel réel'}")
        from programme.correction.service import corriger_exercice
        corriger_exercice(utilisateur_id=eleve.id, programme_id=0, contexte=contexte, analyse_brute=lu.analyse)
        etat = seance.demarrer(utilisateur_id=eleve.id, programme_id=0, contexte=contexte, analyse_brute=lu.analyse)
        seance.explication(etat["id"], eleve.id, etat["version"], "incomprehension")
        self.stdout.write("Opérations enregistrées :")
        for op in OperationIA.objects.exclude(pk__in=avant).order_by("pk"):
            self.stdout.write(f"  {op.fonctionnalite:<16} {op.statut:<9} entrée={op.tokens_entree} sortie={op.tokens_sortie} coût={op.cout_fcfa} FCFA")
        b = budget.mois_et_jour()[0]
        self.stdout.write(f"Mois {b} : voir le rapport admin /api/admin/budget-ia/.")
