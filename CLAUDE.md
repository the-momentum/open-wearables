# CLAUDE.md — wearables.bazard.run

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

---

## Place dans l'écosystème Bazard.run

```
app.bazard.run (Vercel)         api.bazard.run (Coolify, Go)        wearables.bazard.run (Coolify, OW Python)
┌──────────────────┐            ┌──────────────────────────┐         ┌──────────────────────────────┐
│ Next.js + AlignUI│  REST/JWT  │  Go hexagonal            │ webhook │  FastAPI + Celery + Postgres │
│ TanStack Query   │ ─────────► │  - adapter/openwearables │ ◄────── │  + Redis + Svix + Flower     │
└──────────────────┘            │  - webhook receiver      │ REST    │                              │
                                │  - tables activities,    │ ──────► │  Providers : Garmin, Strava, │
                                │    biometric_entries,    │         │  Oura, Whoop, Fitbit, Polar, │
                                │    wearable_connections  │         │  Suunto, Ultrahuman,         │
                                └──────────────────────────┘         │  Apple Health, GHC           │
                                                                     └──────────────────────────────┘
                                                                                 │
                                                                                 ▼
                                                                        Wearable providers (OAuth)
```

- `wearables.bazard.run` est **invisible** pour les athlètes/coachs. Seul `api.bazard.run` lui parle (REST + webhook signé).
- L'OAuth provider (athlete connecte son Garmin) est initié depuis `app.bazard.run`, callbacké via `wearables.bazard.run`, et la confirmation est webhookée vers `api.bazard.run`.
- **Aucune donnée wearable** n'est lue par le frontend directement — toujours via `api.bazard.run`.

Voir : `app.bazard.run/CLAUDE.md` et `api.bazard.run/CLAUDE.md` pour la perspective côté consommateurs.

---

## Patches Bazard locaux

| Fichier | Modif | Pourquoi |
|---|---|---|
| `docker-compose.prod.yml` | Retiré `ports:` sur `db`, `redis`, `flower` | Sur Coolify avec IP publique, exposer Postgres/Redis/Flower = trou de sécurité critique. Communication via le réseau Docker interne uniquement. |

Tout autre fichier reste **identique à l'upstream**. Si un patch est ajouté ici, **inscrire la ligne dans ce tableau** pour que la sync upstream reste prévisible.

---

## Déploiement

| Cible | Plateforme | Domaine | Build |
|---|---|---|---|
| Production | Coolify (même serveur que `api.bazard.run`) | `wearables.bazard.run` | Docker Compose, fichier `docker-compose.prod.yml`, depuis cette branche `main` du fork |

Service exposé publiquement par Coolify : **`app` uniquement (port 8000)**. Tous les autres services (`db`, `redis`, `celery-worker`, `celery-beat`, `flower`, `svix-server`, `frontend`) restent sur le réseau Docker interne.

Le service `frontend` (admin UI OpenWearables) peut être routé en interne pour debug, mais pas exposé publiquement par défaut.

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
