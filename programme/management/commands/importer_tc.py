"""
Import du programme officiel de Mathématiques — Terminale C (Niger).

Usage :
    python manage.py importer_tc

Idempotent : relançable sans créer de doublons (get_or_create partout).
Pour repartir de zéro sur ce seul programme :
    python manage.py importer_tc --reset
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from programme.models import (
    Cycle, Niveau, Serie, Matiere,
    Programme, Theme, Chapitre, Notion,
)


# ============================================================
#  DONNÉES DU PROGRAMME (structure : thèmes → chapitres → notions)
#  Chaque notion : (titre, contenus, objectifs, commentaires)
# ============================================================

PROGRAMME_TC = [
    {
        "theme": "Thème 1 — Organisation des calculs / Calculs numériques",
        "volume_horaire": 48,
        "chapitres": [
            {
                "titre": "Arithmétique",
                "notions": [
                    (
                        "Entiers relatifs et congruences",
                        "Anneau ℤ des entiers relatifs ; multiples d'un entier relatif "
                        "(notation nℤ, n ∈ ℕ*) ; sous-groupes de ℤ ; division euclidienne "
                        "dans ℕ et ℤ ; numération décimale et binaire ; congruence modulo n ; "
                        "anneau ℤ/nℤ.",
                        "Définir un anneau\n"
                        "Déterminer les multiples d'un entier relatif\n"
                        "Déterminer les sous-groupes de ℤ\n"
                        "Déterminer les diviseurs d'un entier relatif\n"
                        "Écrire un entier en numération décimale et binaire\n"
                        "Définir la congruence modulo n\n"
                        "Utiliser les propriétés des congruences pour résoudre des problèmes\n"
                        "Déterminer l'anneau ℤ/nℤ",
                        "",
                    ),
                    (
                        "PGCD et PPCM",
                        "Algorithme d'Euclide ; propriétés du PGCD et du PPCM ; nombres "
                        "premiers entre eux ; identité de Bézout et théorème de Gauss ; "
                        "résolution d'équations du premier degré dans ℤ² et (ℤ/nℤ)².",
                        "Utiliser l'algorithme d'Euclide pour déterminer le PGCD\n"
                        "Utiliser les propriétés du PGCD et du PPCM\n"
                        "Définir deux nombres premiers entre eux\n"
                        "Reconnaître et utiliser les théorèmes de Bézout et de Gauss\n"
                        "Résoudre dans ℤ² les équations du type ax + by = c\n"
                        "Résoudre dans ℤ/pℤ des équations et systèmes de 2 équations à 2 inconnues",
                        "Énoncer sans démontrer les théorèmes de Bézout et de Gauss.",
                    ),
                    (
                        "Nombres premiers dans ℤ",
                        "Définition ; diviseurs premiers d'un entier naturel ; nombre premier "
                        "et divisibilité ; corps ℤ/pℤ lorsque p est premier ; décomposition "
                        "d'un entier en produit de facteurs premiers (existence et unicité).",
                        "Définir un nombre premier dans ℤ\n"
                        "Utiliser les propriétés des nombres premiers\n"
                        "Établir que ℤ/pℤ est un corps lorsque p est premier\n"
                        "Décomposer un entier en produit de facteurs premiers",
                        "Sortir la notion de corps sans faire de théorie. "
                        "La démonstration n'est pas exigible.",
                    ),
                ],
            },
            {
                "titre": "Nombres complexes",
                "notions": [
                    (
                        "Différentes formes d'un nombre complexe",
                        "Le corps ℂ des nombres complexes ; forme algébrique ; conjugué ; "
                        "représentation géométrique, affixe d'un point et d'un vecteur ; "
                        "module ; argument d'un complexe non nul ; forme trigonométrique ; "
                        "notation z = r e^(iθ).",
                        "Définir le corps ℂ\n"
                        "Donner les différentes écritures (algébrique, trigonométrique, exponentielle)\n"
                        "Représenter graphiquement un complexe\n"
                        "Déterminer module et argument\n"
                        "Interpréter le module et l'argument de z_B − z_A et de "
                        "(z_C − z_B)/(z_C − z_A) dans des problèmes de distance et d'angle "
                        "(alignement, cocyclicité)",
                        "La construction algébrique de ℂ n'est pas au programme. "
                        "On pourra introduire ℂ à partir de la non-existence de solution "
                        "réelle de x² + 1 = 0.",
                    ),
                    (
                        "Applications de la forme trigonométrique",
                        "Formule de Moivre ; linéarisation ; transformation de cos nx et "
                        "sin nx en polynôme de cos x et sin x ; racines n-ièmes d'un "
                        "complexe ; interprétation géométrique.",
                        "Reconnaître et utiliser les formules de Moivre et d'Euler\n"
                        "Linéariser un polynôme trigonométrique (degré ≤ 5)\n"
                        "Déterminer et interpréter géométriquement la racine n-ième d'un complexe",
                        "",
                    ),
                    (
                        "Résolution dans ℂ d'équations du second degré",
                        "",
                        "Résoudre des équations du second degré dans ℂ\n"
                        "Résoudre une équation du 3ᵉ degré connaissant une racine",
                        "",
                    ),
                ],
            },
        ],
    },
    {
        "theme": "Thème 2 — Géométrie plane",
        "volume_horaire": 60,
        "chapitres": [
            {
                "titre": "Calculs barycentriques",
                "notions": [
                    (
                        "Barycentre de n points",
                        "Définition ; propriétés.",
                        "Définir le barycentre de n points",
                        "",
                    ),
                    (
                        "Lignes de niveau",
                        "Fonction scalaire de Leibniz. Exemple : MA/MB = k.",
                        "Établir les formules réduites des expressions Σαᵢ·MAᵢ et "
                        "Σαᵢ·‖MAᵢ‖² et les utiliser",
                        "C'est l'occasion de généraliser les propriétés vues dans les "
                        "classes antérieures.",
                    ),
                ],
            },
            {
                "titre": "Applications affines du plan",
                "notions": [
                    (
                        "Généralités",
                        "Définition ; propriétés ; application linéaire associée à une "
                        "application affine ; matrice d'une application linéaire.",
                        "Définir une application affine\n"
                        "Déterminer l'image d'une droite, d'un plan\n"
                        "Définir et déterminer l'application linéaire associée\n"
                        "Déterminer la matrice d'une application linéaire\n"
                        "Utiliser les propriétés pour des démonstrations",
                        "L'application affine sera définie comme conservant le barycentre. "
                        "Il ne s'agira pas de faire une théorie sur les matrices.",
                    ),
                    (
                        "Applications affines particulières (isométries)",
                        "Isométries affines ; isométrie vectorielle associée ; translations ; "
                        "symétries orthogonales ; symétries centrales ; rotations ; symétrie "
                        "glissée ; classification des isométries.",
                        "Définir une isométrie affine et l'isométrie vectorielle associée\n"
                        "Reconnaître ces applications comme isométries\n"
                        "Classer les isométries en déplacements et antidéplacements selon "
                        "leurs points invariants",
                        "Une isométrie affine conserve la distance ; l'isométrie vectorielle "
                        "conserve le produit scalaire.",
                    ),
                    (
                        "Similitudes planes directes et indirectes",
                        "Définition ; caractérisation ; propriétés.",
                        "Définir une similitude\n"
                        "Déterminer l'application complexe associée et réciproquement\n"
                        "Déterminer les éléments caractéristiques\n"
                        "Déterminer l'expression analytique\n"
                        "Construire les images de figures simples\n"
                        "Utiliser : f similitude ⇔ d(f(A),f(B)) = k·d(A,B)",
                        "Une similitude est la composée d'une isométrie et d'une homothétie.",
                    ),
                    (
                        "Projections, affinités",
                        "Définitions ; propriétés.",
                        "Définir ces applications affines\n"
                        "Utiliser leurs propriétés pour construire et résoudre des problèmes",
                        "",
                    ),
                ],
            },
            {
                "titre": "Coniques",
                "notions": [
                    (
                        "Coniques",
                        "Définitions géométriques (foyer et directrice) ; équations "
                        "cartésiennes réduites ; équation d'une hyperbole rapportée à ses "
                        "asymptotes ; équations paramétriques ; tangente en un point.",
                        "Définir une conique et reconnaître ses éléments caractéristiques\n"
                        "Déterminer une équation cartésienne ou paramétrique\n"
                        "Déterminer la nature et les éléments caractéristiques\n"
                        "Tracer la tangente en un point\n"
                        "Représenter graphiquement une conique",
                        "Introduction via la ligne de niveau MF/MH = e. "
                        "Traiter des exemples de régionnement du plan.",
                    ),
                ],
            },
        ],
    },
    {
        "theme": "Thème 3 — Géométrie dans l'espace",
        "volume_horaire": 32,
        "chapitres": [
            {
                "titre": "Applications affines de l'espace",
                "notions": [
                    (
                        "Applications affines de l'espace",
                        "Translation ; homothétie ; symétrie orthogonale par rapport à un "
                        "plan ou une droite ; rotation ; vissage ; isométries de l'espace.",
                        "Définir ces applications\n"
                        "Reconnaître celles qui sont des isométries\n"
                        "Construire le transformé d'un point\n"
                        "Utiliser leurs propriétés pour démontrer alignement, parallélisme, "
                        "orthogonalité\n"
                        "Classer les isométries à partir des points invariants",
                        "L'étude se fera sur des exemples.",
                    ),
                ],
            },
        ],
    },
    {
        "theme": "Thème 4 — Organisation des données",
        "volume_horaire": 68,
        "chapitres": [
            {
                "titre": "Suites numériques",
                "notions": [
                    (
                        "Raisonnement par récurrence",
                        "",
                        "Utiliser le raisonnement par récurrence pour établir certaines propriétés",
                        "",
                    ),
                    (
                        "Convergence d'une suite",
                        "Propriétés de convergence ; suites divergentes ; exemples "
                        "(uₙ = aⁿ, uₙ = nᵅ, uₙ₊₁ = f(uₙ), uₙ₊₁ = a·uₙ + b·uₙ₋₁) ; "
                        "théorèmes de comparaison.",
                        "Démontrer qu'une suite est convergente\n"
                        "Utiliser : toute suite croissante majorée (resp. décroissante "
                        "minorée) est convergente\n"
                        "Utiliser : si uₙ₊₁ = f(uₙ), (uₙ) convergente de limite l et f "
                        "continue en l, alors f(l) = l\n"
                        "Utiliser les théorèmes de comparaison",
                        "Les suites arithmétiques et géométriques ne seront pas reprises "
                        "mais utilisées. Les propriétés de comparaison seront admises.",
                    ),
                ],
            },
            {
                "titre": "Fonctions logarithmes",
                "notions": [
                    (
                        "Fonction logarithme népérien",
                        "Définition ; premières propriétés algébriques ; dérivée ; limites ; "
                        "représentation graphique.",
                        "Définir la fonction ln\n"
                        "Utiliser ses propriétés\n"
                        "Utiliser la dérivée de x ↦ ln(u(x))\n"
                        "Utiliser les limites : lim(x→0⁺) x·ln x = 0 ; "
                        "lim(x→+∞) (ln x)/xᵅ = 0 (α > 0) ; lim(x→0) ln(x+1)/x = 1 ; "
                        "lim(x→1) ln x/(x−1) = 1\n"
                        "Représenter graphiquement ln",
                        "Introduire ln comme la primitive sur ℝ*₊ de x ↦ 1/x qui s'annule en 1.",
                    ),
                    (
                        "Fonction logarithme de base a",
                        "",
                        "Étudier et représenter la fonction logarithme de base a "
                        "(a ∈ ℝ*₊ \\ {1})",
                        "Définie par log_a(x) = ln x / ln a. Insister sur le cas a = 10.",
                    ),
                ],
            },
            {
                "titre": "Propriétés des fonctions continues ou dérivables sur un intervalle",
                "notions": [
                    (
                        "Continuité, dérivabilité, bijection",
                        "Théorème des valeurs intermédiaires ; fonction réciproque ; "
                        "dérivée d'une composée, de la réciproque d'une bijection ; "
                        "notation df/dx, d²f/dx².",
                        "Déterminer l'image d'un intervalle par une fonction continue\n"
                        "Reconnaître et utiliser le TVI\n"
                        "Utiliser continuité et stricte monotonie pour montrer qu'une "
                        "fonction est une bijection\n"
                        "Déterminer les dérivées d'une composée ou d'une réciproque",
                        "Les démonstrations des théorèmes ne sont pas exigibles.",
                    ),
                ],
            },
            {
                "titre": "Fonctions exponentielles",
                "notions": [
                    (
                        "Fonction exponentielle de base e",
                        "Définition ; représentation graphique ; propriétés algébriques ; "
                        "dérivée ; limites.",
                        "Définir exp\n"
                        "Utiliser ses propriétés\n"
                        "Utiliser la dérivée de x ↦ e^(u(x))\n"
                        "Utiliser les limites : lim(x→+∞) xᵅ/eˣ = 0 ; lim(x→+∞) eˣ/x = +∞ ; "
                        "lim(x→+∞) x·e^(−x) = 0 ; lim(x→0) (eˣ−1)/x = 1",
                        "",
                    ),
                    (
                        "Fonction exponentielle de base a",
                        "Fonctions x ↦ aˣ (a ∈ ℝ*₊ \\ {1}).",
                        "Déterminer la réciproque de l'exponentielle de base a\n"
                        "Étudier et représenter cette fonction",
                        "Introduite par aˣ = e^(x·ln a).",
                    ),
                ],
            },
            {
                "titre": "Exemples d'étude de fonctions",
                "notions": [
                    (
                        "Étude de fonctions",
                        "Représentation graphique ; résolution d'équations et inéquations ; "
                        "point d'inflexion.",
                        "Utiliser une représentation graphique pour résoudre équations/inéquations\n"
                        "Rechercher directions asymptotiques et asymptotes\n"
                        "Déterminer la position d'une courbe par rapport à ses asymptotes et "
                        "à sa tangente\n"
                        "Étudier des fonctions rationnelles, irrationnelles, trigonométriques, "
                        "logarithmiques, exponentielles",
                        "",
                    ),
                ],
            },
            {
                "titre": "Encadrements et approximations",
                "notions": [
                    (
                        "Inégalité des accroissements finis",
                        "Inégalité des accroissements finis (1ʳᵉ et 2ᵉ forme) ; encadrement "
                        "d'une fonction (par des constantes, par 2 fonctions) ; approximation "
                        "d'un zéro d'une fonction.",
                        "Utiliser le théorème des accroissements finis\n"
                        "Encadrer une fonction par deux constantes, par deux fonctions\n"
                        "Déterminer une valeur approchée d'un zéro d'une fonction",
                        "Occasion d'utiliser le TVI.",
                    ),
                ],
            },
            {
                "titre": "Calcul intégral",
                "notions": [
                    (
                        "Intégrale d'une fonction continue",
                        "Définition ; propriétés (Chasles, linéarité, positivité, inégalité "
                        "de la moyenne) ; valeur moyenne.",
                        "Définir l'intégrale d'une fonction\n"
                        "Utiliser ses propriétés",
                        "La théorie de l'intégrale de Riemann est hors programme.",
                    ),
                    (
                        "Techniques du calcul intégral",
                        "Intégration par primitivation ; par changement de variable ; par parties.",
                        "Utiliser les techniques (primitives usuelles, intégration par parties, "
                        "changement de variables affines)",
                        "",
                    ),
                    (
                        "Fonctions définies par une intégrale",
                        "",
                        "Étudier et représenter des fonctions définies par une intégrale",
                        "",
                    ),
                    (
                        "Applications du calcul intégral",
                        "Encadrements à l'aide d'intégrales ; calcul d'aires ; calcul de volumes.",
                        "Déterminer une valeur approchée d'une intégrale\n"
                        "Calculer l'aire d'un domaine plan\n"
                        "Calculer des volumes (pyramide, cône, boule)",
                        "Méthode des rectangles pour les valeurs approchées.",
                    ),
                ],
            },
            {
                "titre": "Équations différentielles",
                "notions": [
                    (
                        "Équations différentielles linéaires homogènes",
                        "Équations linéaires homogènes du 1ᵉʳ et 2ᵉ ordre à coefficients "
                        "constants ; définition ; résolution.",
                        "Définir et résoudre ces équations",
                        "Les équations avec second membre (non homogènes) ne sont pas au programme.",
                    ),
                ],
            },
            {
                "titre": "Probabilité sur un ensemble fini",
                "notions": [
                    (
                        "Notion de probabilité",
                        "Définition ; vocabulaire ; calcul par dénombrement.",
                        "Définir une probabilité\n"
                        "Reconnaître le vocabulaire\n"
                        "Déterminer la probabilité d'un événement\n"
                        "Retrouver et utiliser les propriétés",
                        "La probabilité d'un événement est toujours comprise entre 0 et 1. "
                        "Faire le lien avec les statistiques.",
                    ),
                    (
                        "Probabilité conditionnelle",
                        "Définition ; événements indépendants ; produit de n espaces "
                        "probabilisés finis.",
                        "Utiliser P_B(A) = P(A∩B)/P(B)\n"
                        "Reconnaître et utiliser la formule de la probabilité totale\n"
                        "Reconnaître des événements indépendants\n"
                        "Définir le produit de n espaces probabilisés finis",
                        "Pour la probabilité totale, se limiter au cas n = 3. "
                        "Pour le produit, se limiter à n = 2.",
                    ),
                ],
            },
            {
                "titre": "Variables aléatoires",
                "notions": [
                    (
                        "Variable aléatoire",
                        "Définition ; loi de probabilité ; espérance, variance, écart-type ; "
                        "fonction de répartition ; loi binomiale ; schéma de Bernoulli, "
                        "épreuves répétées.",
                        "Définir une variable aléatoire réelle\n"
                        "Déterminer sa loi de probabilité\n"
                        "Déterminer espérance, variance, écart-type\n"
                        "Déterminer la fonction de répartition\n"
                        "Définir et utiliser la loi binomiale",
                        "",
                    ),
                ],
            },
            {
                "titre": "Séries statistiques à deux variables",
                "notions": [
                    (
                        "Séries statistiques doubles",
                        "Nuage de points ; point moyen ; droites de régression ; "
                        "coefficient de corrélation.",
                        "Représenter un nuage de points\n"
                        "Déterminer le point moyen\n"
                        "Déterminer les équations des droites de régression et les tracer\n"
                        "Calculer et interpréter le coefficient de corrélation",
                        "La corrélation est bonne quand |r| ∈ [0,87 ; 1].",
                    ),
                ],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Importe le programme officiel de Mathématiques — Terminale C"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime le programme Maths Tle C existant avant réimport.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Rangement administratif
        cycle, _ = Cycle.objects.get_or_create(
            nom="Second cycle", defaults={"ordre": 2}
        )
        niveau, _ = Niveau.objects.get_or_create(
            cycle=cycle, nom="Terminale", defaults={"ordre": 3}
        )
        serie, _ = Serie.objects.get_or_create(niveau=niveau, nom="C")
        matiere, _ = Matiere.objects.get_or_create(nom="Mathématiques")

        # 2. Programme
        programme, cree = Programme.objects.get_or_create(
            matiere=matiere, niveau=niveau, serie=serie
        )

        if options["reset"] and not cree:
            programme.themes.all().delete()
            self.stdout.write(self.style.WARNING("Anciens thèmes supprimés (--reset)."))

        # 3. Thèmes → Chapitres → Notions
        n_themes = n_chap = n_notions = 0
        for i, bloc in enumerate(PROGRAMME_TC, start=1):
            theme, _ = Theme.objects.get_or_create(
                programme=programme,
                titre=bloc["theme"],
                defaults={"volume_horaire": bloc["volume_horaire"], "ordre": i},
            )
            n_themes += 1

            for j, chap in enumerate(bloc["chapitres"], start=1):
                chapitre, _ = Chapitre.objects.get_or_create(
                    theme=theme, titre=chap["titre"], defaults={"ordre": j}
                )
                n_chap += 1

                for k, (titre, contenus, objectifs, commentaires) in enumerate(
                    chap["notions"], start=1
                ):
                    Notion.objects.get_or_create(
                        chapitre=chapitre,
                        titre=titre,
                        defaults={
                            "ordre": k,
                            "contenus_officiels": contenus,
                            "objectifs_officiels": objectifs,
                            "commentaires_officiels": commentaires,
                        },
                    )
                    n_notions += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nImport terminé : {programme}\n"
            f"  {n_themes} thèmes, {n_chap} chapitres, {n_notions} notions."
        ))
