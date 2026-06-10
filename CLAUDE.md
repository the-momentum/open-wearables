# CLAUDE.md — ow.bazard.run

> **Fork Bazard.run** de [`the-momentum/open-wearables`](https://github.com/the-momentum/open-wearables) (MIT).
> Sert de **passerelle wearables** pour l'écosystème Bazard.run : agrège Garmin, Strava, Oura, Whoop, Fitbit, Polar, Suunto, Ultrahuman, Apple Health, Google Health Connect derrière une API REST unifiée.

Pour les conventions, l'architecture interne et les commandes du projet upstream OpenWearables, voir **`AGENTS.md`** à la racine. Ce fichier-ci concerne uniquement **les modifications Bazard et l'intégration dans l'écosystème**.

---

## Pourquoi ce fork ?

On a besoin de **patcher localement** des choses qu'on ne peut pas faire upstream :

1. **Sécurité prod** : retirer les ports Postgres/Redis/Flower exposés sur l'host par défaut dans `docker-compose.prod.yml`
2. **Pin de version** : on choisit quand on prend les nouveautés upstream (pas de redeploy automatique sur leurs commits)
3. **Capacité de patcher en urgence** un bug ou un comportement spécifique sans dépendre de leur réactivité

**On ne pousse JAMAIS vers `upstream`.** Le push y est désactivé sur ce repo (`git remote -v` confirme l'URL push factice).

### ⚠️ Règle Claude — `gh pr create` sur ce fork

`gh pr create` sans flag explicite **route vers le repo parent (`the-momentum/open-wearables`)** par défaut quand on est sur un fork. Une PR Bazard créée sans précaution se retrouve publiquement proposée à l'upstream OpenWearables — fuite de doc/conventions internes.

**Toujours forcer le repo cible** :

```bash
gh pr create --repo IDK-JB/ow.bazard.run --base main --head <branche> --title "..." --body "..."
```

Pareil pour toute opération `gh`: `--repo IDK-JB/ow.bazard.run` systématique. Le `git push -u origin <branche>` reste sûr (origin = fork), c'est uniquement `gh pr create` / `gh pr edit` / `gh pr comment` qui dérivent vers l'upstream sans flag.

Incident de référence : PR upstream #1085 ouverte par erreur le 2026-05-28, fermée immédiatement (doc-only, aucun code merge).

---

## Place dans l'écosystème Bazard.run

```
bazard.run (Astro, Coolify)     app.bazard.run (Next.js, Vercel)    api.bazard.run (Coolify, Go)        ow.bazard.run (Coolify, OW Python)
┌──────────────────┐            ┌──────────────────┐                ┌──────────────────────────┐         ┌──────────────────────────────┐
│ Landing statique │   liens    │ Next.js + AlignUI│  REST/JWT      │  Go hexagonal            │ webhook │  FastAPI + Celery + Postgres │
│ Vitrine + dons   │  externes  │ TanStack Query   │ ─────────────► │  - adapter/openwearables │ ◄────── │  + Redis + Svix + Flower     │
│ Patch notes      │   /sign-in │ Auth + App       │                │  - webhook receiver      │ REST    │                              │
└──────────────────┘            └──────────────────┘                │  - tables activities,    │ ──────► │  Providers : Garmin, Strava, │
                                                                    │    biometric_entries,    │         │  Oura, Whoop, Fitbit, Polar, │
                                                                    │    wearable_connections  │         │  Suunto, Ultrahuman,         │
                                                                    └──────────────────────────┘         │  Apple Health, GHC           │
                                                                                                         └──────────────────────────────┘
                                                                                                                     │
                                                                                                                     ▼
                                                                                                            Wearable providers (OAuth)
```

- `bazard.run` est la **landing statique** (Astro, Coolify). Pas de logique
  metier, pas d'appel a l'API. Les CTAs pointent vers `app.bazard.run`.
- `ow.bazard.run` est **invisible** pour les athlètes/coachs. Seul `api.bazard.run` lui parle (REST + webhook signé).
- L'OAuth provider (athlete connecte son Garmin) est initié depuis `app.bazard.run`, callbacké via `ow.bazard.run`, et la confirmation est webhookée vers `api.bazard.run`.
- **Aucune donnée wearable** n'est lue par le frontend directement — toujours via `api.bazard.run`.

Voir : `bazard.run/CLAUDE.md` (landing), `app.bazard.run/CLAUDE.md` et `api.bazard.run/CLAUDE.md` pour la perspective côté consommateurs.

---

## Patches Bazard locaux

| Fichier | Modif | Pourquoi |
|---|---|---|
| `docker-compose.prod.yml` | Retiré `ports:` sur `db`, `redis`, `flower` | Sur Coolify avec IP publique, exposer Postgres/Redis/Flower = trou de sécurité critique. Communication via le réseau Docker interne uniquement. |
| `docker-compose.prod.yml` | Service `db` : `POSTGRES_*` lus depuis `${DB_NAME}` / `${DB_USER}` / `${DB_PASSWORD}` (au lieu de littéraux `open-wearables`) | Permet de mettre un mot de passe fort via les env vars Coolify. `DB_PASSWORD` est désormais **requis** (le compose plante si non défini) — ce qui force la bonne pratique. |
| `docker-compose.prod.yml` | Service `app` : `expose:` au lieu de `ports:` | Évite tout conflit de port sur l'host Coolify (le port 8000 est déjà pris par `api.bazard.run` sur la même machine). Coolify route `ow.bazard.run` vers le container via son proxy interne (Docker network), pas via le port host. |
| `docker-compose.prod.yml` | Service `frontend` : `ports: ["100.86.173.65:3000:3000"]` (IP Tailscale du VPS) | Le frontend OW (admin UI) est exposé **uniquement sur le tailnet**, jamais sur Internet. URL d'accès : `http://frontend-ow.bazard.run:3000` (record DNS A public qui pointe vers l'IP Tailscale → seuls les devices Tailscale peuvent l'atteindre). Coolify ne route pas le frontend, c'est le bind IP-specific qui fait la restriction. |

| `backend/app/api/routes/v1/users.py` | `DELETE /users/{id}` : `DeveloperDep` → `ApiKeyDep` | La Bazard API supprime un user en server-to-server (clé admin, effacement RGPD BAZ-341). `ApiKeyDep` accepte aussi le JWT developer : dashboard inchangé. Test upstream `test_delete_user_requires_bearer_token` adapté en conséquence. |
| `backend/app/services/raw_payload_storage.py` | Ajout `purge_user_payloads(user_id)` | Effacement RGPD : purge les payloads bruts S3/R2 d'un user (scan paginé + delete par batch). Appelé par `user_service.delete`. BAZ-341. |
| `backend/app/services/user_service.py` | `delete()` appelle `purge_user_payloads` (best-effort + Sentry) | Les payloads archivés portent des données de santé : ils doivent disparaître avec le compte. Un échec storage est loggé/capturé mais ne bloque pas la suppression DB. BAZ-341. |

Tout autre fichier reste **identique à l'upstream**. Si un patch est ajouté ici, **inscrire la ligne dans ce tableau** pour que la sync upstream reste prévisible.

---

## Déploiement

| Cible | Service | URL | Accessibilité |
|---|---|---|---|
| Production | `app` (FastAPI) | `https://ow.bazard.run` | Public Internet (Coolify Traefik + Let's Encrypt). Sert l'API REST + Svix + assets `/static`. Webhooks Strava/Garmin et consommation par `api.bazard.run` passent par là. |
| Production | `frontend` (Vite SPA, admin UI) | `http://frontend-ow.bazard.run:3000` | **Tailnet uniquement.** Le DNS A pointe vers l'IP Tailscale du VPS (`100.86.173.65`), seuls les devices Tailscale peuvent router. Pas de HTTPS (chiffrement déjà assuré par WireGuard). |

Tous les autres services (`db`, `redis`, `celery-worker`, `celery-beat`, `flower`, `svix-server`) restent sur le réseau Docker interne, pas exposés à l'host.

Build & déploiement : Docker Compose, fichier `docker-compose.prod.yml`, depuis cette branche `main` du fork.

---

## Sync upstream

```bash
# Récupérer les commits du repo upstream sans rien casser
git fetch upstream
git log HEAD..upstream/main --oneline   # voir ce qui arrive

# Merger quand tu es prêt (sur une branche pour relire le diff avant)
git checkout -b sync/upstream-YYYY-MM-DD
git merge upstream/main
# Résoudre les conflits éventuels (souvent sur docker-compose.prod.yml)
# Vérifier que les patches Bazard sont toujours présents
git push origin sync/upstream-YYYY-MM-DD
# Ouvrir une PR sur le fork, valider en preview Coolify, merger sur main → redeploy
```

⚠️ **Toujours faire la sync via une PR**, jamais directement sur `main` du fork — Coolify suit `main` et redéploiera sans filet.

---

## Variables d'environnement (Coolify)

À définir dans l'UI Coolify (ne pas commit `.env`). Voir `backend/config/.env.example` upstream pour la liste exhaustive. Critiques pour Bazard :

- `SECRET_KEY` / `JWT_SECRET` — random sécurisé
- `DB_*` — credentials Postgres OW (interne au compose)
- Une **API key admin** générée au premier boot, partagée avec `api.bazard.run` (`OPENWEARABLES_API_KEY`)
- Un **secret webhook** partagé avec `api.bazard.run` pour signer les notifications (`OPENWEARABLES_WEBHOOK_SECRET`)
- Pour chaque provider activé : `{PROVIDER}_CLIENT_ID` + `{PROVIDER}_CLIENT_SECRET` (créer les apps OAuth sur les portails dev des providers)

---

## Workflow Bazard

- **Pas de `git add` / `git commit` / `git push` sans demande explicite** (cohérent avec `app.bazard.run` et `api.bazard.run`).
- Linear : workspace `bazardrun`, projet `api.bazard.run` (les tickets wearables y vivent — pas de projet Linear séparé pour le fork).
- Patch notes : tout changement visible côté produit (ex : nouveau provider activé) → entrée dans `app.bazard.run/app/(landing)/patch-notes/_data/entries.ts`.

---

## Quand modifier ce repo ?

**Rarement.** Cas légitimes :

1. Ajouter un patch de sécurité (compose, env)
2. Ajouter une variable d'env Bazard-spécifique
3. Mettre à jour `CLAUDE.md` ou ce fichier
4. Sync upstream via une PR dédiée

**Pour tout le reste** (nouveau provider, nouvel endpoint, custom logic métier) → ça vit dans `api.bazard.run`, pas ici. OW reste vanille autant que possible.

---

## Setup dev local

Pour lancer OW en local et l'intégrer à `api.bazard.run` + `app.bazard.run`, suis [`contributing/bazard-dev-setup.md`](contributing/bazard-dev-setup.md). Inclut le flow complet : copie de `backend/config/.env.example` (upstream natif), génération de la clé OW admin, configuration Svix → API, vérif end-to-end avec Strava sandbox.

## ⚠️ Règle Claude — accès aux fichiers d'env

Claude n'a le droit de **lire ou modifier QUE** `backend/config/.env.local` (gitignored, valeurs dev local). Toute autre lecture/écriture d'un fichier d'env contenant des vraies valeurs est interdite — **même en lecture seule**. Cela inclut `backend/config/.env` (qui contient les credentials provider, Svix secret, etc.).

- ✅ OK : `backend/config/.env.local`, `backend/config/.env.example` (template upstream commité).
- ❌ Off-limits : `backend/config/.env` (secrets de prod / valeurs réelles).

Pour lister les *noms* de vars sans révéler les valeurs : `cut -d= -f1 backend/config/.env`. Pour obtenir une valeur, demander à l'utilisateur.
