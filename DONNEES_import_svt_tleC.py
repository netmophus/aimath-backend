# DONNÉES D'IMPORT — SVT (Sciences de la Vie et de la Terre) Terminale C
# Source : programme officiel nigérien (PDF second cycle, pages 401-406).
# En SVT : 1 chapitre = 1 notion (comme physique/chimie).
# → L'agent transforme ceci en commande Django (modèle importer_physique_tc /
#   importer_chimie_tc), attachée au programme SVT × Terminale × C.
#
# ATTENTION : le programme SVT × Tle C doit exister en base (matière "SVT" ou
# "Sciences de la Vie et de la Terre"). S'il n'existe pas, la commande le
# signale, ne l'invente pas.
#
# Le programme SVT Tle C a 5 thèmes : 2 en Sciences de la Terre, 3 en Sciences
# de la Vie. On garde l'ordre du programme (thèmes numérotés 1 à 5).

SVT_TLE_C = [
  {
    "theme": "Les processus géologiques à l'origine de l'accumulation des ressources géologiques",
    "volume_horaire": 10,
    "chapitres": [
      {
        "titre": "Altération et sédimentation",
        "contenus": "Les mécanismes d'altération des roches ; le transport des sédiments ; la diagenèse.",
        "objectifs": "Expliquer les processus de décomposition chimique et de désagrégation mécanique des roches. Expliquer l'origine possible d'un sable en comparant un granite sain et une arène granitique. Déterminer l'action des agents de transport. Expliquer les processus de sédimentation et de diagenèse. Expliquer la formation des évaporites.",
        "commentaires": "Observation des différents stades d'altération du granite. L'altération s'effectue sur les roches préexistantes (magmatiques, métamorphiques, sédimentaires) qui se désagrègent en sédiments sous l'effet de processus physiques (vent, eau, gel-dégel), chimiques (dissolution par les eaux) et biologiques (lichens). Les produits d'altération renseignent sur l'origine/la nature des éléments d'un sédiment. L'étude des évaporites se limite au sel de cuisine et au gypse."
      },
      {
        "titre": "Métamorphisme",
        "contenus": "Les types de métamorphisme ; les facteurs ou conditions de métamorphisme.",
        "objectifs": "Définir le métamorphisme. Distinguer métamorphisme de contact et métamorphisme général. Expliquer la notion de série métamorphique. Expliquer la diversité des roches métamorphiques en s'appuyant sur les conditions/facteurs du métamorphisme et la nature chimique des roches.",
        "commentaires": "Le métamorphisme est l'ensemble des transformations minéralogiques et structurales d'une roche sous l'action de la température et/ou de la pression. Types : métamorphisme de contact, régional (général), d'impact (choc), hydrothermal. Les séries métamorphiques correspondent à la succession de roches le long d'un gradient pression–température ; trois gradients principaux : haute P–basse T, moyenne P–moyenne T, basse P–haute T."
      },
      {
        "titre": "Magmatisme (volcanisme et plutonisme)",
        "contenus": "Roches de la famille du granite (granite et rhyolite) ; roches de la famille du basalte (basalte et gabbro) ; l'origine des magmas granitiques (plutoniques) et effusifs.",
        "objectifs": "Distinguer volcanisme et plutonisme. Expliquer la diversité des roches magmatiques du point de vue chimique et structural. Expliquer l'origine des magmas.",
        "commentaires": "Le magmatisme est l'ensemble des phénomènes de fusion puis cristallisation/solidification des constituants des roches. Volcanisme (magma solidifié en surface) et plutonisme (magma cristallisé en profondeur). Classement par composition chimique : famille du granite (roches acides) et famille du basalte (roches basiques). La structure distingue les roches d'une même famille : structure microlitique (volcanisme), structure grenue (plutonisme)."
      }
    ]
  },
  {
    "theme": "Quelques ressources géologiques exploitées au Niger",
    "volume_horaire": 12,
    "chapitres": [
      {
        "titre": "Les gisements métallifères et les processus associés",
        "contenus": "Gisements dus à la cristallisation fractionnée des magmas (nickel, cobalt, platine) ; gisements liés au métamorphisme de contact (fer, magnésium, cuivre) ; gisements filoniens (or) ; accumulation due à l'altération (bauxite, nickel) ; accumulation due à la sédimentation (or et platine par sédimentation détritique ; fer et phosphate par sédimentation chimique).",
        "objectifs": "Décrire les processus de solidification et de cristallisation d'un magma. Reconnaître les indices de présence des ressources géologiques. Énumérer les différents types de gisements. Localiser les gisements de minerais sur une carte du Niger. Expliquer les processus d'accumulation et de formation des ressources géologiques dans les différents types de roches.",
        "commentaires": "Ressource géologique : substances prélevées dans le sous-sol à des fins utilitaires ; les lieux d'accumulation constituent des gisements (roches sédimentaires, métamorphiques ou magmatiques). Chaque type de gisement est associé à des roches et structures propres. Deux types de gisements d'or au Niger : primaires (filons de quartz hydrothermaux) et secondaires (alluvions). Un filon est une accumulation de minéraux dans une fissure de roche. Un minerai : accumulation de minéraux métallifères exploitables. Les plus importants gisements d'or, de chrome et l'essentiel des réserves d'uranium sont dans des terrains âgés de 1000 à 1500 Ma."
      },
      {
        "titre": "Le pétrole",
        "contenus": "Étapes de la prospection et conditions de formation du pétrole ; étapes de la formation du pétrole.",
        "objectifs": "Expliquer les étapes et conditions de la formation du pétrole. Énumérer les étapes de la recherche et de l'exploitation pétrolière. Énumérer les avantages et inconvénients de l'utilisation du pétrole. Définir : énergies renouvelables ; énergies non renouvelables.",
        "commentaires": "La formation du pétrole nécessite une quantité suffisante de matières organiques (animales et végétales) déposées en général dans les mers (le pétrole lacustre est rare). L'exploration comprend : observation de la surface (géologie pétrolière), étude des profondeurs (géophysique), vérification par forage d'exploration. Étapes de formation : dépôt et enfouissement de matières organiques dans un bassin sédimentaire ; maturation (66,5 à 150 °C, sur des millions d'années) ; migration vers une roche-magasin poreuse sous l'effet de la pression. Les énergies non renouvelables ont un temps de formation très long et une quantité limitée."
      }
    ]
  },
  {
    "theme": "Le fonctionnement des appareils génitaux et leur régulation",
    "volume_horaire": 16,
    "chapitres": [
      {
        "titre": "Les appareils génitaux et leur fonctionnement",
        "contenus": "Organisation des appareils génitaux ; gonades (organisation, structure, fonctions) ; gamétogenèse (spermatogenèse et ovogenèse) ; production d'hormones sexuelles.",
        "objectifs": "Décrire l'organisation des appareils génitaux de l'homme et de la femme. Annoter les schémas des appareils génitaux. Décrire les étapes de la formation des gamètes masculin et féminin. Déterminer les caractéristiques de l'activité testiculaire. Préciser les effets biologiques des hormones sexuelles sur le fonctionnement des appareils génitaux.",
        "commentaires": "Activités : dissection de l'appareil génital de la souris ; observations microscopiques de coupes d'ovaires/utérus et de spermatozoïdes ; analyses d'expériences sur le rôle endocrine des ovaires et le contrôle hypothalamo-hypophysaire. La gamétogenèse réinvestit les notions sur la méiose. Chez l'homme, production continue des gamètes de la puberté à la fin de la vie, sous contrôle du complexe hypothalamo-hypophysaire. Chez la femme, de la puberté à la ménopause, la physiologie sexuelle s'inscrit dans un cycle menstruel."
      },
      {
        "titre": "Régulation du fonctionnement des organes génitaux",
        "contenus": "Les cycles sexuels chez la femme et leur régulation (cycle ovarien, cycle utérin, cycle de la glaire cervicale) ; l'activité testiculaire et son contrôle hormonal.",
        "objectifs": "Expliquer la régulation de l'activité testiculaire et de l'activité ovarienne. Déterminer les caractéristiques des cycles ovarien et utérin. Expliquer la synchronisation des cycles ovarien et utérin. Expliquer les modifications de la glaire au cours du cycle sexuel. Expliquer la sécrétion cyclique des hormones hypophysaires. Expliquer le mécanisme de rétrocontrôle. Expliquer le déterminisme des cycles sexuels.",
        "commentaires": "L'activité ovarienne est sous le contrôle du complexe hypothalamo-hypophysaire, lui-même contrôlé par l'ovaire (rétrocontrôle des hormones ovariennes) et des stimuli internes/externes. L'ovaire contrôle le cycle utérin, synchronisant ovulation et réceptivité utérine. L'augmentation préovulatoire des œstrogènes exerce un rétrocontrôle positif sur l'axe hypothalamo-hypophysaire, assurant le synchronisme entre maturation folliculaire et commande de l'ovulation."
      },
      {
        "titre": "De la fécondation à la nidation",
        "contenus": "La fécondation (définition, localisation, étapes, effets sur le cycle sexuel) ; l'œuf (définition, devenir) ; migration et premières divisions cellulaires ; nidation.",
        "objectifs": "Décrire les étapes de la fécondation. Expliquer les conséquences de la fécondation sur le cycle sexuel. Expliquer le maintien de la sécrétion de progestérone au début de la grossesse. Définir la fécondation. Localiser le lieu de la fécondation. Décrire le devenir de l'œuf.",
        "commentaires": "Activités : étude de la fécondation à l'appui de films, exploitation de documents. La rencontre des gamètes dépend en partie de la qualité de la glaire cervicale. La fécondation a lieu dans le tiers supérieur des trompes, possible seulement brièvement après l'ovulation. Après fécondation et nidation, la sécrétion d'HCG par le jeune embryon maintient l'activité du corps jaune (donc la progestérone), indispensable au maintien de la muqueuse utérine en début de grossesse."
      }
    ]
  },
  {
    "theme": "La régulation des naissances",
    "volume_horaire": 4,
    "chapitres": [
      {
        "titre": "La régulation des naissances",
        "contenus": "Les méthodes contraceptives (naturelles, mécaniques, chimiques) ; principales causes de stérilité (stérilité chez la femme, infertilité masculine).",
        "objectifs": "Expliquer en quoi la connaissance des mécanismes hormonaux de la reproduction a permis la mise au point des méthodes de régulation des naissances. Expliquer le mode d'action des pilules. Énumérer les autres méthodes de planification des naissances. Expliquer la fiabilité des différentes méthodes contraceptives. Citer quelques causes de stérilité. Distinguer les différents types de stérilité chez l'homme et la femme et leurs causes.",
        "commentaires": "La contraception hormonale féminine s'appuie sur le déterminisme hormonal de la physiologie sexuelle. La contraception hormonale masculine est encore à l'état de recherche. Le couple peut utiliser d'autres moyens contraceptifs (empêcher la rencontre des gamètes ou l'implantation). Les causes d'infertilité touchent homme et femme ; les dosages hormonaux renseignent sur l'activité des gonades et du complexe hypothalamo-hypophysaire. Stérilités chez la femme : hormonales, mécaniques, troubles de réceptivité. Infertilité masculine : anomalies du nombre, de la forme et de la mobilité des spermatozoïdes."
      }
    ]
  },
  {
    "theme": "La communication par voie humorale",
    "volume_horaire": 8,
    "chapitres": [
      {
        "titre": "La régulation de la glycémie",
        "contenus": "La constante glycémique (hypoglycémie, hyperglycémie) ; les organes de stockage du glucose (muscles, tissu adipeux, foie) ; rôle particulier du foie ; la régulation de la glycémie (système hypoglycémiant, système hyperglycémiant, autorégulation) ; le dysfonctionnement (les deux types de diabète).",
        "objectifs": "Définir : glycémie, glycogénogenèse, glycogénolyse, néoglucogenèse. Déterminer les rôles du foie et du pancréas dans la régulation de la glycémie. Annoter le schéma d'une coupe transversale du pancréas. Définir la notion d'hormone et de constante glycémique. Expliquer les différents mécanismes de régulation de la glycémie. Déterminer les troubles liés à l'hyperglycémie et à l'hypoglycémie. Expliquer le mode d'action des hormones du pancréas. Caractériser et expliquer l'origine des deux formes de diabète. Déterminer les causes du dysfonctionnement du système de régulation.",
        "commentaires": "Traiter un exemple de communication humorale : la régulation de la glycémie, exemple de mécanisme d'homéostasie. La glycémie est relativement constante, ≈ 1 g/L (ou 5,5 mmol/L). Foie, pancréas, muscles et tissu adipeux interviennent dans la régulation. Le diabète sucré peut être dû à une insuffisance de production d'insuline (insulinodépendant) ou à une insuffisance de récepteurs (insulinorésistant) ; seul le premier cas se traite par injection d'insuline."
      }
    ]
  }
]

# Récapitulatif : 5 thèmes, 8 chapitres (= 8 notions). SVT Tle C complète
# (2 thèmes Sciences de la Terre + 3 thèmes Sciences de la Vie).
