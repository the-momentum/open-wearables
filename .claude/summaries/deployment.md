# Deployment Guide - Open Wearables (EKYGAI)

**Responsabilité** : Déploiement production sur VPS OVH Ubuntu 25.04

**Infrastructure** :
- VPS: 54.37.38.141
- Frontend: openwearables.ekygai.com
- API: api-openwearables.ekygai.com
- Stack: TanStack Start (Nitro SSR) + FastAPI + PostgreSQL + Redis

---

## Quick Start

```bash
# Sur le VPS
cd /opt/open-wearables
git pull origin ekygai-production
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Architecture de déploiement

```
                    Cloudflare (DNS + CDN)
                            │
                            ▼
    ┌─────────────────────────────────────────┐
    │              Nginx (Reverse Proxy)       │
    │  :443 SSL ─────────────────────────────  │
    └─────────┬─────────────────────┬─────────┘
              │                     │
              ▼                     ▼
    ┌─────────────────┐   ┌─────────────────┐
    │ Frontend :3000  │   │ Backend :8000   │
    │ (Nitro SSR)     │   │ (FastAPI)       │
    └─────────────────┘   └────────┬────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
    │ PostgreSQL :5432│   │  Redis :6379    │   │ Celery Workers  │
    └─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## Problème Nitro/SSR - Résolu

### Symptôme
- Frontend démarre : logs montrent "Listening on: http://localhost:3000/"
- Connexions refusées : `curl http://localhost:3000` → "Connection reset by peer"

### Cause
Nitro 3.x écoute sur `127.0.0.1` par défaut dans le container Docker, inaccessible depuis l'extérieur.

### Solution
Variables d'environnement obligatoires pour Nitro :
```yaml
environment:
  - NITRO_HOST=0.0.0.0
  - NITRO_PORT=3000
  - HOST=0.0.0.0
  - PORT=3000
```

**Important** : Utiliser `docker-compose.prod.yml` et non `docker-compose.yml` (qui est pour le dev).

---

## Installation complète

### 1. Prérequis VPS

```bash
# Update système
apt update && apt upgrade -y

# Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# Nginx
apt install nginx certbot python3-certbot-nginx -y
```

### 2. Cloner le repo

```bash
mkdir -p /opt/open-wearables
cd /opt/open-wearables
git clone https://github.com/EKYGAI/open-wearables.git .
git checkout ekygai-production
```

### 3. Configuration environnement

```bash
# Backend
cp backend/config/.env.example backend/config/.env
nano backend/config/.env
```

Variables critiques :
```env
# Base
SECRET_KEY=<generate-secure-key>
ALLOWED_HOSTS=api-openwearables.ekygai.com

# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=open-wearables
DB_USER=open-wearables
DB_PASSWORD=<secure-password>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# OAuth (Garmin, Polar, etc.)
GARMIN_CONSUMER_KEY=xxx
GARMIN_CONSUMER_SECRET=xxx
```

### 4. Configuration Nginx

```bash
# Copier la config
cp nginx/openwearables.conf /etc/nginx/sites-available/

# Activer
ln -s /etc/nginx/sites-available/openwearables.conf /etc/nginx/sites-enabled/

# Certificats SSL
certbot --nginx -d openwearables.ekygai.com -d api-openwearables.ekygai.com

# Tester et recharger
nginx -t && systemctl reload nginx
```

### 5. Lancer les containers

```bash
# Build et start
docker compose -f docker-compose.prod.yml up -d --build

# Vérifier les logs
docker compose -f docker-compose.prod.yml logs -f frontend

# Vérifier le binding Nitro
docker exec frontend__open-wearables wget -qO- http://localhost:3000/ | head -20
```

---

## Tests de validation

### Test 1: Container health

```bash
docker compose -f docker-compose.prod.yml ps
# Tous les services doivent être "healthy" ou "running"
```

### Test 2: Backend API

```bash
curl -I https://api-openwearables.ekygai.com/docs
# Doit retourner 200 OK
```

### Test 3: Frontend SSR

```bash
curl -I https://openwearables.ekygai.com
# Doit retourner 200 OK avec HTML
```

### Test 4: Depuis l'intérieur du container

```bash
# Ce test confirme que Nitro écoute sur 0.0.0.0
docker exec frontend__open-wearables sh -c "wget -qO- http://0.0.0.0:3000/ | head -5"
```

---

## Troubleshooting

### "Connection reset by peer"

**Cause** : Nitro écoute sur 127.0.0.1 au lieu de 0.0.0.0

**Solution** :
```bash
# Vérifier les variables d'environnement
docker exec frontend__open-wearables env | grep -E "HOST|PORT|NITRO"

# Doit afficher:
# NITRO_HOST=0.0.0.0
# NITRO_PORT=3000
# HOST=0.0.0.0
# PORT=3000
```

### "502 Bad Gateway" Nginx

**Causes possibles** :
1. Container frontend non démarré
2. Mauvais upstream dans Nginx
3. Port non exposé

**Debug** :
```bash
# Vérifier que le container répond
curl -v http://127.0.0.1:3000

# Vérifier les logs Nginx
tail -f /var/log/nginx/error.log
```

### Build échoue

```bash
# Nettoyer et rebuild
docker compose -f docker-compose.prod.yml down -v
docker system prune -af
docker compose -f docker-compose.prod.yml up -d --build --force-recreate
```

---

## Monitoring

### Logs en temps réel

```bash
# Tous les services
docker compose -f docker-compose.prod.yml logs -f

# Frontend uniquement
docker compose -f docker-compose.prod.yml logs -f frontend

# Backend uniquement
docker compose -f docker-compose.prod.yml logs -f app
```

### Health checks

```bash
# Script de monitoring basique
#!/bin/bash
curl -sf https://openwearables.ekygai.com > /dev/null && echo "Frontend: OK" || echo "Frontend: FAIL"
curl -sf https://api-openwearables.ekygai.com/health > /dev/null && echo "Backend: OK" || echo "Backend: FAIL"
```

---

## Mise à jour

```bash
cd /opt/open-wearables
git pull origin ekygai-production
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Fichiers clés

| Fichier | Usage |
|---------|-------|
| `docker-compose.prod.yml` | Config Docker production |
| `frontend/Dockerfile` | Build Nitro SSR |
| `nginx/openwearables.conf` | Reverse proxy config |
| `backend/config/.env` | Variables backend |

---

## Historique des problèmes résolus

| Date | Problème | Solution |
|------|----------|----------|
| 2026-02 | Nitro ne répond pas | Ajout NITRO_HOST=0.0.0.0 |
