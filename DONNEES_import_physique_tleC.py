# DONNÉES D'IMPORT — Physique Terminale C (thèmes 2 à 5, hors Mécanique)
# Source : programme officiel nigérien (PDF second cycle, pages 309-323).
# Le Thème 1 (Mécanique) est DÉJÀ saisi à la main → NON inclus ici.
# La chimie est HORS périmètre → NON incluse.
#
# Structure : chaque thème a un titre + volume horaire, et une liste de
# chapitres. En physique, 1 chapitre = 1 notion (pas de sous-notions).
# Chaque chapitre porte : titre, contenus, objectifs, commentaires.
#
# → L'agent transforme ceci en commande Django (sur le modèle importer_tc),
#   attachée au programme Physique × Terminale C existant, en SAUTANT le
#   Thème 1 Mécanique déjà présent (ne pas recréer, ne pas dupliquer).

PHYSIQUE_TLE_C = [
  {
    "theme": "Vibration et propagation",
    "volume_horaire": 32,
    "chapitres": [
      {
        "titre": "Généralités",
        "contenus": "Phénomènes périodiques, phénomènes vibratoires ; vibrations sinusoïdales ; vecteur de Fresnel ; déphasage entre deux fonctions ; décalage horaire ; étude expérimentale des phénomènes périodiques (observation à l'oscillographe et au stroboscope).",
        "objectifs": "Définir et donner des exemples de phénomènes périodiques et vibratoires. Attribuer un caractère sinusoïdal à la vibration sonore (diapason, haut-parleur sur GBF). Donner la nature et les caractéristiques du son : source, récepteur, hauteur, fréquences audibles, ultrasons et infrasons. Utiliser un stroboscope ; interpréter une immobilité ou un ralenti apparent. Associer à une fonction sinusoïdale un vecteur de Fresnel. Définir : en phase, en opposition de phase, en quadrature avance/retard. Définir le décalage horaire. Utiliser le vecteur tournant de Fresnel pour tracer une sinusoïde. Utiliser GBF + haut-parleur pour produire un son ; microphone + oscillographe pour déterminer une fréquence. Déterminer période, fréquence, amplitude à partir d'un oscillogramme.",
        "commentaires": "Introduire la théorie du stroboscope à partir de l'immobilité ou du mouvement apparent d'un rayon peint sur un disque en rotation. Se limiter, en exercices, aux cas simples (immobilité N = k·Ne, k∈ℕ*, ou mouvement apparent pour une fréquence d'éclairs voisine de la fréquence propre). L'oscillographe s'utilise via un capteur (haut-parleur ou microphone). À une fonction sinusoïdale du temps on associe le vecteur tournant de Fresnel ; le passage fonction ↔ représentation doit être parfaitement maîtrisé."
      },
      {
        "titre": "Propagation d'un phénomène vibratoire",
        "contenus": "Propagation d'un ébranlement, célérité ; onde progressive, longueur d'onde.",
        "objectifs": "Citer des exemples d'ébranlements (signaux) transversaux et longitudinaux. Définir la propagation d'un ébranlement comme un transport d'énergie et non de matière. Définir la célérité C d'un ébranlement et donner un ordre de grandeur de la célérité du son. Citer des exemples d'ondes progressives : rectiligne, plane, circulaire, sphérique. Définir la longueur d'onde. Utiliser la relation λ = C·T. Reconnaître la direction de propagation d'une onde. Établir et exploiter l'équation de la double périodicité : y_M = y_max·cos[2π(t/T − x/λ)]. Déterminer sur un document la direction de propagation, la longueur d'onde, les lignes d'onde. Donner la méthode de mesure de la célérité du son à partir des oscillogrammes.",
        "commentaires": "Deux ordres de grandeur à retenir : célérité du son dans l'air ≈ 340 m·s⁻¹ ; célérité de la lumière dans le vide ≈ 3·10⁸ m·s⁻¹ (d'où l'année-lumière). L'onde progressive résulte de la progression d'une succession périodique de signaux émis par une source. La réflexion, la réfraction et la diffraction peuvent être observées mais NE SONT PAS au programme. Mettre en évidence λ = C·T par l'équidistance des crêtes. Expliquer l'affaiblissement du son avec la distance par dilution de l'énergie sur une sphère. Une vibration complexe se décompose en somme de sinusoïdes, d'où l'intérêt d'étudier l'onde sinusoïdale."
      },
      {
        "titre": "Superposition de deux phénomènes vibratoires",
        "contenus": "Principe de la superposition des petits mouvements ; interférence d'ondes mécaniques : à la surface d'un liquide, expérience de Melde.",
        "objectifs": "Énoncer le principe de superposition des petits mouvements. Définir le phénomène d'interférence et donner des exemples d'interférences mécaniques. Définir des sources synchrones. Utiliser la règle de Fresnel. Définir les lieux des maxima et des minima de vibration. Réaliser et interpréter des expériences d'interférences mécaniques. Réaliser l'expérience de Melde et interpréter les ondes stationnaires observées.",
        "commentaires": "Faire observer la superposition en un point de deux ébranlements se croisant : le principe de superposition suppose que la présence d'un signal ne modifie pas la propagation de l'autre. Réaliser la superposition de deux vibrations à la surface de l'eau (cuve à ondes), figure d'interférence claire en éclairage rasant. La superposition constructive/destructive s'explique sans étude analytique, à partir de la différence des distances aux sources ; utiliser aussi la construction de Fresnel."
      },
      {
        "titre": "Interférences d'ondes lumineuses",
        "contenus": "Étude expérimentale (fentes de Young) ; interprétation, aspect ondulatoire de la lumière ; interfrange ; déplacement de la frange centrale ; domaine de la lumière dans les ondes électromagnétiques.",
        "objectifs": "Donner le schéma de principe et expliquer le dispositif des fentes de Young. Définir des sources monochromatiques cohérentes. Associer la présence de franges à la nature ondulatoire de la lumière. Établir et appliquer l'expression de la différence de marche. Établir et appliquer l'expression de l'interfrange. Donner l'ordre de grandeur des longueurs d'onde des radiations visibles et situer UV et IR par rapport au visible. Citer des exemples d'ondes électromagnétiques. Réaliser une expérience d'interférences avec une source laser. Mesurer l'interfrange. Calculer le déplacement de la frange centrale.",
        "commentaires": "Objectif : justifier la nature ondulatoire de la lumière par les franges d'interférence de deux sources cohérentes, non l'étude d'un dispositif particulier. Utiliser un laser comme source monochromatique dans le dispositif de Young (tout autre dispositif est hors programme). Insister sur interférences constructives/destructives (lumière + lumière = obscurité). Le déplacement de la frange centrale se fait par déplacement de la source et interposition d'une lame à faces parallèles (épaisseur e, indice n). La superposition de franges de diverses couleurs et le spectre cannelé en lumière blanche NE SONT PAS au programme."
      }
    ]
  },
  {
    "theme": "Electromagnétisme",
    "volume_horaire": 22,
    "chapitres": [
      {
        "titre": "Champ magnétique",
        "contenus": "Champ magnétique créé par un courant ; champ magnétique de quelques circuits (fil, solénoïde).",
        "objectifs": "Décrire le champ magnétique créé par un courant. Donner les caractéristiques du vecteur champ magnétique. Déterminer le champ magnétique créé par un solénoïde. Utiliser les règles d'orientation (règle de la main droite, du bonhomme d'Ampère…).",
        "commentaires": "Un courant circulant dans un fil produit un champ magnétique. L'analogie solénoïde–aimant sera exploitée."
      },
      {
        "titre": "Force de Lorentz",
        "contenus": "Force magnétique sur une particule chargée en mouvement ; mouvement d'une particule chargée dans un champ magnétique uniforme.",
        "objectifs": "Donner l'expression de la force de Lorentz F = q·v∧B. Déterminer le mouvement d'une particule chargée dans un champ magnétique uniforme. Montrer que la puissance de la force magnétique est nulle.",
        "commentaires": "La force électromagnétique s'exerce sur une particule chargée (électron ou ion) en mouvement. La puissance F·v de la force magnétique est nulle ; en l'absence d'autre force, le mouvement est uniforme. Expériences avec bobines de Helmholtz ; on ne considérera que les cas simples."
      },
      {
        "titre": "Force de Laplace",
        "contenus": "Force exercée sur un conducteur parcouru par un courant placé dans un champ magnétique ; applications.",
        "objectifs": "Donner l'expression de la force de Laplace. Déterminer ses caractéristiques (direction, sens, intensité). Décrire des applications : rails de Laplace, balance de Cotton, roue de Barlow, moteur électrique, haut-parleur.",
        "commentaires": "Applications : rails de Laplace, balance de Cotton, roue de Barlow, principe du moteur électrique, principe du haut-parleur. L'étude des appareils magnétoélectriques n'est PAS au programme."
      },
      {
        "titre": "Induction électromagnétique",
        "contenus": "Flux magnétique ; force électromotrice d'induction ; loi de Faraday, loi de Lenz.",
        "objectifs": "Définir le flux magnétique à travers un circuit. Énoncer la loi de Lenz. Exprimer la force électromotrice d'induction (loi de Faraday). Appliquer à des situations simples.",
        "commentaires": "La variation de flux à travers un circuit engendre une force électromotrice d'induction. La formule de Faraday s'exprime par e = −dΦ/dt. La notion de champ électromoteur n'est PAS au programme."
      },
      {
        "titre": "Auto-induction",
        "contenus": "Phénomène d'auto-induction ; inductance d'une bobine ; force électromotrice d'auto-induction ; énergie magnétique.",
        "objectifs": "Définir le phénomène d'auto-induction. Exprimer la force électromotrice d'auto-induction. Définir l'inductance L d'une bobine. Exprimer l'énergie magnétique emmagasinée dans une bobine.",
        "commentaires": "La puissance reçue conduit à identifier ½·L·i² comme l'énergie magnétique emmagasinée dans la bobine. La détermination graphique de l'inductance est HORS programme."
      }
    ]
  },
  {
    "theme": "Oscillations électriques",
    "volume_horaire": 16,
    "chapitres": [
      {
        "titre": "Circuit oscillant",
        "contenus": "Oscillations libres (circuit LC) ; observation d'oscillations amorties (régimes pseudo-périodique, apériodique, critique).",
        "objectifs": "Réaliser un circuit oscillant et l'étudier à l'oscillographe. Représenter l'allure de la décharge d'un condensateur en régime pseudo-périodique, apériodique et critique. Établir l'équation différentielle d'un circuit LC et en donner la solution. Donner l'expression de la fréquence propre du circuit LC. Exprimer la conservation de l'énergie et la vérifier.",
        "commentaires": "L'équation L·q″ + q/C = 0 s'établit en identifiant les tensions aux bornes du condensateur et de la bobine. Solution sinusoïdale q = Qm·cos(ω₀t + φ) avec ω₀ = 1/√(LC). Échange alternatif entre énergie électrostatique ½·q²/C et énergie magnétique ½·L·i² ; noter l'analogie avec un oscillateur mécanique."
      },
      {
        "titre": "Circuit en régime sinusoïdal forcé",
        "contenus": "Circuit RLC série en régime sinusoïdal forcé ; impédance ; résonance d'intensité ; surtension.",
        "objectifs": "Établir l'expression de l'impédance d'un circuit RLC série. Déterminer le déphasage entre tension et intensité (construction de Fresnel). Tracer et interpréter une courbe de résonance. Définir la résonance d'intensité et la bande passante. Décrire le phénomène de surtension.",
        "commentaires": "Utiliser la construction de Fresnel pour le circuit RLC série. Tracer et interpréter la courbe de résonance. Le phénomène de surtension à la résonance dans un élément sera signalé."
      }
    ]
  },
  {
    "theme": "Phénomènes corpusculaires",
    "volume_horaire": 18,
    "chapitres": [
      {
        "titre": "Effet photoélectrique",
        "contenus": "Émission d'électrons, seuil d'émission ; interprétation par le photon (Einstein) ; cellule photoélectrique.",
        "objectifs": "Définir l'effet photoélectrique. Exprimer l'énergie cinétique des électrons émis. Expliquer l'effet photoélectrique par l'interaction photon-électron. Définir le travail d'extraction et la fréquence seuil.",
        "commentaires": "Introduire l'effet photoélectrique par l'expérience de Hertz : la lumière peut arracher des électrons à un métal. L'hypothèse du photon (Einstein), particule d'énergie h·ν, explique l'effet. L'électron n'est émis que si l'énergie du photon dépasse le travail d'extraction W₀ ; l'énergie excédentaire devient énergie cinétique de l'électron."
      },
      {
        "titre": "Noyau atomique",
        "contenus": "Constitution du noyau ; isotopes ; défaut de masse ; énergie de liaison.",
        "objectifs": "Décrire la constitution d'un noyau (nucléons : protons, neutrons). Définir les isotopes. Calculer le défaut de masse d'un noyau. Calculer l'énergie de liaison et l'énergie de liaison par nucléon.",
        "commentaires": "Utiliser l'équivalence masse-énergie E = m·c². L'énergie de liaison par nucléon caractérise la stabilité du noyau (courbe d'Aston)."
      },
      {
        "titre": "Réactions nucléaires",
        "contenus": "Radioactivité (α, β⁻, β⁺, γ) ; lois de conservation (Soddy) ; loi de décroissance radioactive ; réactions nucléaires provoquées : fission, fusion.",
        "objectifs": "Écrire une équation de désintégration en appliquant les lois de conservation (Soddy). Distinguer les radioactivités α, β⁻, β⁺, γ. Établir et exploiter la loi de décroissance radioactive N = N₀·e^(−λt). Définir la constante radioactive, la demi-vie (période) et l'activité. Distinguer fission et fusion.",
        "commentaires": "À la radioactivité β⁻ on associe l'émission d'un électron ; à β⁺ celle d'un positron ; le rayonnement γ correspond au passage d'un état excité du noyau à un état moins excité. Réactions provoquées : fission (noyau lourd) et fusion (noyaux légers). Applications énergétiques mentionnées."
      }
    ]
  }
]

# Récapitulatif : 4 thèmes, 14 chapitres (= 14 notions), hors Mécanique et hors Chimie.
