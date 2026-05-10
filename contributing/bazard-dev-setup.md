# Bazard dev setup

> Comment lancer `wearables.bazard.run` en local pour développer Bazard
> de bout en bout (athlète connecte Strava → activité importée dans
> `app.bazard.run` via `api.bazard.run`).

Cette page est **Bazard-only**. Pour la doc upstream OW, voir `contributing/developing.md`.

## Pré-requis

- Docker + Docker Compose
- Les 3 repos clonés à plat dans `~/.../bazard.run/` :
  ```
  bazard.run/
  ├── api.bazard.run/
  ├── app.bazard.run/
  └── wearables.bazard.run/   ← tu es ici
  ```
- Une app Strava sandbox sur https://www.strava.com/settings/api
  (Authorization Callback Domain : `localhost`).

## Setup initial

```bash
# 1. Copier le template Bazard dev
cp backend/config/.env.dev.example backend/config/.env

# 2. Remplir les valeurs Strava (et autres providers si besoin)
$EDITOR backend/config/.env
#   STRAVA_CLIENT_ID=...
#   STRAVA_CLIENT_SECRET=...

# 3. Lancer la stack OW (db + app + celery + svix + redis + frontend)
docker compose up
```

OW démarre sur :

| Service | URL |
|---|---|
| Backend OW (FastAPI) | http://localhost:8000 |
| Frontend OW (admin) | http://localhost:3000 (collision avec `app.bazard.run` — utilise un seul à la fois ou drop ce service) |
| Svix dashboard | http://localhost:8071 |
| Flower (monitoring Celery) | http://localhost:5555 |

> **Tip** : le frontend OW prend le port `3000` qu'utilise `app.bazard.run`. Dans le compose, commente le service `frontend` si tu n'en as pas besoin. Le backend (port 8000) suffit pour faire marcher le flow Bazard.

## Récupérer la clé API OW

`api.bazard.run` parle à OW en server-to-server avec une clé admin :

1. Au premier boot, OW crée un compte admin (cf `ADMIN_EMAIL` / `ADMIN_PASSWORD` dans le `.env`).
2. Connecte-toi sur http://localhost:8000/admin (ou via le frontend OW si tu le lances).
3. Va dans **Settings → API Credentials** → génère une clé.
4. Copie-la dans `api.bazard.run/.env.dev` :
   ```
   OPENWEARABLES_API_KEY=<la clé générée>
   ```

## Configurer le webhook Svix → API

OW pousse les events (`workout.created`, `connection.created`) vers `api.bazard.run` via Svix.

1. Sur http://localhost:8071, crée un endpoint :
   - URL : `http://host.docker.internal:8080/api/v1/webhooks/openwearables`
   - Filter types : `connection.created`, `workout.created`
2. Copie le `whsec_...` généré dans `api.bazard.run/.env.dev` :
   ```
   OPENWEARABLES_WEBHOOK_SECRET=whsec_xxxxx
   ```

## Vérification end-to-end

1. Lance `api.bazard.run` : `cd ../api.bazard.run && task dev` (ou `docker compose up`).
2. Lance `app.bazard.run` : `cd ../app.bazard.run && pnpm dev`.
3. Sur http://localhost:3000, crée un compte coach, va sur `/profile`, clique "Connecter Strava".
4. Tu es redirigé vers Strava → autorise → retour sur l'app.
5. Si tout est bien câblé : la card Strava passe sur "Connecté" et tes 30 derniers jours d'activités apparaissent dans le calendrier.

## Troubleshooting

- **OW timeout au connect Strava** : vérifie que `API_BASE_URL=http://localhost:8000` dans `backend/config/.env` (Strava redirige sur cette URL après auth).
- **API ne reçoit pas les webhooks** : vérifie l'endpoint Svix (URL + secret) et que `host.docker.internal` est résolu côté Linux (ajouter `extra_hosts: ["host.docker.internal:host-gateway"]` dans le compose api).
- **Card Strava reste "En attente"** : OW upstream n'émet `connection.created` qu'au premier connect. Si tu reconnectes après revoke, déclenche `POST /api/v1/me/wearables/sync` côté API (le bouton « Resync » dans `/profile` côté app le fait pour toi).
