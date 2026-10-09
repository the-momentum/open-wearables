# Gadgetbridge sur serv-kaell (Ubuntu, Docker et Portainer)

Cette pile indépendante ajoute Open Wearables au serveur. Elle ne modifie pas les piles Endurain (`/opt/stacks/endurain`, port 8095) et Home Assistant. Le fournisseur Gadgetbridge et le convertisseur sont décrits dans [le guide d'utilisation](../../docs/providers/gadgetbridge.mdx).

## Préparer une version

Utiliser une révision Git contenant cette intégration, après revue et commit des changements. Les images officielles Open Wearables ne contiennent pas cette nouvelle stratégie tant qu'elle n'y est pas intégrée. Construire les images à partir du checkout, jamais en éditant un conteneur.

```bash
cd /opt/stacks
git clone https://github.com/KaellWin/open-wearables.git open-wearables
cd open-wearables
git checkout <revision-contenant-integration>
cp deploy/gadgetbridge/.env.example deploy/gadgetbridge/.env
chmod 600 deploy/gadgetbridge/.env
```

Vérifier les ports sur **le serveur cible** avant de choisir les valeurs :

```bash
ss -ltn
docker ps --format '{{.Names}} {{.Ports}}'
```

Les valeurs proposées, 18000 pour l'API et 13000 pour l'interface, diffèrent du port Endurain 8095. Leur disponibilité a été vérifiée dans l'environnement de développement, pas sur `serv-kaell`. Si elles sont occupées, modifier `OW_API_PORT` et `OW_FRONTEND_PORT`. Garder `OW_BIND_ADDRESS=127.0.0.1` pour l'accès par tunnel SSH ou proxy HTTPS.

Créer `/srv/open-wearables`, dédié à cette pile, avec les permissions permettant aux images PostgreSQL/Redis d'initialiser leurs sous-répertoires. Ne pas réutiliser les répertoires d'autres services.

Compléter `.env` localement, sans afficher ses valeurs dans les journaux ni les ajouter à Git :

| Variable | Rôle |
| --- | --- |
| `OW_IMAGE_TAG` | Révision Git complète revue, utilisée pour les deux images locales |
| `OW_DATA_DIR` | `/srv/open-wearables`, données PostgreSQL, Redis et planificateur |
| `DB_PASSWORD` | Mot de passe aléatoire PostgreSQL, sans espaces ni caractères réservés d'URL |
| `SECRET_KEY` | Secret aléatoire de signature, stable entre redémarrages |
| `MASTER_KEY` | Clé Fernet, stable et indispensable pour restaurer les données chiffrées |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Compte administrateur initial, mot de passe fort |
| `API_BASE_URL` | URL publique de l'API, par exemple `https://wearables-api.example.net` |
| `FRONTEND_URL` | Origine exacte de l'interface, par exemple `https://wearables.example.net` |
| `OW_BIND_ADDRESS`, `OW_API_PORT`, `OW_FRONTEND_PORT` | Adresse d'écoute et ports vérifiés |
| `POSTGRES_IMAGE`, `REDIS_IMAGE`, `PYTHON_IMAGE`, `UV_IMAGE`, `BUN_IMAGE` | Images de base ; fixer leurs digests `@sha256:…` pour une release reproductible |
| `OW_ENV_FILE` | `.env` par défaut, `stack.env` pour Portainer |

Générer `MASTER_KEY` avec `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` dans un terminal privé disposant de cette dépendance. Les autres secrets peuvent être générés avec `openssl rand -hex 32`. Enregistrer les valeurs uniquement dans le fichier local et le coffre/système de sauvegarde choisi.

Le Compose impose une valeur non vide pour les secrets indispensables. Les images sont versionnées, les installations Python/Bun utilisent les lockfiles du dépôt ; des tags de base restent mutables, d'où la recommandation de digests pour les releases.

## Construire et démarrer avec Docker Compose

Depuis la racine du dépôt :

```bash
docker compose -f deploy/gadgetbridge/compose.yml \
  -f deploy/gadgetbridge/compose.build.yml config --quiet
docker compose -f deploy/gadgetbridge/compose.yml \
  -f deploy/gadgetbridge/compose.build.yml build
docker compose -f deploy/gadgetbridge/compose.yml up -d
docker compose -f deploy/gadgetbridge/compose.yml ps
docker compose -f deploy/gadgetbridge/compose.yml logs --tail=100 app worker
curl --fail http://localhost:18000/
```

La pile comprend PostgreSQL 18, Redis 8 avec AOF, API, worker Celery, beat et interface web. Seules l'API et l'interface publient un port sur l'hôte. L'API exécute les migrations et initialise les paramètres/priorités des fournisseurs au démarrage ; aucun OAuth Gadgetbridge n'est nécessaire. La télémétrie, Sentry, les webhooks sortants, l'offload S3 et le stockage des payloads bruts sont désactivés dans cette pile.

Pour un tunnel depuis votre ordinateur :

```bash
ssh -L 13000:127.0.0.1:13000 -L 18000:127.0.0.1:18000 utilisateur@192.168.0.2
```

Configurer alors `FRONTEND_URL=http://localhost:13000` et `API_BASE_URL=http://localhost:18000`. Pour l'accès LAN direct, installer un proxy HTTPS et définir les deux URL HTTPS. Les cookies sécurisés de l'interface peuvent empêcher la connexion persistante sur une adresse LAN en HTTP. Si un proxy Docker utilise le réseau de cette pile, vérifier ses permissions et ses routes avant de l'y connecter. Ne pas exposer PostgreSQL ou Redis.

Créer un utilisateur et une clé API dans le portail, activer Gadgetbridge, puis exécuter le convertisseur depuis `backend` ou dans une installation Python locale utilisant les dépendances du dépôt. Les fichiers SQLite et le répertoire de sortie restent privés sur l'hôte. L'API est accessible via tunnel ou HTTPS ; aucune dépendance à Internet Helper pour cet import.

## Portainer

Construire d'abord les deux images sur le même moteur Docker que Portainer, avec les commandes ci-dessus. `compose.yml` contient uniquement des références d'images ; `compose.build.yml` est réservé au build. Il n'est donc pas nécessaire que l'éditeur Portainer résolve des contextes de build relatifs.

Dans Portainer, créer une pile distincte **open-wearables-gadgetbridge**, coller/téléverser `deploy/gadgetbridge/compose.yml`, puis renseigner les variables de `.env.example` dans la configuration d'environnement de cette pile. Ajouter `OW_ENV_FILE=stack.env` pour utiliser le fichier d'environnement généré par Portainer. Garder le même `OW_IMAGE_TAG` que les images construites. Ces images sont locales : ne pas activer une option qui impose leur téléchargement depuis un registre. Pour un autre moteur Docker, transférer les images avec `docker image save`/`load` ou utiliser votre registre privé et adapter leurs noms.

Si la pile a déjà été lancée par CLI, arrêter **cette pile** avec `docker compose -f deploy/gadgetbridge/compose.yml down` avant sa gestion par Portainer, puis déployer sous le même nom et avec les mêmes chemins de données. `down` sans `--volumes` ne supprime pas les bind mounts. Éviter deux gestionnaires concurrents de la même pile. Les instructions ont été vérifiées via Docker Compose ; l'interface Portainer de votre serveur n'était pas accessible dans cette tâche.

## Sauvegarde

Sauvegarder PostgreSQL, les secrets, la configuration, la révision et les images avant chaque mise à jour. Redis conserve la queue et les états récents des imports ; les checkpoints du convertisseur se sauvegardent séparément avec les exports privés.

Exemple exécuté depuis la racine du dépôt, dans un terminal administrateur local. Choisir un répertoire de sauvegarde privé, hors Git :

```bash
backup_dir=/srv/backups/open-wearables/$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
umask 077
docker compose -f deploy/gadgetbridge/compose.yml stop frontend app worker beat
docker compose -f deploy/gadgetbridge/compose.yml exec -T db \
  pg_dump -U open-wearables -d open-wearables -Fc > "$backup_dir/database.dump"
docker compose -f deploy/gadgetbridge/compose.yml exec -T redis redis-cli SAVE
docker compose -f deploy/gadgetbridge/compose.yml stop redis
cp deploy/gadgetbridge/.env "$backup_dir/environment.env"
cp deploy/gadgetbridge/compose*.yml "$backup_dir/"
git rev-parse HEAD > "$backup_dir/revision.txt"
# OW_DATA_DIR peut différer : adapter ce chemin à votre configuration.
tar -C /srv/open-wearables -czf "$backup_dir/queue-and-beat.tar.gz" redis beat
docker compose -f deploy/gadgetbridge/compose.yml up -d
```

Vérifier les codes de sortie ; en cas d'échec, arrêter la procédure et remettre cette pile en fonctionnement. Conserver également les images exactes, par exemple `docker image save local/open-wearables-backend:<ancienne-revision> local/open-wearables-frontend:<ancienne-revision> -o "$backup_dir/images.tar"`. Protéger et tester les sauvegardes : elles contiennent des données de santé et des secrets. Ne pas copier un répertoire PostgreSQL actif comme seule sauvegarde.

## Mise à jour et retour arrière

1. Effectuer une sauvegarde cohérente et noter les tags d'images précédents.
2. Récupérer la nouvelle révision, lire ses migrations et notes, puis la sélectionner. Préserver le `.env` local.
3. Définir un nouveau `OW_IMAGE_TAG` correspondant à cette révision, construire avec `compose.build.yml`, puis lancer `compose.yml up -d` ou redéployer la pile Portainer avec ce tag.
4. Vérifier les migrations, la santé des services, une connexion au portail et un petit import confirmé jusque dans PostgreSQL. Conserver les images précédentes et le dump.

Si les migrations sont compatibles en arrière, remettre le tag précédent et relancer les services. Si elles ne le sont pas, restaurer le dump et les secrets avec la révision correspondante plutôt que lancer un ancien code sur un nouveau schéma. La restauration remplace les données postérieures à la sauvegarde : effectuer d'abord une sauvegarde de l'état actuel.

Pour une restauration planifiée, arrêter les services applicatifs, garder PostgreSQL démarré, restaurer le dump avec `pg_restore --clean --if-exists --no-owner -U open-wearables -d open-wearables`, via `docker compose exec -T db` et redirection du dump en entrée. Ne pas lancer l'API avant d'avoir sélectionné les anciennes images et les anciennes clés. Restaurer Redis/beat uniquement conteneurs arrêtés ; des tâches restaurées peuvent être rejouées. Réconcilier les checkpoints du convertisseur et utiliser sa déduplication. Tester d'abord la restauration dans une pile isolée sur d'autres chemins et ports.

## Validation de cette implémentation

Les deux images ont été construites dans l'environnement cloud et les six services démarrés. L'export fourni a traversé l'API, Celery et PostgreSQL : 29 lots confirmés, 13 312 mesures, deux sessions de sommeil, une activité. La reprise avec checkpoint et le renvoi des mêmes lots ont été vérifiés sans duplication. La sauvegarde PostgreSQL a aussi été restaurée dans une base isolée : les 13 312 mesures y ont été retrouvées. La base originale a été ouverte en lecture seule et n'est pas ajoutée au dépôt. Aucun déploiement n'a été effectué sur `serv-kaell` et aucun service Endurain/Home Assistant n'a été modifié.

## Synchronisation automatique

Pour exporter périodiquement sur Android, transférer le fichier sur le LAN et convertir/importer automatiquement dans Docker, suivre [AUTOMATION.md](AUTOMATION.md). Les services optionnels sont fournis dans `compose.syncthing.yml` et `compose.automation.yml`.
