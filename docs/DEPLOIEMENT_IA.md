# Déploiement de fahimta ai : séquence et exploitation

Aucune de ces étapes n'est exécutée automatiquement. Toutes les variables Heroku se règlent à la main, une à la fois.

## Principe de compatibilité

Le backend ne répond 202 (tâche en file) que si `IA_TRAITEMENT_ASYNCHRONE=True`. Tant que ce réglage reste à False
(valeur par défaut), il répond comme avant : un ancien frontend ne verra JAMAIS de 202. Le réglage ne passe à True
qu'après le déploiement du frontend qui sait suivre les tâches (`lib/taches.ts`).

## Séquence

1. Déployer le backend avec les fonctions IA désactivées (`IA_LECTURE_ACTIVE`, `IA_CORRECTION_ACTIVE`,
   `IA_PROF_ACTIVE` à False, `IA_INTERRUPTEUR_GLOBAL` à False, `IA_TRAITEMENT_ASYNCHRONE` à False).
2. La phase `release` (`migrate`) applique : `budget_ia.0001`, `budget_ia.0002_operation_tache`,
   `traitement_ia.0001`, `traitement_ia.0002_table_cache` (crée la table `cache_fahimta`). Vérifier : `heroku run python manage.py showmigrations budget_ia traitement_ia`.
3. Démarrer le worker (`heroku ps:scale worker=1`, type Basic) puis contrôler `heroku logs --ps worker` : le worker
   démarre à vide, sans aucun appel IA (test automatisé : `test_le_worker_demarre_a_vide_sans_aucun_appel_ia_ni_operation`).
4. Déployer le frontend compatible.
5. Vérifier le parcours 202 puis consultation avec des API SIMULÉES (aucun appel Anthropic) sur l'application déployée.
6. Régler la limite de dépenses dans la console Anthropic (organisation ou espace de travail) : 100 000 FCFA ≈ 170 USD
   au taux de 589,25 ; fixer la limite en USD sous ce seuil. À l'atteinte, Anthropic refuse les appels (HTTP 400).
7. `IA_TRAITEMENT_ASYNCHRONE=True`.
8. Test réel autorisé : `python manage.py test_integration_ia` affiche d'abord son plafond (253,44 FCFA) ;
   les appels n'ont lieu qu'avec `--j-autorise-le-cout --telephone <compte de développement>`.
9. Activer progressivement : `IA_INTERRUPTEUR_GLOBAL=True`, lecture, puis correction, puis fahimta ai.
   Retour arrière immédiat : `IA_INTERRUPTEUR_GLOBAL=False` (coupe aussi les tâches déjà en file).

## Reprise après actualisation (lecture, correction, séance fahimta ai)

`GET /api/eleve/reprise/?programme=<id>` (élève connecté, programme de sa classe, sinon 404) renvoie en LECTURE SEULE :
l'énoncé lu (`analyse`), la dernière tâche de lecture, la dernière tâche de correction (statut, résultat ou erreur) et la
séance fahimta ai non terminée (historique autorisé, indices utilisés, `echanges_restants`, progression). Aucun appel
fournisseur, aucune facturation. Le frontend la consulte au chargement de la page de dépôt.

- Les séances vivent dans le cache partagé PostgreSQL (pas la mémoire d'un processus), durée glissante 7 200 s ; un pointeur
  « séance courante de l'élève pour ce programme » est tenu à jour à chaque action. Les quotas (3 exercices par jour, 10
  interactions) sont comptés en base (`OperationIA`), donc inchangés par une actualisation.
- `GET /api/eleve/taches/` et `/api/eleve/taches/<id>/` : uniquement les tâches de l'élève connecté (404 sinon).
- Résultats : disponibles `IA_TACHE_RESULTAT_SECONDES` = 7 200 s (2 h). Passé ce délai l'API renvoie `statut: "expiree"` SANS
  contenu, même avant la purge ; le worker efface alors le contenu (énoncé, correction, analyse) et garde une trace vide
  `IA_TACHE_TRACE_SECONDES` = 86 400 s (24 h) pour afficher « Ton résultat a expiré », puis supprime la ligne.
- Un résultat déjà présenté n'est jamais ressorti automatiquement (mémoire locale du navigateur).
- Tâche interrompue dont l'issue est inconnue : 503 `resultat_inconnu` (« Le traitement a été interrompu. Relance l'analyse. »),
  jamais de relance payante silencieuse.

## Délais, bail, tentatives, idempotence

- Plus long appel d'une tentative : correction 180 s + 4 × 20 s Wolfram = 260 s ; lecture 120 s ; professeur 150 s + Wolfram.
- Réservation périmée après 420 s ; bail de tâche 480 s (supérieur à la réservation, supérieur au plus long appel).
- 2 tentatives au plus. Une reprise qui trouve un appel payant déjà ouvert pour la même tâche (issue inconnue, ou réponse
  non conservée) ne rappelle PAS le fournisseur : la tâche se termine en 503 `resultat_inconnu`. L'opération orpheline
  reste comptée comme dépensée (statut `inconnue`). Les résultats de lecture et de correction déjà obtenus sont relus
  dans le cache partagé sans nouvel appel.
- Double soumission : la clé de requête (contrainte unique partielle) renvoie la tâche active existante ; 3 tâches actives au plus par élève.

## Ressources (Heroku)

- Connexions PostgreSQL (Essential-0 : 20) : web = `WEB_CONCURRENCY` (2) + worker = threads (4) + release/commandes ponctuelles. Mesure en test : 6 connexions pour 4 threads.
- Mémoire : pic mesuré 178 Mo pour un processus de test complet ; dyno Basic = 512 Mo. Surveiller `heroku logs` (R14).
- Coût : dyno worker Basic, environ 7 USD par mois.

## Modèle Anthropic

Défaut : `claude-sonnet-5-5` (tarifs 2 USD entrée, 10 USD sortie par million de tokens, vérifiés dans la documentation
officielle). Le SDK installé (anthropic 1.5.0) transmet l'identifiant tel quel, mais ne le liste pas dans ses types :
l'accès réel du compte Anthropic ne peut être confirmé que par le test réel (`test_integration_ia`). Si `IA_MODELE` est
défini sur Heroku, il l'emporte sur ce défaut. Les tarifs restent surchargeables par `IA_TARIFS_USD`.

## Liste blanche de comptes de développement (mode pilote)

`IA_COMPTES_AUTORISES` = téléphones d'élèves séparés par des virgules (variable Heroku, jamais journalisée).

- Vide (défaut) : comportement habituel. En production, les fonctions restent fermées tant que `IA_*_DEV_SEULEMENT=True`.
- Non vide : chaque fonction (`IA_LECTURE_ACTIVE`, `IA_CORRECTION_ACTIVE`, `IA_PROF_ACTIVE`) n'est ouverte QU'aux élèves actifs de
  la liste ; `IA_*_DEV_SEULEMENT` n'a plus d'effet (la liste le remplace). Les autres élèves voient le service comme désactivé
  (`*_disponible` à false, 503 `correction_desactivee` / `professeur_desactive`, dépôt simple sans IA) : aucune tâche, aucune
  opération, aucun appel.
- Fermé par défaut : un numéro inexistant ou mal saisi n'ouvre rien à personne d'autre.
- Double contrôle : aux portes d'entrée (vues) ET dans `budget_ia.service.ouvrir`, passage obligé de tout appel payant, y compris
  l'exécution différée par le worker (compte retiré de la liste après la mise en file : aucun appel, `ia_non_autorisee`).
- Quotas (3 exercices par jour, 10 interactions par exercice) et budget (seuil 90 000 FCFA) s'appliquent aux comptes listés.
- Rapport admin `/api/admin/budget-ia/` : `mode_pilote` et `comptes_autorises` (nombre seulement, jamais les numéros).
- Test de la chaîne complète (soumission, 202, worker, consultation, lecture, correction, fahimta ai) : définir `IA_COMPTES_AUTORISES`
  avec le seul compte de développement, `IA_TRAITEMENT_ASYNCHRONE=True` et les trois `IA_*_ACTIVE=True`, puis retirer ces réglages
  (ou vider la liste et remettre les drapeaux à False) à la fin. Retour arrière immédiat : `IA_INTERRUPTEUR_GLOBAL=False`.
- Numéros validés strictement (format `+227` suivi de 8 chiffres, comme à l'inscription) : une entrée mal formée est ignorée, jamais corrigée.
  Tant que la variable n'est pas vide, le mode pilote reste actif : une liste entièrement erronée ferme tout, elle n'ouvre rien.
  `python manage.py check` signale `budget_ia.W001` (nombre d'entrées mal formées, sans les numéros).
- Compte retiré de la liste (ou désactivé) après la mise en file : le worker clôt la tâche en 503 `ia_non_autorisee`, message élève
  « Service IA indisponible. », AVANT toute exécution : aucun appel fournisseur, aucune opération (donc aucun quota consommé), aucune tâche
  bloquée. Les opérations déjà ouvertes par une tentative précédente restent comptées (facturées ou à réconcilier).
