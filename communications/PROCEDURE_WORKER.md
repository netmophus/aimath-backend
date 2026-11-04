# Worker Communications : procédure à la demande

Le worker Communications envoie les SMS des campagnes confirmées. Il est **séparé** du worker fahimta ai
(`worker: traiter_taches_ia`) et **n'est pas permanent**. Il est **le seul** point d'envoi des campagnes :
ni le web, ni un hook, ni un signal, ni le worker IA, ni la phase release ne les envoient (vérifié par des tests).

## Garanties
- **Rien ne part sans worker.** `COMMUNICATIONS_SMS_ACTIVES=true` seul n'envoie rien : cette variable autorise le
  worker à envoyer, elle ne lance aucun processus. Aucun autre processus ne peut envoyer.
- **Redémarrage des dynos.** Redémarrer (ou re-déployer) web ou le worker IA ne lance pas le worker Communications. Dans le
  `Procfile`, `communications:` est un type de process à part : un type ajouté démarre à **0 dyno**, le dépôt ne contient
  ni `app.json` ni `heroku.yml` imposant un nombre de dynos, et seul un `heroku ps:scale communications=N` explicite le
  démarre. À vérifier après déploiement : `heroku ps -a fahimtanabackend` ne doit lister que `web` et `worker`.
- **Un seul message en vol.** Le worker réserve un message à la fois : une coupure brutale n'affecte qu'un message.
- **Jamais de renvoi automatique d'un message incertain.** Ni le worker, ni « Relancer les échecs » (qui ne reprend que
  les `echec`). Deux workers simultanés ne se doublent pas (verrou par message).

## Ce que voit l'administrateur sans worker
- Après « Confirmer et envoyer », la campagne est **En attente** : confirmée, mais **aucun message n'est parti**.
- `/admin/communications` affiche un bandeau « N message(s) confirmé(s) attendent d'être traités ».
- Les messages restent `en_attente` sans limite de durée : ni perte, ni envoi spontané, ni doublon.
- États d'une campagne : **En attente** (aucun message traité) → **En cours** → **Terminée** (plus rien à traiter).
  « Terminée » ne veut pas dire « tout envoyé » : lire le détail (acceptés, échecs, incertains).
- « Accepté » = pris en charge par le fournisseur. Aucun accusé de livraison n'est exploité : jamais de « Livré ».

## Contrôles avant CHAQUE envoi (`services.garde_envoi`)
Le worker réévalue, avant chaque message, dans cet ordre :
1. `COMMUNICATIONS_SMS_ACTIVES` est vrai (sinon `envois_desactives`) ;
2. `COMMUNICATIONS_FOURNISSEUR` est un fournisseur connu : `simule` ou `lam` (sinon `fournisseur_inconnu`). Il n'y a
   **jamais** de repli silencieux sur le simulé : une faute de frappe n'« accepte » donc rien à tort ;
3. un plafond mensuel est défini (`plafond_absent`) et un tarif de segment est renseigné (`tarif_absent`) ;
4. la dépense du mois (messages en attente, en cours, acceptés, incertains) ne dépasse pas le plafond (`plafond_depasse`).

Au premier blocage, le worker **s'arrête sans rien perdre** : les messages restent `en_attente`. Un plafond baissé
pendant un traitement arrête donc le worker au message suivant. Aussi : compte suspendu, consentement retiré ou
opposition entre la confirmation et l'envoi → ce message devient `ignore` (jamais envoyé).
`COMMUNICATIONS_FOURNISSEUR=simule` en production « accepte » sans rien envoyer : l'écran Communications affiche le
fournisseur actif, à contrôler avant de lancer un traitement.

## Commande `traiter_communications`
| Option | Comportement |
|---|---|
| `--etat` | Lecture seule : affiche la file (en attente, en cours d'envoi, incertains) et si l'envoi est possible (ou le motif de blocage). N'envoie rien. |
| `--jusqu-a-vide` | Traite tout ce qui est en attente puis s'arrête (voir ci-dessous). |
| `--une-fois` | Un seul passage (au plus `COMMUNICATIONS_LOT` messages), sans erreur si bloqué. Essais manuels. |
| (aucune) | Boucle permanente (process `communications`) : attend les nouveaux messages. |

### `--jusqu-a-vide` en détail
- **Campagnes confirmées en attente** : le worker traite, dans l'ordre des messages, les messages `en_attente` des campagnes
  confirmées (`en_cours`). Une campagne seulement en aperçu, arrêtée ou terminée n'est jamais traitée. Débit :
  `COMMUNICATIONS_DEBIT_PAR_MINUTE` (60 par défaut : 600 messages ≈ 10 minutes). Les campagnes passent à **Terminée**
  quand plus aucun de leurs messages n'est en attente ou en cours.
- **Fin normale (code 0)** : la file est vide. La commande affiche `N message(s) traité(s) (terminé). Restent en attente : 0 ; incertains : X.`
  File vide et envois désactivés : sortie 0 avec « Rien n'est traité ».
- **Blocage (code 1, `CommandError`)** : des messages attendent mais `garde_envoi` refuse (envois désactivés, fournisseur
  inconnu, plafond/tarif absent, plafond dépassé), au démarrage ou en cours de route. Les messages restent `en_attente` ;
  corriger la cause puis relancer. Le code 1 apparaît dans `heroku logs` (« Process exited with status 1 »).
- **Messages réservés par un autre processus** : si des messages sont en attente mais verrouillés par un autre worker, la
  commande patiente (12 essais de 5 s) puis sort avec le code 1 sans rien doubler.
- **Erreurs d'envoi** :
  - refus du fournisseur, ou envoi impossible (configuration LAM incomplète, fournisseur injoignable avant l'envoi) → message `echec`, relançable par « Relancer les échecs » ;
  - numéro devenu invalide, compte suspendu, consentement retiré → message `ignore` (non envoyé) ;
  - exception inattendue ou délai dépassé après envoi → message **`incertain`** : on ignore s'il est parti.
  La commande continue avec les messages suivants, et le bilan final signale « dont N nouveau(x) : à vérifier à la main ».
- **Messages incertains** : jamais renvoyés. Un message resté « en cours d'envoi » plus de
  `COMMUNICATIONS_TIMEOUT_REPRISE_MIN` minutes (worker coupé en plein vol) passe en `incertain` (code `interrompu`) au
  démarrage suivant. Vérifier auprès de LAM ou du destinataire ; ne jamais le remettre à la main en `en_attente`.
- **Arrêt** : SIGTERM, `heroku ps:stop` ou Ctrl+C → le message en cours est terminé, la commande sort proprement
  (« arrêt demandé, sortie propre ») et le reste demeure `en_attente`.

## Prérequis (une seule fois, avec autorisation)
```
heroku config:set COMMUNICATIONS_SMS_ACTIVES=true COMMUNICATIONS_FOURNISSEUR=lam -a fahimtanabackend
```
`SMS_MOCK` doit rester faux pour de vrais SMS. Renseigner dans `/admin/communications` : tarif d'un segment,
plafond mensuel, lien du groupe WhatsApp. Chaque changement de variable Heroku redémarre les dynos web et IA (sans lancer le
worker Communications).

## Méthode recommandée : dyno ponctuel qui s'arrête seul
```
# 1. Voir la file et si l'envoi est possible (lecture seule, rien n'est envoyé)
heroku run python manage.py traiter_communications --etat -a fahimtanabackend

# 2. Traiter toute la file puis sortir (dyno ponctuel, facturé à la durée d'exécution)
heroku run:detached python manage.py traiter_communications --jusqu-a-vide -a fahimtanabackend

# 3. Suivre
heroku logs --tail -a fahimtanabackend --dyno run

# 4. Vérifier : bandeau d'attente disparu, campagne « Terminée », ou de nouveau --etat
```

## Méthode alternative : dyno permanent le temps du traitement
```
heroku ps:scale communications=1 -a fahimtanabackend
# ... attendre « Terminée » dans l'écran Communications ...
heroku ps:scale communications=0 -a fahimtanabackend
```
