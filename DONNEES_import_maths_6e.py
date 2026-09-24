# DONNÉES D'IMPORT — Mathématiques 6e (premier cycle / collège)
# Source : programme officiel nigérien (PDF premier cycle, pages 158-168).
# Horaire hebdomadaire : 7h. Coefficient : 3.
#
# → L'agent transforme ceci en commande Django (modèle importer_maths_td /
#   importer_physique_tc), attachée au programme MATHÉMATIQUES × 6e.
#
# ATTENTION : contrairement au lycée (Terminale × série C/D), le collège n'a
# PAS de série. La classe est le NIVEAU "6e" (ou "Sixième"), sans série.
# → Le programme visé est Mathématiques × niveau "6e" (série = null / vide).
#   Il faut que ce niveau "6e" (premier cycle) existe dans la base, et le
#   programme Mathématiques × 6e. S'il n'existe pas, la commande le signale,
#   ne l'invente pas.
#
# 7 thèmes. 1 chapitre = 1 notion (comme physique/chimie Tle C).

MATHS_6E = [
  {
    "theme": "Configurations de l'espace",
    "volume_horaire": 11,
    "chapitres": [
      {
        "titre": "Cube et pavé droit",
        "contenus": "Observation et description du solide. Vocabulaire. Construction d'un patron. Réalisation du solide. Calculs d'aires et de volumes.",
        "objectifs": "Dénombrer les sommets, les arêtes, les faces d'un pavé droit, d'un cube. Décrire les positions des éléments les uns par rapport aux autres. Reconnaître dans un ensemble de solides un cube, un pavé droit. Reconnaître et dessiner un patron d'un cube, d'un pavé droit. Réaliser un cube, un pavé droit à partir de leurs patrons. Calculer l'aire, le volume d'un cube, d'un pavé droit.",
        "commentaires": "Le professeur amènera l'élève à reconnaître les solides, à les décrire, à connaître le vocabulaire. On insistera sur la construction de plusieurs patrons du même solide. L'aire et le volume d'un cube d'arête a sont respectivement 6a² et a³. L'aire et le volume d'un pavé droit de dimensions a, b, c sont respectivement 2(ab + bc + ac) et abc."
      },
      {
        "titre": "Cylindre droit",
        "contenus": "Observation et description du solide. Vocabulaire. Construction d'un patron. Réalisation du solide. Calculs d'aires et de volumes.",
        "objectifs": "Reconnaître parmi les objets concrets ceux qui ont une forme cylindrique. Reconnaître et dessiner un patron d'un cylindre droit. Réaliser un cylindre à partir de son patron. Calculer l'aire, le volume d'un cylindre.",
        "commentaires": "Le professeur amènera l'élève à reconnaître le solide, à le décrire, à connaître le vocabulaire. On insistera sur la construction de plusieurs patrons du cylindre. L'aire et le volume d'un cylindre droit de rayon r et de hauteur h sont respectivement 2πr² + 2πrh et πr²h."
      }
    ]
  },
  {
    "theme": "Configurations du plan",
    "volume_horaire": 55,
    "chapitres": [
      {
        "titre": "Droites dans le plan",
        "contenus": "Droites ; points alignés ; demi-droites. Droites sécantes ; droites perpendiculaires. Droites parallèles : définition ; propriétés. Révision sur le voyage sur un quadrillage, agrandissement, réduction.",
        "objectifs": "Matérialiser le plan et un point. Représenter, nommer et tracer une droite passant par deux points. Vérifier l'alignement de points. Exprimer l'appartenance d'un point à une droite (symboles ∈ et ∉). Représenter, reconnaître, tracer et nommer une demi-droite. Vérifier et construire la perpendicularité de deux droites (pliage, équerre). Vérifier et construire des droites parallèles à la règle et à l'équerre. Utiliser la propriété : lorsque deux droites sont parallèles, toute sécante (resp. perpendiculaire) à l'une est sécante (resp. perpendiculaire) à l'autre.",
        "commentaires": "On donnera une vision intuitive du plan, assimilé à la feuille ou au tableau. Une droite peut être notée (D), (d), (AB). On insistera sur le caractère illimité de la droite et sur la différence entre droite et demi-droite. Notation [AB) pour la demi-droite d'origine A contenant B. Les parallèles sont introduites comme perpendiculaires à une même droite. Toute droite est parallèle à elle-même."
      },
      {
        "titre": "Segments",
        "contenus": "Segment ; support d'un segment. Longueur d'un segment ; mesure de cette longueur. Milieu d'un segment. Médiatrice d'un segment.",
        "objectifs": "Représenter, reconnaître, nommer et tracer un segment d'extrémités données. Comparer les longueurs de deux segments (compas, bande de papier). Mesurer la longueur d'un segment. Distinguer et utiliser correctement les notations [AB], [AB), (AB) et AB. Construire et vérifier le milieu d'un segment. Définir, reconnaître et construire la médiatrice d'un segment (règle-équerre, règle-compas). Vérifier que tout point de la médiatrice est à égale distance des extrémités.",
        "commentaires": "Un segment d'extrémités A et B est noté [AB]. On parlera d'inclusion : [AB] ⊂ (AB). On insistera sur la différence des notations. Les pliages introduisent la définition du milieu. On insistera sur l'alignement et l'égalité des longueurs."
      },
      {
        "titre": "Angles",
        "contenus": "Introduction de la notion d'angle. Vocabulaire. Mesure (en degrés). Angles adjacents, complémentaires, supplémentaires. Bissectrice d'un angle.",
        "objectifs": "Représenter un angle, identifier son sommet et ses côtés. Reconnaître les angles particuliers (nul, aigu, droit, obtus, plat). Comparer des angles. Mesurer un angle en degrés au rapporteur. Construire un angle de mesure donnée et un angle superposable. Reconnaître deux angles adjacents, complémentaires, supplémentaires. Tracer la bissectrice d'un angle (pliage, rapporteur, compas).",
        "commentaires": "Deux demi-droites de même origine [OA) et [OB) déterminent l'angle AOB. On se limitera aux angles saillants. La mesure de l'angle est celle du secteur angulaire, notée mes AOB. On insistera sur l'utilisation correcte du rapporteur."
      },
      {
        "titre": "Triangles",
        "contenus": "Vocabulaire. Triangles particuliers. Droites particulières : hauteurs, médiatrices, bissectrices, médianes. Périmètre, aire.",
        "objectifs": "Désigner un triangle sous des noms différents. Identifier côtés, sommets, angles, côté et sommet opposés. Construire un triangle connaissant les mesures des côtés et/ou des angles. Construire les triangles particuliers (isocèle, équilatéral, rectangle, isocèle rectangle). Coder et reconnaître un triangle particulier. Construire les droites particulières d'un triangle (pliage, instruments, main levée). Calculer le périmètre et l'aire d'un triangle.",
        "commentaires": "Faire la différence entre triangles superposables et triangles égaux. Éviter l'emploi du mot base ; faire varier les positions. Étudier les droites particulières l'une après l'autre. Utiliser (côté × hauteur correspondante)/2 pour l'aire."
      },
      {
        "titre": "Cercles",
        "contenus": "Centre ; rayon ; diamètre ; corde. Périmètre du cercle ; aire du disque.",
        "objectifs": "Définir un cercle, un disque. Tracer un cercle de centre et rayon donnés, de centre donné passant par un point, de diamètre donné. Distinguer rayon, diamètre, corde, arc, secteur circulaire. Utiliser les propriétés caractéristiques des points d'un cercle ou d'un disque. Utiliser les cercles dans des problèmes de construction. Calculer le périmètre d'un cercle et l'aire d'un disque.",
        "commentaires": "On insistera sur la différence entre cercle et disque : le centre est un point du disque mais pas du cercle."
      }
    ]
  },
  {
    "theme": "Applications du plan",
    "volume_horaire": 10,
    "chapitres": [
      {
        "titre": "Figures symétriques par rapport à une droite",
        "contenus": "Programme de construction. Droites, segments, angles symétriques par rapport à une droite.",
        "objectifs": "Reconnaître à vue si une figure admet un axe de symétrie et vérifier par pliage. Discerner des points qui se correspondent dans deux figures symétriques. Construire le symétrique d'un point, d'une figure simple (droite, segment, angle) par rapport à une droite. Reconnaître et construire les axes de symétrie d'une figure simple. Utiliser les axes de symétrie pour trouver des propriétés (égalité de longueurs, d'angles ; alignement).",
        "commentaires": "On utilisera le papier carbone, le découpage, les quadrillages. Exemples : motifs de pagnes, carrelages, feuilles d'arbres, panneaux de signalisation. On n'oubliera pas les cas particuliers de la médiatrice et de la bissectrice."
      },
      {
        "titre": "Figures symétriques par rapport à un point",
        "contenus": "Programme de construction. Droites, segments, angles symétriques par rapport à un point.",
        "objectifs": "Construire le symétrique par rapport à un point d'un point et de figures simples (droite, segment, angle). Reconnaître une configuration admettant un centre de symétrie et préciser ce centre. Établir un tableau de correspondance. Utiliser les centres de symétrie pour trouver des propriétés (égalité de longueurs, d'angles ; alignement de 3 points).",
        "commentaires": "(non renseigné)"
      }
    ]
  },
  {
    "theme": "Outil vectoriel — Géométrie analytique",
    "volume_horaire": 3,
    "chapitres": [
      {
        "titre": "Repérage d'un point sur une droite",
        "contenus": "Demi-droite graduée : origine, unité. Droite graduée : origine, unité, abscisse d'un point.",
        "objectifs": "Graduer une demi-droite. Repérer un décimal arithmétique par un point d'une demi-droite graduée. Graduer une droite. Repérer un décimal relatif par un point d'une droite graduée. Déterminer l'abscisse d'un point d'une droite graduée.",
        "commentaires": "Le chapitre sera traité en liaison avec les nombres décimaux. Pour repérer un décimal relatif, on utilisera la demi-droite des décimaux arithmétiques et le symétrique d'un point par rapport à un point donné."
      }
    ]
  },
  {
    "theme": "Organisation de calculs — Calculs numériques",
    "volume_horaire": 86,
    "chapitres": [
      {
        "titre": "Les entiers naturels",
        "contenus": "Ensemble ℕ des entiers naturels. Addition et multiplication dans ℕ. Comparaison d'entiers naturels. Multiples. Diviseurs. Caractères de divisibilité (par 10, 100, 1000 ; par 2, 5, 4, 25 ; par 3, 9).",
        "objectifs": "Noter l'ensemble ℕ, utiliser les symboles ∈ et ∉. Lire et écrire un nombre en chiffres et en lettres. Utiliser les propriétés de l'addition et de la multiplication. Comparer et ranger des entiers naturels (< et >). Reconnaître des entiers consécutifs. Utiliser les mots multiple, facteur, produit. Déterminer les multiples et diviseurs d'un entier. Reconnaître la divisibilité par 10, 100, 1000, 2, 5, 4, 25, 3, 9. Reconnaître si un entier est pair ou impair.",
        "commentaires": "On introduira les notions d'ensemble, d'élément et d'appartenance (∈) sans étude systématique. Le but n'est pas de nommer les propriétés (associativité, commutativité) mais de familiariser l'élève à leur usage en calcul mental. On se limite aux symboles < et >. On évitera de donner l'ensemble complet des multiples ou diviseurs."
      },
      {
        "titre": "Fractions",
        "contenus": "Notion de fraction. Différentes écritures d'une fraction ; simplification. Fraction décimale. Somme ou différence de deux fractions de même dénominateur. Comparaison de fractions. Produit de deux fractions.",
        "objectifs": "Utiliser les mots fraction, numérateur, dénominateur. Déterminer une fraction d'une quantité donnée. Reconnaître une fraction sous différentes écritures. Simplifier des fractions dans des cas simples. Reconnaître deux fractions égales et une fraction décimale. Déterminer la somme et la différence de deux fractions de même dénominateur. Comparer deux fractions de même dénominateur ou numérateur. Calculer le produit d'un entier par une fraction et le produit de deux fractions. Déterminer et utiliser l'inverse d'une fraction.",
        "commentaires": "On évitera de définir la fraction ; on l'abordera sur des exemples concrets (les 3/4 des élèves sont des filles ; découper les 2/3 d'une bande de papier). Exemple : en versant 120 L d'eau dans un tonneau, on le remplit aux 2/3 ; quelle est sa capacité ?"
      },
      {
        "titre": "Nombres décimaux arithmétiques",
        "contenus": "Opérations : addition, soustraction, multiplication, division. Comparaison. Estimation d'un résultat.",
        "objectifs": "Exprimer un nombre décimal sous forme de fraction. Reconnaître un nombre décimal sous différentes écritures. Calculer somme, différence, produit de deux décimaux. Diviser un décimal par un décimal. Utiliser les propriétés pour simplifier des calculs. Encadrer un décimal par deux entiers consécutifs. Comparer et ranger des décimaux. Donner un ordre de grandeur d'un résultat.",
        "commentaires": "On pourra introduire les décimaux à partir des fractions décimales. Multiplier par 0,1 ; 0,01 revient à diviser par 10 ; 100. On se limite aux inégalités < et >. Habituer les élèves à conjecturer une valeur approchée (autocontrôle)."
      },
      {
        "titre": "Nombres décimaux relatifs",
        "contenus": "Ensemble ℤ des entiers relatifs (notion, somme, comparaison). Ensemble 𝔻 des décimaux relatifs (notion, somme, opposé d'un nombre décimal).",
        "objectifs": "Lire et écrire un entier relatif. Faire la somme et la différence de deux entiers relatifs. Déterminer l'opposé d'un entier relatif et ranger les entiers relatifs. Lire et écrire un décimal relatif. Reconnaître ℕ et ℤ comme sous-ensembles de 𝔻. Déterminer la somme de deux décimaux relatifs, l'opposé d'un décimal relatif et l'opposé d'une somme. Traduire des situations concrètes de bilans.",
        "commentaires": "L'introduction des entiers relatifs se fera à partir d'exemples de la vie courante (bilans, températures, dates historiques). Pour les décimaux relatifs, on utilisera la demi-droite des décimaux arithmétiques et le symétrique d'un point."
      }
    ]
  },
  {
    "theme": "Organisation des calculs — Calcul littéral",
    "volume_horaire": 7,
    "chapitres": [
      {
        "titre": "Organisation des calculs",
        "contenus": "Utilisation des propriétés de l'addition et de la multiplication. Règles de priorité des opérations ; utilisation des parenthèses.",
        "objectifs": "Effectuer des calculs avec parenthèses. Reconnaître les règles de priorité des opérations.",
        "commentaires": "Le but n'est pas de nommer les propriétés (associativité, commutativité) mais de familiariser l'élève à leur utilisation. Il n'est pas question d'étudier la distributivité en soi."
      },
      {
        "titre": "Initiation au calcul littéral",
        "contenus": "Notion de variable et d'inconnue dans une formule.",
        "objectifs": "Reconnaître les lettres remplaçables (notion de variable) dans une formule (ex. L = 2 × 3,14 × R) ; les remplacer par des valeurs numériques données. Donner la notion d'inconnue.",
        "commentaires": "On s'appuiera sur des exemples (calculs de périmètres, d'aires, de volumes) pour montrer l'importance des parenthèses. L'inconnue est la quantité cherchée, désignée par une lettre."
      }
    ]
  },
  {
    "theme": "Organisation des données",
    "volume_horaire": 10,
    "chapitres": [
      {
        "titre": "Situation de proportionnalité",
        "contenus": "Tableau de proportionnalité. Coefficient de proportionnalité. Pourcentage. Échelle.",
        "objectifs": "Reconnaître deux suites proportionnelles de nombres. Trouver le coefficient de proportionnalité. Retrouver un nombre manquant dans deux suites proportionnelles. Représenter une situation de proportionnalité par un opérateur multiplicatif. Résoudre des problèmes de proportionnalité. Calculer le pourcentage ou l'échelle d'une situation donnée et utiliser ces opérateurs dans des problèmes concrets.",
        "commentaires": "Le professeur présentera exemples et contre-exemples de proportionnalité. La notion d'opérateur est connue sous le nom de machine au cycle de base I. On veillera à utiliser des échelles correspondant à des agrandissements comme à des réductions."
      },
      {
        "titre": "Statistiques",
        "contenus": "Lecture graphique.",
        "objectifs": "Lire et exploiter les informations afférentes à une représentation graphique d'une série statistique (géographie, économie, etc.).",
        "commentaires": "La lecture graphique est comprise dans le sens d'une exploitation des informations relatives à une représentation graphique (courbes de température, diagrammes à bandes, etc.)."
      }
    ]
  }
]

# Récapitulatif (compté sur le contenu réel) : 7 thèmes, 18 chapitres = 18 notions.
# Configurations de l'espace (2), Configurations du plan (5), Applications du
# plan (2), Outil vectoriel/Géométrie analytique (1), Organisation de calculs/
# Calculs numériques (4), Organisation des calculs/Calcul littéral (2),
# Organisation des données (2) → 2+5+2+1+4+2+2 = 18 notions attendues à l'import.
