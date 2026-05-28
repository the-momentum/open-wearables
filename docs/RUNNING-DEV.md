# Running the Bazard.run stack in dev

Doc unique pour lancer tout l'écosystème en local. La même version est copiée dans les 4 repos :

- `bazard.run/` (landing Astro)
- `api.bazard.run/` (API Go)
- `app.bazard.run/` (Next.js)
- `wearables.bazard.run/` (OpenWearables, self-host)

---

## TL;DR — démarrage rapide (déjà setup)

Dans **4 terminaux**, depuis `~/Documents/Code/moi/bazard.run/` :

```bash
# 1. Redis (one-shot, idempotent)
cd api.bazard.run && task dev:redis

# 2. API Go (hot reload)
cd api.bazard.run && task dev                    # http://localhost:8080

# 3. Frontend Next.js
cd app.bazard.run && pnpm dev                    # http://localhost:3000

# 4. OpenWearables (uniquement si tu testes les wearables)
cd wearables.bazard.run && make up               # http://localhost:8000

# 5. Landing (uniquement si tu touches à la vitrine)
cd bazard.run && pnpm dev                        # http://localhost:4321
```

Pas besoin de tout lancer à chaque fois — l'**API + App** suffit pour 90% du dev.

---

## Architecture

```
                                     ┌──────────────┐
                                     │  bazard.run  │  Astro landing (publique)
                                     │   :4321      │  pitch, /patch-notes, /docs
                                     └──────────────┘

  ┌────────────────────┐     ┌──────────────────────────────────────┐
  │  app.bazard.run    │     │  api.bazard.run                      │
  │   :3000            │ ──→ │   :8080  ──→ Neon Postgres (dev)     │
  │  Next.js, AlignUI  │     │   Go, Fuego, hexagonal               │
  │  TanStack Query    │     │   ──→ Redis local :6379              │
  └────────────────────┘     │   ──→ OW (si WEARABLES_ENABLED=true) │
                             └──────────────────────────────────────┘
                                              ▲
                                              │ webhooks Svix
                             ┌────────────────┴─────────────┐
                             │  wearables.bazard.run        │
                             │   :8000  OpenWearables       │
                             │   Backend FastAPI + Front    │
                             │   ──→ Strava/Garmin/Oura/... │
                             └──────────────────────────────┘
```

**Règle d'or** : la base de données est **Neon** (cloud). Chaque dev a sa propre **branche Neon** (`dev-jeremy`, `dev-...`) pour ne JAMAIS toucher la prod. Pas de Postgres local.

---

## Prérequis (à installer une fois)

```bash
# Communs
brew install go-task/tap/go-task pnpm
nvm install                              # picks .nvmrc (Node 22)

# API Go
brew install go ariga/tap/atlas
go install github.com/air-verse/air@latest

# OpenWearables (Docker)
# Docker Desktop déjà installé
```

**Versions cibles** :
- Go 1.25.4 (cf. `api.bazard.run/.go-version`)
- Node 22 (cf. `app.bazard.run/.nvmrc`)
- pnpm 11+

---

## Setup initial (une fois par machine)

### 1. Cloner les 4 repos

```bash
mkdir -p ~/Documents/Code/moi/bazard.run && cd $_
gh repo clone IDK-JB/bazard.run
gh repo clone IDK-JB/api.bazard.run
gh repo clone IDK-JB/app.bazard.run
gh repo clone IDK-JB/wearables.bazard.run
```

### 2. Créer une branche Neon dédiée dev

Sur [Neon UI](https://console.neon.tech) → ton projet Bazard → **Branches** → **Create branch** `dev-<prénom>` (forké depuis `main`).

Récupère les 2 URLs de connexion :
- L'URL **pooler** (avec `-pooler` dans le hostname) → `DATABASE_URL`
- L'URL **directe** (sans `-pooler`) → `DATABASE_URL_MIGRATE`

### 3. Configurer chaque repo

```bash
# API
cd api.bazard.run
cp .env.example .env
#   → remplir : DATABASE_URL, DATABASE_URL_MIGRATE, JWT_SECRET (openssl rand -hex 32),
#               RESEND_API_KEY (vide OK en dev → console log)
go mod download
task migrate                              # applique schema/schema.sql sur la branche Neon
task seed                                 # data dev (athletes, sessions)

# App
cd ../app.bazard.run
cp .env.example .env
#   → laisser NEXT_PUBLIC_API_URL vide (proxy local), NEXT_PUBLIC_ENV=dev
pnpm install

# OpenWearables (si tu testes les wearables)
cd ../wearables.bazard.run
cp backend/config/.env.example backend/config/.env
#   → suivre contributing/bazard-dev-setup.md pour les creds Strava sandbox
make up                                   # premier build Docker (lent)

# Landing (rarement touchée)
cd ../bazard.run
pnpm install
```

### 4. Vérifier que tout boot

```bash
cd api.bazard.run
task dev:redis                            # démarre Redis local
task dev                                  # API doit log "server starting" sur :8080

# Dans un autre terminal
cd app.bazard.run
pnpm dev                                  # App sur :3000

# Ouvre http://localhost:3000 → banner rose "DEV" en haut + login OK
```

---

## Workflow dev quotidien

### Mode classique (90% du temps)

```bash
# Terminal 1 — Redis (souvent déjà tourne)
task dev:redis

# Terminal 2 — API
cd api.bazard.run && task dev

# Terminal 3 — App
cd app.bazard.run && pnpm dev

# → code, save, hot reload partout (Air côté Go ~1s, Turbopack côté Next ~instantané)
```

### Mode wearables (test du flow Garmin/Strava)

#### Lancer OW

```bash
cd wearables.bazard.run

# Première fois seulement
cp backend/config/.env.example backend/config/.env

# Démarrer la stack (db + backend + celery + svix + redis + frontend)
docker compose up -d
# ou : make up   (non-détaché, voit les logs)
```

#### Services exposés

| Service | URL | Usage |
|---|---|---|
| Backend OW (FastAPI) | http://localhost:8000 | Swagger : `/docs`, admin : `/admin` |
| Frontend OW | http://localhost:3000 | ⚠️ **conflit** avec `pnpm dev` du front Bazard |
| Svix dashboard | http://localhost:8071 | Configure les webhooks vers l'API |
| Flower (Celery) | http://localhost:5555 | Monitoring jobs |
| Redis OW | localhost:6379 | ⚠️ **conflit** avec `task dev:redis` |
| Postgres OW | localhost:5432 | DB interne OW |

#### ⚠️ 2 conflits de ports à gérer

**Port 3000** (frontend OW vs frontend Bazard) — Stoppe le frontend OW une fois la clé admin récupérée :
```bash
cd wearables.bazard.run && docker compose stop frontend
```
L'admin OW reste accessible via http://localhost:8000/admin.

**Port 6379** (Redis OW vs `task dev:redis`) — Deux options :
- **Recommandé** : partage le Redis OW avec l'API Bazard. Ne lance PAS `task dev:redis`, le `REDIS_URL=redis://localhost:6379` dans `.env` api tape sur OW (caches séparés par préfixe de clé).
- **Alternative** : OW sur un autre port Redis. Crée `wearables.bazard.run/.env` :
  ```dotenv
  REDIS_PORT=6380
  ```

#### Setup 1ère fois (récupérer creds OW + Strava sandbox)

```bash
# 1. Lance OW
cd wearables.bazard.run && docker compose up -d

# 2. Récupère la clé admin OW
#    → http://localhost:3000 (front OW) ou direct API :8000/admin
#    → admin@admin.com / your-secure-password
#    → Settings → API Credentials → générer

# 3. Mets dans api.bazard.run/.env :
#    WEARABLES_ENABLED=true
#    OPENWEARABLES_BASE_URL=http://localhost:8000
#    OPENWEARABLES_API_KEY=<clé>

# 4. Sur http://localhost:8071 (Svix) — crée un endpoint :
#    URL: http://host.docker.internal:8080/api/v1/webhooks/openwearables
#    Filter: connection.created, workout.created
#    → copie le whsec_... dans api/.env :
#    OPENWEARABLES_WEBHOOK_SECRET=whsec_...

# 5. Strava sandbox (https://www.strava.com/settings/api, callback "localhost")
#    Dans wearables.bazard.run/backend/config/.env :
#    STRAVA_CLIENT_ID=...
#    STRAVA_CLIENT_SECRET=...

# 6. Recharge OW pour prendre les creds Strava
docker compose restart app celery-worker celery-beat svix-server

# 7. Redémarre l'API pour prendre WEARABLES_ENABLED
#    (Air ne reload pas sur changement .env)
```

#### Stopper OW

```bash
cd wearables.bazard.run
make stop                  # garde les data
make down                  # stoppe + supprime containers (data conservées dans volumes)
docker compose down -v     # nuke complet (PERD la DB OW dev — il faudra re-setup)
```

Détails et troubleshooting end-to-end : `wearables.bazard.run/contributing/bazard-dev-setup.md`.

### Mode container (validation pré-push)

```bash
cd api.bazard.run
task docker:down      # tuer un éventuel reste
task docker:up        # rebuild image + boot api + redis en compose
# → vérifie que l'image Coolify boot, que les migrations passent au container start
task docker:down
```

À faire **avant** de push une modif de `Dockerfile`, `entrypoint.sh`, ou `schema/schema.sql`.

---

## Opérations courantes

### Migrations DB

```bash
# Modifier schema/schema.sql, puis :
cd api.bazard.run
task migrate:diff     # preview du diff (Atlas)
task migrate          # apply sur la branche Neon dev
```

### Reset / re-seed dev data

```bash
task migrate          # idempotent
task seed             # ré-applique les fixtures
```

### Régénérer le client TS depuis l'OpenAPI

```bash
# WIP, voir Taskfile.yml > generate:client
```

### Stopper tout

```bash
# API natif
^C                                        # dans le terminal task dev

# Redis dev
cd api.bazard.run && task dev:redis:stop

# OW
cd wearables.bazard.run && make down

# Compose api (si lancé)
cd api.bazard.run && task docker:down
```

---

## Dépannage

### `bind: address already in use` au boot de l'API

Un container Docker squatte le port 8080. Liste-le :
```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```
Si tu vois `apibazardrun-api-1` → `task docker:down`.

### `redis: lookup redis: no such host`

Ton `.env` api a `REDIS_URL=redis://redis:6379` (hostname du compose).
En mode natif (`task dev`), c'est `redis://localhost:6379`. Édite `.env`.

L'API boot quand même sans Redis (WARN puis "running without cache") — pas urgent à fixer.

### `task dev` plante : `no Go files in <repo>`

`.air.toml` manquant ou cassé — il doit pointer vers `cmd/api` :
```toml
[build]
  cmd = "go build -o ./tmp/main ./cmd/api"
  bin = "./tmp/main"
```

### Migrations bloquées (`task migrate` plante)

Atlas refuse les URLs pooler. Vérifie que `DATABASE_URL_MIGRATE` est l'URL **directe** (sans `-pooler` dans le hostname).

### App affiche écran blanc ou 502 sur les requêtes

- L'API tourne-t-elle ? `curl http://localhost:8080/health`
- Le proxy Next fonctionne-t-il ? `curl http://localhost:3000/api/health`
- Si l'app est buildée pour prod (`NEXT_PUBLIC_API_URL` non vide), le proxy est désactivé et l'app tape directement sur l'URL configurée.

### `pnpm dev` plante avec une erreur de package

```bash
cd app.bazard.run
rm -rf node_modules .next && pnpm install
```

### OW container ne démarre pas

```bash
cd wearables.bazard.run
docker compose logs -f                    # voir l'erreur précise
docker compose down -v                    # reset complet (perd les data OW locales)
make up
```

---

## Isolation prod/dev — rappels

| Risque | Garde-fou |
|---|---|
| Toucher la DB prod | Branche Neon dédiée dev (`DATABASE_URL` pointe sur `dev-...`) |
| Envoyer des emails réels | `RESEND_API_KEY` vide en dev → logs console |
| Connecter un vrai compte Garmin/Strava | Apps **sandbox** uniquement côté OW |
| Pusher des secrets | `.env*` gitignored sauf `.env.example` |
| Run prod localement | Coolify a ses propres vars d'env — aucun `.env*` du repo n'est lu en prod |

---

## Liens utiles

- [Neon console](https://console.neon.tech)
- [Coolify dashboard](#) (URL interne)
- [Resend dashboard](https://resend.com)
- API docs Fuego : `http://localhost:8080/swagger`
- AlignUI docs : https://alignui.com
- Linear : https://linear.app/bazardrun

---

**Source de vérité** : ce fichier est dupliqué dans les 4 repos. Si tu le modifies, synchronise les 4. (À terme, on peut le mettre dans `bazard.run/docs/` et linker — TODO.)
