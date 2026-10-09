# Gadgetbridge → serveur → Open Wearables, automatiquement

Le téléphone exporte périodiquement une **copie SQLite** avec la fonction native de Gadgetbridge. Syncthing transfère ce fichier directement au serveur. Un service Docker surveille le fichier reçu, le convertit et soumet les lots à l'API locale, avec confirmation du worker et reprise persistante. Aucun export manuel, tâche cron, root Android ou accès à la base interne de l'application n'est nécessaire après configuration.

L'importeur accepte également un autre outil de transfert : il attend seulement un fichier `/srv/gadgetbridge/incoming/Gadgetbridge.db`. L'option documentée ici est Syncthing, avec téléphone en **envoi seulement** et serveur en **réception seulement**. Ce flux complète Endurain et Home Assistant.

## 1. Mettre à jour les images

Le serveur doit utiliser une version contenant `scripts/gadgetbridge_watch.py`. Sur Ubuntu, depuis votre checkout :

```bash
cd /opt/stacks/open-wearables
sudo git fetch origin
sudo git switch feat/gadgetbridge-native
sudo git pull --ff-only origin feat/gadgetbridge-native
release=$(git rev-parse --short=8 HEAD)
sudo docker build --build-arg PYTHON_IMAGE=python:3.14.7-slim \
  --build-arg UV_IMAGE=ghcr.io/astral-sh/uv:0.12.19 \
  --build-arg GIT_SHA="$(git rev-parse HEAD)" \
  -t "local/open-wearables-backend:$release" backend
sudo docker build --build-arg BUN_IMAGE=oven/bun:1.4.0-alpine \
  -t "local/open-wearables-frontend:$release" frontend
printf 'OW_IMAGE_TAG=%s\n' "$release"
```

Conserver vos secrets et paramètres HTTPS/Nginx Proxy Manager. Effectuer une sauvegarde avant la mise à jour, selon [README.md](README.md). Dans Portainer, modifier `OW_IMAGE_TAG` avec la valeur affichée, puis redéployer la pile existante sans imposer de pull des images locales. Le changement d'images ne supprime pas les bind mounts existants.

## 2. Préparer les dossiers sur serv-kaell

Identifier l'UID/GID de votre utilisateur Linux (exemple `kl`) et vérifier les ports proposés :

```bash
id -u kl
id -g kl
sudo ss -ltn
sudo docker ps --format '{{.Names}} {{.Ports}}'
```

Les exemples utilisent UID/GID 1000. Adapter si les commandes renvoient d'autres nombres :

```bash
sudo install -d -m 700 -o 1000 -g 1000 /srv/gadgetbridge/incoming
sudo install -d -m 700 -o 1000 -g 1000 /srv/gadgetbridge/importer
sudo install -d -m 700 -o 1000 -g 1000 /srv/gadgetbridge/syncthing
```

`incoming` contient l'export reçu. `importer` conserve les checkpoints, états de reprise et rapports. `syncthing` conserve l'identité et la configuration du serveur Syncthing. Sauvegarder ces dossiers en privé, notamment `importer` : une reprise dépend de ses fichiers. L'importeur ne modifie jamais le fichier reçu.

## 3. Installer Syncthing dans Portainer

Créer une **nouvelle** stack `gadgetbridge-transfer`, puis coller le contenu de [compose.syncthing.yml](compose.syncthing.yml). C'est une pile Docker Standalone ; ne pas la fusionner avec Endurain ou Home Assistant.

Variables possibles dans Portainer :

```dotenv
GADGETBRIDGE_UID=1000
GADGETBRIDGE_GID=1000
SYNCTHING_BIND_ADDRESS=192.168.0.2
SYNCTHING_GUI_PORT=18384
SYNCTHING_SYNC_PORT=22000
```

Adapter les UID/GID et ports si nécessaire. Ouvrir `http://192.168.0.2:18384` et configurer immédiatement un utilisateur/mot de passe pour l'interface Syncthing (**Actions → Paramètres → Interface graphique**). Utiliser un tunnel SSH ou Nginx Proxy Manager avec HTTPS pour administrer cette interface si souhaité. Le port 22000 transporte les fichiers chiffrés entre appareils ; il ne fournit pas une interface web.

Dans Syncthing serveur, **Paramètres → Connexions**, désactiver la découverte globale, les relais et la traversée NAT pour ce flux LAN. L'adressage explicite du serveur ci-dessous dispense de découverte Internet. Supprimer le partage du dossier par défaut si vous ne l'utilisez pas.

## 4. Configurer le Samsung

Installer **Syncthing-Fork** depuis sa source officielle : [dépôt maintenu](https://github.com/researchxxl/syncthing-android) ou sa fiche F-Droid `com.github.catfriend1.syncthingandroid`. La version vérifiée lors de la rédaction est `v2.1.6.0`. Le serveur utilise l'image officielle `syncthing/syncthing:2.1.6`.

Créer un dossier partagé accessible aux deux applications, par exemple :

```text
Documents/GadgetbridgeExport
```

Dans Gadgetbridge, ouvrir **Paramètres → Automatisations → Exporter automatiquement la base de données** (dans certaines versions, ce réglage est directement dans les paramètres) :

1. Activer l'export automatique de la **base de données**, pas ZIP, FIT ou GPX.
2. Choisir l'emplacement `Documents/GadgetbridgeExport/Gadgetbridge.db`. Gadgetbridge utilise le sélecteur Android pour autoriser l'écriture de ce fichier.
3. Choisir un intervalle de **1 heure** pour commencer, puis l'heure de départ souhaitée.
4. Synchroniser le bracelet et utiliser le bouton de test **Exécuter maintenant / Tester l'export**.
5. Vérifier qu'un fichier SQLite est créé et que la dernière exécution est indiquée comme réussie.

Gadgetbridge planifie l'export avec Android WorkManager : l'intervalle n'est pas une garantie à la minute près. Il exporte les données déjà présentes dans Gadgetbridge ; le bracelet doit être synchronisé pour transmettre de nouvelles mesures.

Dans Syncthing-Fork :

1. Ajouter votre serveur avec son **Device ID**, affiché dans Syncthing serveur via **Actions → Afficher l'identifiant**.
2. Pour l'adresse du serveur, utiliser `tcp://192.168.0.2:22000` (adapter si le port a changé).
3. Accepter le téléphone côté serveur.
4. Ajouter le dossier `Documents/GadgetbridgeExport`, partagé avec le serveur, avec le type **Envoi seulement / Send Only**.
5. Côté serveur, accepter le dossier proposé, choisir le chemin **`/incoming`** et le type **Réception seulement / Receive Only**. `/incoming` est le chemin dans le conteneur ; il correspond à `/srv/gadgetbridge/incoming` sur Ubuntu.
6. Désactiver également relais/découverte globale/NAT sur Android, et autoriser Syncthing à fonctionner sur votre Wi-Fi domestique.

Pour Gadgetbridge et Syncthing-Fork, configurer l'utilisation de batterie **Non restreinte** et les retirer des applications en veille profonde de Samsung. Accorder l'accès au dossier exporté à Syncthing. Laisser les notifications de service actives si l'application les demande. Le téléphone transfère les fichiers lorsqu'il peut joindre le serveur sur le LAN ; hors de ce réseau, le prochain export disponible sera transmis au retour.

Ne pas utiliser l'emplacement privé `Android/data/...` ou une copie de la base vivante de Gadgetbridge. Le dossier partagé doit contenir un **export autonome**, sans dépendance à un fichier `-wal`. Les fichiers temporaires `.syncthing...tmp` sont ignorés par l'importeur.

## 5. Ajouter l'importeur à votre stack Open Wearables

Dans Portainer, ouvrir la stack Open Wearables existante. Ajouter le service `gadgetbridge-importer` du fichier [compose.automation.yml](compose.automation.yml) sous votre bloc `services:`. Ne pas remplacer vos services existants ou vos URL HTTPS.

Ajouter ces variables d'environnement à **cette stack Open Wearables** :

```dotenv
GADGETBRIDGE_API_KEY=REMPLACER_PAR_LA_CLE_API_OPEN_WEARABLES
GADGETBRIDGE_USER_ID=REMPLACER_PAR_UUID_UTILISATEUR
GADGETBRIDGE_UID=1000
GADGETBRIDGE_GID=1000
```

`GADGETBRIDGE_API_KEY` est la clé créée dans **Settings → API keys**, pas le mot de passe administrateur. `GADGETBRIDGE_USER_ID` est l'UUID de l'utilisateur de santé dans **Users**, pas l'identifiant du compte développeur. Réutiliser l'utilisateur déjà testé pour conserver un historique unique. La clé est transmise à l'importeur par variable d'environnement ; elle n'est pas inscrite dans ses arguments ou journaux.

Le service communique avec `http://app:8000` sur le réseau Docker de la pile. Nginx Proxy Manager et les certificats publics ne sont donc pas nécessaires à cette communication interne. Il utilise la même image backend que les autres services, mais s'exécute avec l'UID/GID propriétaire des fichiers.

Pour une gestion par CLI, l'équivalent est :

```bash
docker compose -f deploy/gadgetbridge/compose.yml \
  -f deploy/gadgetbridge/compose.automation.yml up -d
```

Les variables doivent alors être présentes dans le `.env` local existant ou dans l'environnement du processus Compose. Pour un export multi-appareils/utilisateurs, ajouter au `command` du service `--device-id` / `--gadgetbridge-user-id` avec la sélection vérifiée. Les options du CLI peuvent également modifier le délai de stabilisation, le polling, la taille des lots et le délai de reprise.

## 6. Vérifier la chaîne complète

1. Dans Gadgetbridge, lancer le test d'export et contrôler sa réussite.
2. Dans Syncthing, attendre **À jour** pour le dossier. Sur Ubuntu : `stat /srv/gadgetbridge/incoming/Gadgetbridge.db` confirme la réception.
3. Dans Portainer, ouvrir les logs de `gadgetbridge-importer`. Après un fichier stable pendant 30 secondes, le résultat doit être **`confirmed`**. `waiting_for_export` indique un fichier absent ou un mauvais nom ; `waiting_for_stable_file` indique l'attente de stabilisation ; `unchanged` indique un export déjà traité.
4. Vérifier les mesures et les synchronisations dans la fiche de l'utilisateur Open Wearables, sur les dates réellement présentes dans l'export.
5. Synchroniser ensuite de nouvelles données du bracelet, relancer l'export Android et vérifier qu'un nouvel import automatique est confirmé.
6. Redémarrer le conteneur importeur avec ses bind mounts conservés : le dernier fichier confirmé ne doit pas être renvoyé.

**HTTP 202 n'est jamais une confirmation d'import.** Le service attend le résultat Celery de chaque lot, vérifie les compteurs et signale les types historiques terminés. `status.json` conserve l'empreinte du fichier confirmé, l'heure du dernier succès et le travail éventuellement en attente. Chaque job conserve un `checkpoint.json` et un `report.json`. Les payloads complets sont supprimés après confirmation ; ils restent disponibles uniquement pendant une reprise.

Le fichier est attendu pendant 30 secondes sans changement de métadonnées, puis copié dans un instantané privé. L'identité du fichier est vérifiée avant/après copie et SQLite `quick_check` doit réussir. Une copie tronquée n'est pas envoyée. Le contenu confirmé est identifié par SHA-256 ; un fichier identique ou un redémarrage ne provoque pas de nouvel envoi.

En cas d'erreur, le service conserve le travail en cours et attend 5 minutes avant une nouvelle tentative. Il cherche d'abord la confirmation de l'ancien lot ; un lot échoué ou sans confirmation peut être renvoyé avec un nouvel identifiant. Le traitement est donc **au moins une fois**, avec la déduplication déjà vérifiée en base. Un nouvel export reçu pendant une panne attend que le travail précédent soit terminé. Les logs rapportent des statuts et classes d'erreurs, jamais la clé ni les valeurs des mesures.

Si l'importeur reste en erreur, vérifier la clé, l'UUID, l'état du worker et ses journaux, puis le schéma du fichier. Ne pas supprimer le dossier `importer` pour résoudre un incident sans examiner les lots en attente. Un changement de serveur, utilisateur, fuseau ou taille de lot exige un nouvel emplacement d'état ou une réconciliation planifiée ; l'état ne peut pas être réaffecté silencieusement.

## Limites et validation

Chaque export modifié est converti intégralement. L'API déduplique les mesures déjà présentes ; le watcher évite les envois de fichiers strictement inchangés. Il ne s'agit pas encore d'une extraction SQL incrémentale. Les corrections de valeurs historiques déjà importées ne sont pas automatiquement remplacées par la déduplication. Les limites de mapping du [guide Gadgetbridge](../../docs/providers/gadgetbridge.mdx) restent applicables, notamment le stress Huawei non converti.

L'export automatique a été vérifié dans le code officiel Gadgetbridge, révision `a19e7e14c810697f9c02fa12ee4cff0839584302`, notamment `DatabaseExportWorker`, `PeriodicDbExporter`, `PeriodicExporter` et les paramètres Android. Le transfert local Syncthing a été exercé entre deux conteneurs avec découverte globale et relais désactivés : fichier SQLite initial et mise à jour identiques. Ces deux conteneurs simulent le transfert ; la configuration réelle du Samsung reste à effectuer et vérifier sur place.

Validation serveur : 3 089 tests backend réussis (deux ignorés), dont 12 nouveaux tests du watcher, et contrôles pré-commit réussis. Le service Docker a été exercé avec un UID non-root : export synthétique détecté et confirmé dans PostgreSQL, redémarrage sans duplication, transfert tronqué rejeté, puis nouvelle version automatiquement convertie et importée. La réception Syncthing et sa mise à jour ont été testées séparément entre deux appareils simulés par des conteneurs. Les commandes et services n'ont pas été exécutés sur `serv-kaell` ni sur le Samsung ; leur activation locale suit les étapes ci-dessus.
