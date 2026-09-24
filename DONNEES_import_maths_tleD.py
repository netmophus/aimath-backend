# DONNÉES D'IMPORT — Mathématiques Terminale D
# Source : programme officiel nigérien (PDF second cycle, pages 243-249).
# → L'agent transforme ceci en commande Django (modèle importer_physique_tc /
#   importer_chimie_tc), attachée au programme MATHÉMATIQUES × Terminale × D.
#
# ATTENTION : le programme Mathématiques × Tle D doit exister en base. S'il
# n'existe pas, la commande le signale, ne l'invente pas.
#
# Le programme maths Tle D a 3 thèmes. Certains chapitres comportent plusieurs
# NOTIONS (numérotées 1-, 2-, 3- dans le PDF) → 1 notion par sous-partie
# numérotée ; les chapitres sans numérotation = 1 notion (titre du chapitre).

MATHS_TLE_D = [
  {
    "theme": "Organisation des calculs — Calculs numériques",
    "volume_horaire": 24,
    "chapitres": [
      {
        "titre": "Nombres complexes",
        "notions": [
          {
            "titre": "Différentes formes d'un nombre complexe",
            "contenus": "Le corps des nombres complexes. Forme algébrique. Conjugué d'un nombre complexe. Représentation géométrique d'un nombre complexe, affixe d'un point, d'un vecteur. Module d'un nombre complexe. Argument d'un nombre complexe non nul. Forme trigonométrique d'un nombre complexe non nul. Notation z = r·e^(iθ).",
            "objectifs": "Définir le corps ℂ des nombres complexes. Donner les différentes écritures d'un nombre complexe : algébrique, trigonométrique, exponentielle. Représenter graphiquement un nombre complexe. Déterminer le module et un argument d'un nombre complexe. Interpréter le module et l'argument de z_B − z_A et de (z_C − z_B)/(z_C − z_A), z_A, z_B, z_C étant des nombres complexes, dans des problèmes de distance et d'angle (alignement, cocyclicité).",
            "commentaires": "La construction algébrique de ℂ n'est pas au programme. On pourra introduire ℂ à partir de la non-existence de solution réelle de l'équation x² + 1 = 0."
          },
          {
            "titre": "Applications de la forme trigonométrique d'un nombre complexe",
            "contenus": "Formule de Moivre. Linéarisation ; transformation de cos(nx) et sin(nx) en polynôme de cos x et sin x. Racines n-ièmes d'un nombre complexe. Interprétation géométrique.",
            "objectifs": "Reconnaître et utiliser les formules de Moivre et d'Euler. Linéariser un polynôme trigonométrique (degré inférieur ou égal à 5). Déterminer et interpréter géométriquement la racine n-ième d'un nombre complexe.",
            "commentaires": "(non renseigné)"
          },
          {
            "titre": "Résolution dans ℂ d'équations du second degré",
            "contenus": "Résolution dans ℂ d'équations du second degré.",
            "objectifs": "Résoudre des équations du second degré dans ℂ. Résoudre une équation du 3ème degré connaissant une racine.",
            "commentaires": "(non renseigné)"
          }
        ]
      }
    ]
  },
  {
    "theme": "Applications affines du plan",
    "volume_horaire": 9,
    "chapitres": [
      {
        "titre": "Similitudes planes directes",
        "contenus": "Similitudes planes directes : application affine associée à une application complexe, éléments caractéristiques, expression analytique, forme complexe, images de figures simples.",
        "objectifs": "Déterminer l'application affine associée à l'application complexe z ↦ az + b, (a, b) ∈ ℂ. Déterminer les éléments caractéristiques et l'expression analytique d'une similitude plane directe. Déterminer la forme complexe d'une similitude plane directe à partir de ses éléments caractéristiques. Déterminer l'image de figures simples (droite, cercle) par une similitude plane directe.",
        "commentaires": "(non renseigné)"
      }
    ]
  },
  {
    "theme": "Organisation des données",
    "volume_horaire": 123,
    "chapitres": [
      {
        "titre": "Suites numériques",
        "notions": [
          {
            "titre": "Raisonnement par récurrence",
            "contenus": "Raisonnement par récurrence.",
            "objectifs": "Utiliser le raisonnement par récurrence pour établir certaines propriétés.",
            "commentaires": "(non renseigné)"
          },
          {
            "titre": "Convergence d'une suite",
            "contenus": "Propriétés de convergence des suites. Suites divergentes. Exemples de suites de la forme un = aⁿ, un = nᵅ, un+1 = f(un), un+1 = a·un + b·un−1 (a, b réels). Théorèmes de comparaison des suites : si à partir d'un certain rang un ≤ vn et lim un = +∞ alors lim vn = +∞ ; si |vn − L| ≤ un et lim un = 0 alors lim vn = L ; théorèmes d'encadrement et de comparaison des limites.",
            "objectifs": "Démontrer qu'une suite est convergente. Utiliser la propriété : toute suite croissante et majorée (resp. décroissante et minorée) est convergente. Utiliser la propriété : si un+1 = f(un), (un) convergente de limite l et f continue en l, alors f(l) = l. Utiliser les théorèmes de comparaison lors de la résolution des problèmes.",
            "commentaires": "Les suites arithmétiques et géométriques ne seront pas reprises mais seront utilisées dans les activités ; par exemple, pour étudier la convergence d'une suite un+1 = a·un + b (a ≠ 1), on étudie la convergence de vn = un − b/(1−a). Ces propriétés seront admises."
          }
        ]
      },
      {
        "titre": "Fonctions logarithmes",
        "notions": [
          {
            "titre": "Fonction logarithme népérien",
            "contenus": "Définition. Premières propriétés algébriques. Dérivée. Limites. Représentation graphique.",
            "objectifs": "Définir la fonction logarithme népérien. Utiliser les propriétés de la fonction logarithme népérien dans la résolution des problèmes. Utiliser la dérivée de x ↦ ln(u(x)). Utiliser les limites : lim(x→0) x·ln x = 0 ; lim(x→+∞) (ln x)/xᵅ = 0 (α > 0) ; lim(x→0) ln(x+1)/x = 1 ; lim(x→1) ln x/(x−1) = 1. Représenter graphiquement la fonction logarithme népérien.",
            "commentaires": "On introduira la fonction logarithme népérien comme la primitive sur ℝ*₊ de la fonction x ↦ 1/x qui s'annule en x = 1."
          },
          {
            "titre": "Fonction logarithme de base a",
            "contenus": "Fonction logarithme de base a (a ∈ ℝ*₊ − {1}).",
            "objectifs": "Étudier et représenter la fonction logarithme de base a (a ∈ ℝ*₊ − {1}).",
            "commentaires": "La fonction logarithme de base a sera définie par log_a(x) = ln x / ln a. On insistera sur le cas particulier où a = 10."
          }
        ]
      },
      {
        "titre": "Propriétés des fonctions continues ou dérivables sur un intervalle",
        "contenus": "Théorème des valeurs intermédiaires. Fonction réciproque. Dérivée d'une application composée, de la réciproque d'une bijection. Notation df/dx ; d²f/dx².",
        "objectifs": "Déterminer l'image d'un intervalle par une fonction continue. Reconnaître et utiliser le théorème des valeurs intermédiaires. Utiliser la continuité et la stricte monotonie pour montrer qu'une application f est une bijection d'un intervalle I sur f(I). Déterminer et utiliser les fonctions dérivées d'une fonction composée ou de la réciproque d'une fonction si elle existe.",
        "commentaires": "Les démonstrations des différentes propriétés et théorèmes ne sont pas exigibles."
      },
      {
        "titre": "Fonction exponentielle",
        "contenus": "Définition. Représentation graphique. Propriétés algébriques. Dérivée. Limites. Fonctions x ↦ aˣ (a ∈ ℝ*₊ − {1}).",
        "objectifs": "Définir la fonction exponentielle de base e. Utiliser les propriétés de la fonction exponentielle de base e dans la résolution des problèmes. Utiliser la dérivée de x ↦ e^(u(x)). Utiliser les limites : pour α ∈ ℝ, lim(x→+∞) xᵅ/eˣ = 0 ; lim(x→+∞) eˣ/x = +∞ ; lim(x→+∞) x·e^(−x) = 0 ; lim(x→0) (eˣ−1)/x = 1. Déterminer la fonction réciproque de la fonction exponentielle de base a. Étudier et représenter la fonction exponentielle de base a (a ∈ ℝ*₊ − {1}).",
        "commentaires": "La fonction exponentielle de base a (a ∈ ℝ*₊ − {1}) sera introduite par aˣ = e^(x·ln a)."
      },
      {
        "titre": "Exemples d'étude de fonctions",
        "contenus": "Représentation graphique. Résolution d'équations et d'inéquations. Point d'inflexion.",
        "objectifs": "Utiliser la représentation graphique pour résoudre une équation, une inéquation. Rechercher les directions asymptotiques, les asymptotes. Déterminer la position de la courbe par rapport aux asymptotes. Déterminer la position d'une courbe par rapport à sa tangente en un point donné. Étudier des exemples de fonctions rationnelles, irrationnelles, trigonométriques, logarithmiques et exponentielles avec ou sans paramètre.",
        "commentaires": "L'utilisation du paramètre se fera dans des cas simples."
      },
      {
        "titre": "Calcul intégral",
        "notions": [
          {
            "titre": "Intégrale d'une fonction continue sur un intervalle",
            "contenus": "Définition. Propriétés : relation de Chasles ; linéarité ; positivité ; inégalité de la moyenne. Valeur moyenne d'une fonction.",
            "objectifs": "Définir l'intégrale d'une fonction. Utiliser les propriétés de l'intégrale dans la résolution des problèmes.",
            "commentaires": "La théorie de l'intégrale de Riemann est hors programme. Définition recommandée : soit f continue sur un intervalle I ; pour tout couple (a,b) de I², le réel F(b) − F(a) est indépendant du choix de la primitive F ; on le note ∫ₐᵇ f(t) dt. La fonction x ↦ ∫ₐˣ f(t) dt est l'unique primitive de f sur I prenant la valeur 0 en a."
          },
          {
            "titre": "Techniques de calcul intégral",
            "contenus": "Intégration par primitivation. Intégration par changement de variable. Intégration par parties.",
            "objectifs": "Utiliser les techniques de calcul intégral (formules des primitives usuelles, intégration par parties, changement de variables affines) pour calculer des intégrales.",
            "commentaires": "(non renseigné)"
          },
          {
            "titre": "Applications de l'intégration",
            "contenus": "Encadrements à l'aide d'intégrales. Calcul d'aires. Calcul de volumes.",
            "objectifs": "Déterminer une valeur approchée d'une intégrale. Calculer l'aire d'un domaine plan. Calculer des volumes (pyramide, cône et boule).",
            "commentaires": "On utilisera la méthode des rectangles pour déterminer une valeur approchée d'une intégrale."
          }
        ]
      },
      {
        "titre": "Équations différentielles",
        "contenus": "Équations différentielles linéaires homogènes du 1er et du 2ème ordre à coefficients constants. Définition. Résolution.",
        "objectifs": "Définir les équations différentielles linéaires homogènes du 1er et du second ordre à coefficients constants. Résoudre les équations différentielles linéaires homogènes du 1er et du second ordre à coefficients constants.",
        "commentaires": "Les équations différentielles linéaires avec second membre (non homogènes) ne sont pas au programme."
      },
      {
        "titre": "Probabilité sur un ensemble fini",
        "notions": [
          {
            "titre": "Notion de probabilité",
            "contenus": "Définition. Vocabulaire. Calcul des probabilités par dénombrement.",
            "objectifs": "Définir une probabilité. Reconnaître le vocabulaire relatif. Déterminer la probabilité d'un événement. Retrouver quelques propriétés des probabilités et les utiliser.",
            "commentaires": "On fera remarquer que la probabilité d'un événement est toujours comprise entre 0 et 1. Faire le lien entre les statistiques et les probabilités. Pour la loi de probabilité totale, se limiter au plus au cas n = 3."
          },
          {
            "titre": "Probabilité conditionnelle",
            "contenus": "Définition. Événements indépendants. Produit de n espaces probabilisés finis.",
            "objectifs": "Utiliser la formule P_B(A) = P(A∩B)/P(B), P(B) ≠ 0. Reconnaître et utiliser la formule de la probabilité totale. Reconnaître des événements indépendants. Définir le produit de n espaces probabilisés finis.",
            "commentaires": "On se limitera au cas n = 2. On admettra les résultats généraux."
          }
        ]
      },
      {
        "titre": "Variables aléatoires",
        "contenus": "Notion de variable aléatoire. Loi de probabilité : espérance mathématique, variance et écart-type. Fonction de répartition. Loi binomiale : schéma de Bernoulli, épreuves répétées.",
        "objectifs": "Définir une variable aléatoire réelle. Déterminer la loi de probabilité d'une variable aléatoire réelle. Déterminer l'espérance mathématique, la variance, l'écart-type d'une variable aléatoire. Déterminer la fonction de répartition d'une variable aléatoire réelle. Définir et utiliser la loi binomiale.",
        "commentaires": "La fonction de répartition d'une variable aléatoire réelle X est la fonction qui à tout réel x associe le réel P(X ≤ x)."
      },
      {
        "titre": "Séries statistiques à deux variables (doubles)",
        "contenus": "Nuage de points, point moyen. Droites de régression. Coefficient de corrélation.",
        "objectifs": "Représenter un nuage de points. Déterminer le point moyen. Déterminer les équations des droites de régression et tracer ces droites. Calculer et interpréter le coefficient de corrélation.",
        "commentaires": "Montrer l'utilisation des calculatrices scientifiques et programmables, mais les calculatrices programmables ne seront pas utilisées lors des évaluations. Les formules donnant les coefficients des droites de régression peuvent être établies pour trois ou quatre points puis être admises. On estimera que la corrélation est bonne quand la valeur absolue du coefficient de corrélation est comprise entre 0,87 et 1."
      }
    ]
  }
]

# Récapitulatif (compté sur le contenu réel) :
# Thème 1 : 1 chapitre (Nombres complexes) → 3 notions
# Thème 2 : 1 chapitre (Similitudes) → 1 notion
# Thème 3 : 10 chapitres → Suites (2 notions), Logarithmes (2), Propriétés
#   fonctions (1), Exponentielle (1), Études de fonctions (1), Calcul intégral
#   (3), Équations différentielles (1), Probabilité (2), Variables aléatoires
#   (1), Séries stat doubles (1) = 15 notions
# TOTAL : 3 thèmes, 12 chapitres, 19 notions.
#
# NOTE STRUCTURE : contrairement à la physique/chimie (1 chapitre = 1 notion),
# les maths Tle D ont des chapitres à PLUSIEURS notions (clé "notions": [...])
# ET des chapitres à notion unique (clés contenus/objectifs/commentaires
# directement sur le chapitre → 1 notion de même titre que le chapitre).
# La commande d'import doit gérer LES DEUX cas.
