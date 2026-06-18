# Deploying Open Wearables to Fly.io

Fly.io does not run `docker-compose.yml` directly. This setup maps the compose
stack to Fly apps:

| Compose service | Fly resource | Notes |
|---|---|---|
| `db` | Fly Managed Postgres | Managed cluster |
| `redis` | `open-wearables-redis` | Internal Redis app, private 6PN only |
| `app` | `open-wearables-api` process `web` | Public FastAPI app on `:8000` |
| `celery-worker` | `open-wearables-api` process `worker` | Same backend image |
| `celery-beat` | `open-wearables-api` process `beat` | Same backend image |
| `flower` | `open-wearables-flower` | Public Celery dashboard with basic auth |
| `svix-server` | `open-wearables-svix` | Internal webhook server on `.flycast` |
| `frontend` | `open-wearables-frontend` | Nitro server on `:3000` |

Config files in this repo:

- `backend/fly.toml` - API, worker, and beat process groups
- `frontend/fly.toml` - frontend Nitro server
- `deploy/fly/redis.toml` - internal Redis
- `deploy/fly/flower.toml` - Flower
- `deploy/fly/svix.toml` - Svix
- `deploy.ts` - optional Bun helper for deploying components in order

## 0. Prerequisites

```bash
fly auth login
bun --version
```

The examples below use the default app prefix `open-wearables` and region `iad`.
Override them without editing tracked files:

```bash
export FLY_APP_PREFIX=my-wearables
export FLY_REGION=iad
export FLY_ORG=my-fly-org
export FLY_API_URL=https://api.example.com
export FLY_FRONTEND_URL=https://app.example.com
```

You can also override individual app names:

```bash
export FLY_API_APP=my-wearables-api
export FLY_FRONTEND_APP=my-wearables-frontend
export FLY_FLOWER_APP=my-wearables-flower
export FLY_REDIS_APP=my-wearables-redis
export FLY_SVIX_APP=my-wearables-svix
```

Local files such as `.env.fly.local` are ignored by git, so private deployment
values can live outside the open-source branch.

## 1. Managed Postgres

```bash
fly mpg create --name open-wearables-db --region iad
```

Save the generated host, port, database, user, and password. The backend expects
individual database variables:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

The database user must be able to create the `svix` database. The backend startup
script runs `scripts/init/create_svix_db.py` before starting the API.

## 2. Internal Redis

Deploy the private Redis app:

```bash
bun run deploy redis
```

By default the backend reaches Redis at:

```text
open-wearables-redis.internal:6379
```

If you use a managed Redis instead, skip `bun run deploy redis` and set
`REDIS_HOST`, `REDIS_PORT`, `REDIS_USERNAME`, `REDIS_PASSWORD`, and `REDIS_SSL`
on the API and Flower apps with `fly secrets set`.

## 3. Backend Secrets

Set the required backend secrets:

```bash
fly secrets set -a open-wearables-api \
  DB_HOST=<postgres-host> DB_PORT=5432 DB_NAME=open-wearables \
  DB_USER=<postgres-user> DB_PASSWORD=<postgres-password> \
  SECRET_KEY="$(openssl rand -hex 32)" \
  ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD="$(openssl rand -hex 16)" \
  SVIX_JWT_SECRET="$(openssl rand -hex 32)"
```

Also set any provider credentials you need from `backend/config/.env.example`,
such as `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, Sentry, and S3/FIT settings.

Do not commit `.env` files. `backend/config/.env` is intentionally excluded from
Docker builds; Fly should receive secrets through `fly secrets set`.

## 4. Svix

Svix needs its own app and secrets. Use the same `SVIX_JWT_SECRET` value as the
backend.

```bash
fly apps create open-wearables-svix
fly secrets set -a open-wearables-svix \
  SVIX_JWT_SECRET=<same-as-backend> \
  SVIX_DB_DSN="postgresql://<postgres-user>:<postgres-password>@<postgres-host>:5432/svix" \
  SVIX_REDIS_DSN="redis://open-wearables-redis.internal:6379/1"
bun run deploy svix
```

The backend reaches Svix at:

```text
http://open-wearables-svix.flycast:8071
```

The deploy helper passes `SVIX_SERVER_URL` to the API app automatically. If you
deploy manually, include it:

```bash
cd backend
fly deploy --config fly.toml \
  --app open-wearables-api \
  --env SVIX_SERVER_URL=http://open-wearables-svix.flycast:8071
cd ..
```

## 5. Backend App

Deploy the API, worker, and beat process groups:

```bash
bun run deploy api
```

The helper sets non-secret runtime values during deploy:

- `API_BASE_URL`
- `REDIS_HOST`
- `SVIX_SERVER_URL`
- `CORS_ORIGINS`

For a custom domain, set `FLY_API_URL` before deploying:

```bash
export FLY_API_URL=https://api.example.com
bun run deploy api
```

## 6. Flower

Flower reuses the latest backend image. It needs the same database and auth
secrets as the backend because it imports the app settings:

```bash
fly secrets set -a open-wearables-flower \
  DB_HOST=<postgres-host> DB_PORT=5432 DB_NAME=open-wearables \
  DB_USER=<postgres-user> DB_PASSWORD=<postgres-password> \
  SECRET_KEY=<same-as-backend>
bun run deploy flower
```

If `FLOWER_BASIC_AUTH` is missing, `deploy.ts` generates one as `admin:<password>`
and prints it once. Set your own value if you need deterministic credentials:

```bash
fly secrets set -a open-wearables-flower \
  FLOWER_BASIC_AUTH="admin:$(openssl rand -hex 16)"
```

## 7. Frontend

Deploy the frontend:

```bash
bun run deploy frontend
```

The frontend reads `VITE_API_URL` at runtime in the Nitro server, so you do not
need to rebuild the image to point it at a different API. For a custom API:

```bash
export FLY_API_URL=https://api.example.com
bun run deploy frontend
```

If you use a custom frontend domain, add it to CORS:

```bash
export FLY_FRONTEND_URL=https://app.example.com
bun run deploy api
```

## 8. Deploy Everything

After Postgres and required secrets are ready:

```bash
bun run deploy all
```

The helper deploys components in dependency order:

1. Redis
2. API
3. Flower
4. Frontend
5. Svix

If you prefer Svix before API, deploy it separately after setting its secrets:

```bash
bun run deploy redis svix api flower frontend
```

## Notes

- Keep Postgres, Redis, API, Flower, Svix, and frontend in the same region.
- `auto_stop_machines` is disabled because worker, beat, webhooks, and Flower
  should not depend on inbound HTTP traffic to wake up.
- `scripts/start/app.sh` runs migrations and seed tasks on every web boot. This
  is acceptable for one web machine. If you scale the `web` process above one
  machine, move migrations into a Fly release command to avoid concurrent
  migration attempts.
- The default Redis app is intentionally private. Do not add public services or
  public IPs to `deploy/fly/redis.toml`.
