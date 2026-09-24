# DONNÉES D'IMPORT — Chimie Terminale C
# Source : programme officiel nigérien (PDF second cycle, pages 324-332).
# En chimie : 1 chapitre = 1 notion (comme la physique).
# → L'agent transforme ceci en commande Django (sur le modèle importer_tc /
#   importer_physique_tc), attachée au programme CHIMIE × Terminale × C.
#
# ATTENTION : le programme CHIMIE × Tle C doit exister en base (matière
# "Chimie"). S'il n'existe pas, la commande doit le signaler, pas l'inventer.

CHIMIE_TLE_C = [
  {
    "theme": "Chimie générale : Acides et Bases en solution aqueuse",
    "volume_horaire": 16,
    "chapitres": [
      {
        "titre": "Solutions aqueuses",
        "contenus": "Eau solvant ionisant ; dissociation ionique de l'eau pure ; produit ionique de l'eau, pH de l'eau ; pH d'une solution ; solutions acides, solutions basiques.",
        "objectifs": "Expliquer la dispersion des ions lors de la dissolution d'un composé ionique dans l'eau. Expliquer l'ionisation d'un composé moléculaire polaire en présence d'eau. Exprimer l'électroneutralité d'une solution aqueuse. Expliquer la dissociation ionique de l'eau. Donner Ke et pKe à 25 °C. Définir le pH d'une solution. Passer du pH aux concentrations en ions H₃O⁺ et OH⁻ et inversement. Mesurer un pH à l'aide d'un pH-mètre.",
        "commentaires": "L'eau, de forte constante diélectrique, affaiblit les liaisons ioniques : le cristal s'effondre, les ions s'hydratent (H⁺ donne l'ion hydronium H₃O⁺). Distinguer nettement la concentration initiale C de la concentration effective [A]. Rappeler l'autoprotolyse de l'eau ; produit ionique [H₃O⁺]·[OH⁻] = Ke (sans unité). Ke = 10⁻¹⁴ à 25 °C (10⁻¹⁵ à 0 °C, 10⁻¹³ à 60 °C). Maîtrise de la grandeur pH et de l'échelle des pH ; mesure au pH-mètre (à défaut papier pH)."
      },
      {
        "titre": "Solutions aqueuses d'acide chlorhydrique et d'hydroxyde de sodium",
        "contenus": "Définitions selon Brönsted : caractères d'un acide fort et d'une base forte ; formules pH = −log C (acides forts) et pH = 14 + log C (bases fortes) ; réaction entre le chlorure d'hydrogène et l'eau ; dilution d'une solution d'acide ou de base.",
        "objectifs": "Définir selon Brönsted un acide et une base. Définir les caractères d'un acide fort et d'une base forte. Appliquer pH = −log C (acides forts) et pH = 14 + log C (bases fortes). Reconnaître le caractère de la réaction entre le chlorure d'hydrogène et l'eau. Calculer une concentration à partir d'un pH et inversement. Réaliser une dilution à partir d'une solution concentrée d'acide chlorhydrique ou d'une masse de soude.",
        "commentaires": "Se limiter à des solutions ni trop concentrées ni trop diluées (concentrations entre 10⁻¹ et 10⁻⁶ mol·L⁻¹) pour confondre activité et concentration et négliger les ions de l'eau. Ne pas donner une précision excessive aux concentrations issues de mesures de pH (incertitude relative ≈ 23 %). Écrire la réaction du chlorure d'hydrogène avec l'eau, admise totale ; établir la relation pH–concentration et la vérifier expérimentalement (idem pour la soude). Une dilution de 1 à 10 donne une variation de pH de 1 unité (propriété propre aux acides/bases forts)."
      },
      {
        "titre": "Couples acide-base",
        "contenus": "Constante d'acidité, pKa, coefficient d'ionisation, domaine de prédominance ; classification des couples acide-base en solution aqueuse ; nivellement par les couples de l'eau (acides et bases forts) ; couple d'un indicateur coloré.",
        "objectifs": "Expliquer le caractère limité et réversible de la réaction d'un acide (ou base) faible avec l'eau. Exprimer la constante d'acidité d'un couple acide/base. Calculer un pKa à partir du Ka. Donner les couples acide-base au programme et les deux couples de l'eau. Comparer la force des acides/bases à partir de Ka ou pKa. Recenser les espèces d'une solution ; appliquer électroneutralité et conservation de la matière. Calculer le coefficient d'ionisation. Reconnaître espèces majoritaires/minoritaires/ultraminoritaires. Déterminer les formes prédominantes. Expliquer l'équilibre d'un indicateur coloré acido-basique.",
        "commentaires": "Introduire le couple acide-base à partir du couple acide éthanoïque / ion éthanoate (réaction limitée et réversible → acide faible). Deux couples : CH₃COOH/CH₃COO⁻ et H₃O⁺/H₂O ; le couple NH₄⁺/NH₃ via NH₃ + H₂O. Établir pH = pKa + log([Base]/[Acide]) ; pKa = −log Ka ; acide d'autant plus fort que Ka grand (pKa faible). Domaines de prédominance : pH < pKa → acide prédomine ; pH > pKa → base. Privilégier le raisonnement (loi de modération de Le Chatelier). Connaître noms et formules des acides (chlorhydrique, nitrique, sulfurique, éthanoïque, méthanoïque, benzoïque…) et bases (soude, potasse, ammoniac, amines…). Un indicateur coloré a une forme acide et une forme basique de couleurs différentes."
      },
      {
        "titre": "Réaction acide-base",
        "contenus": "Courbe pH = f(v), point d'équivalence, choix de l'indicateur coloré ; dosages : acide fort–base forte, acide faible–base forte, base faible–acide fort.",
        "objectifs": "Reconnaître une réaction acide-base. Reconnaître et tracer le tracé caractéristique des courbes pH = f(v) des dosages au programme. Interpréter une courbe pH = f(v). Justifier le choix de l'indicateur coloré. Utiliser la méthode des tangentes pour déterminer le point d'équivalence. Déterminer le point de demi-équivalence.",
        "commentaires": "Équation-bilan : H₃O⁺ + OH⁻ → 2 H₂O, réaction pratiquement totale. Étudier pH = f(v) pour acide fort–base forte, acide faible–base forte, base faible–acide fort. Point d'équivalence par la méthode des tangentes. Pour acides/bases faibles : premier point d'inflexion à pH = pKa (demi-équivalence). La normalité N'EST PAS au programme. Concentrations de l'ordre de 10⁻² mol·L⁻¹. La méthode volumétrique est précise pour déterminer une concentration."
      },
      {
        "titre": "Solutions tampon",
        "contenus": "Définition, propriétés ; usage ; exemples de solutions tampon.",
        "objectifs": "Définir une solution tampon par ses propriétés. Reconnaître l'effet tampon sur une courbe de dosage acide faible–base forte. Donner au moins un exemple de solution tampon. Citer les méthodes de fabrication d'une solution tampon. Citer quelques applications de l'effet tampon.",
        "commentaires": "Introduire à partir de la courbe de dosage de l'acide éthanoïque par la soude : très faible variation du pH de part et d'autre de la demi-équivalence (solution tamponnée). Le pH d'une solution tampon reste insensible à la dilution et à un ajout modéré d'acide/base. À pH = pKa, [CH₃COOH] = [CH₃COO⁻] (mélange équimolaire acide éthanoïque – éthanoate de sodium). Le cas base faible – acide fort peut être étudié en exercice."
      }
    ]
  },
  {
    "theme": "Chimie organique",
    "volume_horaire": 14,
    "chapitres": [
      {
        "titre": "Alcools",
        "contenus": "Définition et nomenclature ; trois classes d'alcool ; méthodes de préparation (hydratation des alcènes, fermentation) ; propriétés (réaction avec le sodium, déshydratation, oxydation des alcools primaires et secondaires) ; groupe carbonyle C=O des aldéhydes et cétones, caractère réducteur des aldéhydes ; exemples de polyols (glycol, glycérol).",
        "objectifs": "Définir un alcool et donner sa formule générale. Définir les trois classes d'alcools et utiliser les règles de nomenclature. Nommer un alcool à partir de sa formule semi-développée et inversement. Définir un carbone asymétrique ; représenter les énantiomères selon Fischer. Citer les méthodes de préparation d'un alcool. Écrire la réaction du sodium sur un alcool. Citer les réactions de déshydratation. Expliquer l'oxydation ménagée et l'influence de la classe de l'alcool. Distinguer expérimentalement aldéhydes et cétones. Donner les réactions du caractère réducteur d'un aldéhyde. Nommer un aldéhyde et une cétone. Donner formule et nom du glycol et du glycérol.",
        "commentaires": "Construction de modèles moléculaires pour trouver les enchaînements (alcool, éther-oxyde, aldéhyde, cétone, acide, ester). Distinguer les trois classes d'alcool à partir de la formule de Lewis. Réaliser l'oxydation de l'éthanol par divers dispositifs ; les produits dépendent des conditions. DNPH caractérise le groupe C=O ; réactif de Schiff caractérise les aldéhydes (ne pas donner les formules ni les équations de ces réactifs). Réactions des aldéhydes avec la liqueur de Fehling et le nitrate d'argent ammoniacal (réactif de Tollens). Souligner l'importance industrielle des alcools, aldéhydes, cétones, polyols."
      },
      {
        "titre": "Acides carboxyliques",
        "contenus": "Définition, formule, exemples, nomenclature ; réactions : estérification, hydrolyse d'un ester, saponification ; passage aux fonctions dérivées (anhydride d'acide, chlorure d'acyle) pour la synthèse des esters.",
        "objectifs": "Définir un acide carboxylique et donner sa formule générale et le groupe carboxyle. Nommer un acide à partir de sa formule semi-développée et inversement. Donner la réaction d'estérification d'un monoacide par un monoalcool ; nommer un ester. Donner les caractères de l'estérification. Expliquer l'équilibre chimique dynamique ; distinguer accroissement de vitesse et déplacement d'équilibre ; reconnaître l'influence de la température et du catalyseur sur la vitesse. Donner un exemple de saponification ; définir les corps gras (triesters du glycérol). Réaliser estérification, hydrolyse, saponification. Donner les réactions de préparation des chlorures d'acyle et anhydrides d'acide ; les nommer ; expliquer leur intérêt dans la préparation des esters.",
        "commentaires": "Le groupe carboxyle est le terme ultime de l'oxydation des alcools primaires. Connaître les acides méthanoïque, éthanoïque, propanoïque, butanoïque. Les huiles animales/végétales sont des esters d'acides gras. L'estérification introduit l'équilibre chimique dynamique : même état final que l'on parte d'un mélange équimoléculaire acide-alcool ou eau-ester ; déplacement de l'équilibre par ajout/retrait (loi de modération). Influence de la température et du catalyseur sur la vitesse. Avancement suivi par dosage acide-base. Les chlorures d'acyle et anhydrides d'acide permettent une estérification rapide."
      }
    ]
  },
  {
    "theme": "Cinétique chimique",
    "volume_horaire": 6,
    "chapitres": [
      {
        "titre": "Cinétique chimique",
        "contenus": "Vitesse de formation et de disparition d'un corps ; facteurs cinétiques (influence de la concentration et de la température) ; catalyse (définition, exemples) ; mécanisme réactionnel (exemple d'une réaction photochimique).",
        "objectifs": "Citer des exemples de réactions rapides et lentes. Définir la vitesse de formation d'un produit et la vitesse de disparition d'un réactif à volume constant. Citer un exemple d'influence de la concentration et un de la température sur la vitesse. Définir un catalyseur ; donner un exemple de catalyse homogène et hétérogène. Donner un exemple de réaction en chaîne et citer ses trois étapes. Exploiter une série d'expériences (tableau, courbe). Calculer, à partir d'un graphique ou d'un tableau, la vitesse de formation et de disparition d'un corps.",
        "commentaires": "Réactions rapides (précipitation de AgCl, BaSO₄) et lentes (acide chlorhydrique sur thiosulfate de sodium). Vitesse de formation v = d[B]/dt ; vitesse de disparition v = −d[A]/dt. Ne PAS introduire le terme général de vitesse de réaction (dépend des coefficients stœchiométriques). Détermination graphique de la vitesse à une date t. Influence concentration/température essentiellement expérimentale (thiosulfate + HCl ; peroxodisulfate + iodure ; oxalate + permanganate). Catalyse homogène/hétérogène (ex. estérification catalysée par H₃O⁺ ; peroxodisulfate/iodure par Fe²⁺). Réaction en chaîne : synthèse de HCl par voie photochimique, étapes initiation/propagation/rupture."
      }
    ]
  }
]

# Récapitulatif : 3 thèmes, 8 chapitres (= 8 notions). Chimie Tle C complète.
