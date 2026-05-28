# Bazard dev setup

> Comment lancer `ow.bazard.run` en local pour développer Bazard de
> bout en bout (athlète connecte Strava → activité importée dans
> `app.bazard.run` via `api.bazard.run`).

Cette page est **Bazard-only** (jamais pushée upstream). Elle s'appuie
sur le setup **natif d'OpenWearables** documenté dans
[`contributing/developing.md`](developing.md) — pas d'override Bazard
dans le repo.

## Pré-requis

- Docker + Docker Compose
- Les 3 repos clonés à plat dans `~/.../bazard.run/` :
  ```
  bazard.run/
  ├── api.bazard.run/
  ├── app.bazard.run/
  └── ow.bazard.run/   ← tu es ici
  ```
- Une app Strava sandbox sur https://www.strava.com/settings/api
  (Authorization Callback Domain : `localhost`).

## Setup initial

```bash
# 1. Copier l'.env.example natif (rien de Bazard-spécifique à modifier
#    pour un premier boot — les defaults marchent).
cp backend/config/.env.example backend/config/.env

# 2. Lancer la stack OW (db + app + celery + svix + redis + frontend)
docker compose up -d
```

OW démarre sur :

| Service | URL | Notes |
|---|---|---|
| Backend OW (FastAPI) | http://localhost:8000 | Swagger UI : `/docs` |
| Frontend OW (admin) | http://localhost:3000 | **Conflit avec `pnpm dev` d'`app.bazard.run`** — un seul à la fois sur le port 3000. Stoppe l'un ou l'autre selon le besoin (`docker compose stop frontend` côté wearables pour libérer 3000). |
| Svix dashboard | http://localhost:8071 | |
| Flower (monitoring Celery) | http://localhost:5555 | |

## Étape 1 — Récupérer la clé API OW

`api.bazard.run` parle à OW en server-to-server avec une clé admin.

1. Va sur **http://localhost:3000** (frontend OW).
2. Connecte-toi avec les defaults seedés par l'`.env.example` natif :
   - Email : `admin@admin.com`
   - Password : `your-secure-password`
3. Va dans **Settings → API Credentials** → génère une clé.
4. Copie-la dans `api.bazard.run/.env` :
   ```
   OPENWEARABLES_API_KEY=<la clé générée>
   ```

> **Tip** : pour changer ces credentials, édite `ADMIN_EMAIL` /
> `ADMIN_PASSWORD` dans `backend/config/.env` **AVANT le premier boot**.
> Le seed n'a lieu qu'une fois ; un changement après coup nécessite un
> `docker compose down -v` (perte de la DB OW dev).

## Étape 2 — Configurer le webhook Svix → API

OW pousse les events (`workout.created`, `connection.created`) vers
`api.bazard.run` via Svix.

1. Sur http://localhost:8071, crée un endpoint :
   - URL : `http://host.docker.internal:8080/api/v1/webhooks/openwearables`
   - Filter types : `connection.created`, `workout.created`
2. Copie le `whsec_...` généré dans `api.bazard.run/.env` :
   ```
   OPENWEARABLES_WEBHOOK_SECRET=whsec_xxxxx
   ```

## Étape 3 — Strava sandbox

Édite `backend/config/.env` :

```
STRAVA_CLIENT_ID=<client_id de ton app Strava sandbox>
STRAVA_CLIENT_SECRET=<client_secret>
```

Puis recharge le backend :

```bash
docker compose restart app celery-worker celery-beat svix-server
```

## Vérification end-to-end

1. Stoppe le frontend OW pour libérer le port 3000 :
   ```bash
   docker compose stop frontend
   ```
2. Lance `api.bazard.run` : `cd ../api.bazard.run && task dev`
   (mode natif recommandé, hot reload Air).
3. Lance `app.bazard.run` : `cd ../app.bazard.run && pnpm dev`.
4. Sur http://localhost:3000, crée un compte coach, va sur `/profile`,
   clique "Connecter Strava".
5. Tu es redirigé vers Strava → autorise → retour sur l'app.
6. Si tout est bien câblé : la card Strava passe sur "Connecté" et toutes
   tes activités Strava apparaissent dans le calendrier (backfill 10 ans
   par défaut côté API).

## Troubleshooting

- **OW timeout au connect Strava** : vérifie que `API_BASE_URL=http://localhost:8000`
  dans `backend/config/.env` (Strava redirige sur cette URL après auth).
- **API ne reçoit pas les webhooks** : vérifie l'endpoint Svix (URL +
  secret) et que `host.docker.internal` est résolu côté Linux
  (`extra_hosts: ["host.docker.internal:host-gateway"]` à ajouter côté
  api).
- **Card Strava reste "En attente"** : OW upstream n'émet
  `connection.created` qu'au premier connect. Si tu reconnectes après
  revoke, déclenche `POST /api/v1/me/wearables/sync` côté API (le bouton
  « Resync » dans `/profile` côté app le fait pour toi).
- **Login OW échoue** : l'admin a été seedé avec les valeurs dans
  `backend/config/.env` au tout premier boot. Pour reset, `docker compose
  down -v` puis `up -d` recrée la DB OW vide et re-seede.
