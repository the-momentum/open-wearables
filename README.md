
# Open Wearables

<div align="left">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-blue.svg)](https://github.com/the-momentum/open-wearables/issues)
![Built with: FastAPI + React + Tanstack](https://img.shields.io/badge/Built%20with-FastAPI%20%2B%20React%20%2B%20Tanstack-green.svg)
[![Discord](https://img.shields.io/badge/Discord-Join%20Chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/qrcfFnNE6H)

<a href="https://www.producthunt.com/products/open-wearables?embed=true&utm_source=badge-featured&utm_medium=badge&utm_campaign=badge-open-wearables-3" target="_blank" rel="noopener noreferrer"><img alt="Open Wearables - Open infrastructure for wearable-powered health products. | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1132023&theme=light&t=1777448243573"></a>

</div>

---

**Documentation**: https://openwearables.io/docs

---

Open-source platform that unifies wearable device data from multiple providers and enables AI-powered health insights through natural language automations. Build health applications faster with a single API, embeddable widgets, and intelligent webhook notifications.

## What It Does

Open Wearables provides a unified API and developer portal to connect and sync data from multiple wearable devices and fitness platforms. Instead of implementing separate integrations for each provider (e.g., Garmin, Whoop, Apple Health), you can use a single platform to access normalized health data and build intelligent health insights through AI-powered automations.

<div align="center">
<img width="597" height="449" alt="image" src="https://github.com/user-attachments/assets/b626405d-99a3-4ff7-b044-442483a3edea" />
</div>

> [!IMPORTANT]
> **For Individuals**: This platform isn't just for developers - individuals can self-host it to take control of their own wearable data. Connect your devices, explore your health metrics through the unified API, and stay tuned for upcoming features like the AI Health Assistant and personal health insights automations. Best of all, your data stays on your own infrastructure, giving you complete privacy and control.

## Why Use It

**For Developers building health apps:**
- 🔌 Integrate multiple wearable providers through one API instead of maintaining separate implementations
- 📊 Access normalized health data across different devices (heart rate, sleep, activity, steps, etc.)
- 🏠 Self-hosted solution - deploy on your own infrastructure with full data control
- 🚀 No third-party dependencies for core functionality - run it locally with `docker compose up`
- 🤖 Build AI-powered health insights and automations using natural language (coming soon)
- 🧩 Embeddable widgets for easy integration into your applications (coming soon)

**The Problem It Solves:**

Building a health app that supports multiple wearables typically requires:
- Significant development effort per provider (Garmin, Whoop, Apple Health, etc.) to implement OAuth flows, data mapping, and sync logic
- Managing different OAuth flows and APIs for each service
- Handling various data formats and units
- Maintaining multiple SDKs and dealing with API changes

Open Wearables handles this complexity so you can focus on building your product 🚀

## Use Cases

- 🏃 **Fitness Coaching Apps**: Connect user wearables to provide personalized training recommendations. Running coaches can create users, share connection links via WhatsApp, and test AI insights capabilities
- 🏥 **Healthcare Platforms**: Aggregate patient health data from various devices and set up automations for health alerts
- 💪 **Wellness Applications**: Track and analyze user activity across different wearables with AI-powered insights
- 🔬 **Research Projects**: Collect standardized health data from multiple sources
- 🧪 **Product Pilots**: Non-technical product owners can test platform functionality by sharing connection links with users without needing their own app
- 👤 **Personal Use**: Individuals can self-host the platform to connect their own wearables, chat with their health data using the AI Health Assistant, and set up personal health insights - all with complete data privacy and control

## Getting Started

Get Open Wearables up and running in minutes.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/the-momentum/open-wearables.git
   cd open-wearables
   ```

2. **Configure environment variables:**
   
   **Backend configuration:**
   ```bash
   cp ./backend/config/.env.example ./backend/config/.env
   ```
   
   **Frontend configuration:**
   ```bash
   cp ./frontend/.env.example ./frontend/.env
   ```

3. **Start the application**
   
   **Using Docker (Recommended):**
   
   The easiest way to get started is with Docker Compose:
   ```bash
   docker compose up -d
   ```
   
   For local development setup without Docker take a look at [docs](https://openwearables.io/docs/quickstart#local-development-setup)

4. **Log in to the developer portal:**

   An admin account is automatically created on startup using the `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables (defaults: `admin@admin.com` / `your-secure-password`). The seed runs only while the developer table is empty: once any developer account exists it is skipped, so changing `ADMIN_PASSWORD` later does not update an existing account - **change the default password from the developer portal right after your first login**. To add further accounts, invite them from the developer portal.

   Open http://localhost:3000 to access the developer portal and create API keys.

5. **Seed sample data** (optional):
   If you want test users and sample activity data:
   ```bash
   make seed
   ```

   This will create:
   - Test users
   - Sample activity data for test users


6. **View API documentation:**

   Open http://localhost:8000/docs in your browser to explore the interactive Swagger UI.

## Core Features

### Developer Portal Dashboard
Web-based dashboard for managing your integration:
- 📈 **General Statistics**: View number of users and data points at a glance
- 👥 **User Management**: Add users via the portal or through the API
- 📋 **User Details**: View connected data sources, integration status, and user metrics with visualizations
- 🔑 **API Key Management**: Generate and manage credentials in the Credentials tab

### Health Insights & Automations (coming soon)
The platform's most powerful feature - define intelligent health insights using natural language:
- 💬 **Natural Language Conditions**: Describe when notifications should be triggered in plain English
- 🔔 **Webhook Notifications**: Configure your backend endpoint to receive real-time health insights
- 🧪 **Test Automation**: Run dry runs on historical data to see how automations work in practice
- 👤 **Human-in-the-Loop**: Mark incorrect AI interpretations during testing to continuously improve the system
- ✨ **Improve Description**: AI-powered suggestions to refine your automation descriptions
- 📜 **Automation Logs**: Review past automation triggers and provide feedback

### AI Health Assistant (coming soon)
- 💬 Interactive chat interface for debugging and exploring user data
- 🧩 Embeddable widget that can be integrated into any app with just a few lines of code
- 🔄 Customizable AI models (swap models to match your needs)
- 🔍 Natural language queries about user health metrics

### Unified API
Access health data through a consistent REST API regardless of the source device.

### Provider Support
- ☁️ **Cloud-based**: Garmin, Oura, Whoop, Suunto, Polar, Ultrahuman, Strava, Fitbit
- 📱 **SDK-based**: Apple HealthKit, Samsung Health, Google Health Connect

### OAuth Flow Management
Simplified connection process for end users:
1. Generate a connection link for your user (or use the SDK widget)
2. User authenticates with their wearable provider
3. Data automatically syncs to your platform
4. Access via unified API

### Mobile Sync SDKs
Native SDKs for push-based health data sync from on-device health stores:
- **[iOS SDK](https://github.com/the-momentum/open_wearables_ios_sdk)** (Swift) - Apple HealthKit
- **[Android SDK](https://github.com/the-momentum/open_wearables_android_sdk)** (Kotlin) - Samsung Health & Google Health Connect
- **[Flutter SDK](https://github.com/the-momentum/open_wearables_health_sdk)** (Dart) - Cross-platform Flutter wrapper around native SDKs
- **[React Native SDK](https://github.com/the-momentum/open-wearables-react-native-sdk)** (TypeScript) - Cross-platform React Native wrapper around native SDKs

### Widgets (coming soon)
- 🔌 **Connection Widget**: Allow users to connect their wearables directly from your app
- 🤖 **AI Health Assistant Widget**: Embed the AI chat interface for user health queries

## Architecture

Built with:
- 🐍 **Backend**: FastAPI (Python)
- ⚛️ **Frontend**: React + TanStack Router + TypeScript (Vite)
- 🗄️ **Database**: PostgreSQL + Redis
- ⚙️ **Task Queue**: Celery (background jobs for data syncing and processing)
- 🔐 **Authentication**: Self-contained (no external auth services required)
- 📡 **API Style**: RESTful with OpenAPI/Swagger documentation

The platform is designed for self-hosting, meaning each deployment serves a single organization. No multi-tenancy complexity.

## Development Roadmap

**Available**:
- Developer portal
- User management (via API and developer portal)
- OAuth flow for Garmin, Polar, and Suunto
- Workout data sync and API access for Garmin, Polar, and Suunto
- Mobile Sync SDKs (iOS, Android, Flutter, React Native)

**In Development**:
- Core health data endpoints
- Health Insights automations
- AI Health Assistant
- Enhanced widget integration

## Join the Discord

Join our Discord community to connect with other developers, get help, share ideas, and stay updated on the latest developments:

[![Discord](https://img.shields.io/badge/Discord-Join%20Chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/qrcfFnNE6H)

## Fork Patches

This repository is a fork of [the-momentum/open-wearables](https://github.com/the-momentum/open-wearables).
Local fixes are tracked under [`ow-patches/`](ow-patches/) so we keep a clean record
of where we diverge from upstream and can A/B compare upstream behavior against ours
without restoring code from git history.

**Layout:**

```
ow-patches/
├── PATCHES.md           # registry — one entry per patch, explains intent + retire condition
├── apply.py             # imports each patch and monkey-patches at import time
├── check_upstream.py    # `python ow-patches/check_upstream.py` — equivalence + drift checks
├── .upstream-baseline   # upstream/main SHA we last reconciled against (drift origin)
└── local/<patch_id>.py  # patched implementation, one file per patch_id
```

`apply.py` is invoked once from [`backend/app/__init__.py`](backend/app/__init__.py),
so every entry point (FastAPI app, Celery worker, migrations, pytest) ends up with
the same patches applied.

**Check whether upstream has caught up — or silently diverged:**

```bash
# one-time setup if not already configured
git remote add upstream https://github.com/the-momentum/open-wearables.git

python ow-patches/check_upstream.py
```

The script fetches `upstream/main` and runs **two independent checks** per patch:

1. **Equivalence (heuristic).** Greps `upstream/main` for the patch's
   `upstream_equivalent_check` marker (path-qualified with `path::pattern`). A hit
   *suggests* upstream shipped its own version. This is a weak signal — the marker
   is a string unique to *our* code, so it only fires when upstream happens to use
   the same token, and is blind to an upstream change that does the same thing
   differently.

2. **Drift (deterministic).** For every file a patch depends on (its `file:` field),
   runs `git log <baseline>..upstream/main -- <file>` to see whether upstream has
   *touched* it since we last reconciled (`.upstream-baseline`). This is the check
   that catches the dangerous blind spot the equivalence grep misses:

   > A monkey-patch that **wholesale-replaces** an upstream method produces **no git
   > merge conflict** (we never edit the upstream source file), so `git merge` is
   > silent. If upstream rewrites that method, our patch keeps shadowing it with a
   > stale copy — silently dropping upstream's improvements. This is exactly how
   > `avg_hrv_rmssd_ms` went null after upstream rewrote `get_sleep_summaries`.

   Drift is escalated by each patch's `replacement_kind` (see PATCHES.md): drift on
   a `wholesale-replace` patch is a **SHADOW RISK** (re-verify/rebase — the script
   exits non-zero); drift on a `decorate` patch is lower-risk (re-verify only). The
   drift check focuses on monkey-patch patches — `structural` source-edit patches
   surface upstream drift as ordinary git conflicts at merge time. The check is
   file-granular: it flags broadly, then you diff upstream's change against the patch
   to confirm whether your *specific* replaced symbol actually moved.

Nothing is auto-retired or auto-rebased — all changes are manual.

**Reconcile-and-merge workflow:**

```bash
python ow-patches/check_upstream.py          # 1. see what upstream touched since baseline
git merge upstream/main                       # 2. merge (resolve dep/lock conflicts, unify alembic heads)
# 3. for every SHADOW RISK / re-verify row: diff upstream's new body vs the patch,
#    then rebase the patch (decorate > wholesale-replace where possible) or retire it
cd backend && uv run pytest -q                # 4. full suite green with patches applied
python ow-patches/check_upstream.py --update-baseline   # 5. record the new reconciled SHA
```

Skipping step 5 is safe (the baseline just stays older and the next run re-flags the
same drift); never run it *before* steps 3–4, or you erase the signal.

**Disable a single patch (A/B test):**

Edit [`ow-patches/apply.py`](ow-patches/apply.py) and flip the relevant entry in
`PATCHES_ENABLED` to `False`. Restart the backend. That patch reverts to upstream
behavior; nothing else moves. Composed patches (e.g. `fix-hrv-nightly-aggregate`,
`fix-sleep-stages-missing`, and `fix-sleep-timezone` all live inside the same
`get_sleep_summaries` replacement) toggle independently — see `compose()` in
`apply.py`.

A small number of changes are **structural** and not toggleable from `apply.py`:
the `User.timezone` column + migration, and the `basal_calories_kcal` /
`timezone` / `start_time_local` / `end_time_local` fields added to response
schemas. Disabling the corresponding patch causes those fields to come back as
`null`, which is upstream-equivalent enough — see `PATCHES.md` for which patches
have a structural component.

**Container deployment.** `docker-compose.yml` bind-mounts `./ow-patches` into
the app, celery-worker, and celery-beat containers at `/root_project/ow-patches`
and exports `OW_PATCHES_DIR=/root_project/ow-patches`. `app/__init__.py` resolves
the patch directory in this order: `$OW_PATCHES_DIR` → sibling of `app/` (container
layout) → repo root (host layout). To pick up patch changes without rebuilding the
image, run `docker compose restart app celery-worker celery-beat` (or `docker compose
watch` for live reloads).

**Retire a patch when upstream covers it:**

1. Verify upstream's implementation matches: same provider scope, same field
   names, same units, nullability equal or stricter than ours.
2. In `ow-patches/PATCHES.md`, change `status:` from `local_only` /
   `upstream_candidate` to `retired`.
3. In `ow-patches/apply.py`, set the patch's `PATCHES_ENABLED` entry to `False`.
4. Keep `ow-patches/local/<patch_id>.py` for reference (don't delete) — it's
   our institutional memory of what we changed and why.
5. Re-run the test suite to confirm upstream covers the cases our patch did.

## Contributing

Contributions are welcome! This project aims to be a community-driven solution for wearable data integration.

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on:
- 🛠️ Setting up the development environment
- 📝 Code style and testing requirements
- 🔀 Pull request process

## License

[MIT License](LICENSE) - Use it freely in commercial and open-source projects.

## Community

- 💬 [GitHub Discussions](https://github.com/the-momentum/open-wearables/discussions) - Questions and ideas

---

**Note**: This is an early-stage project under active development. APIs may change before version 1.0. We recommend pinning to specific versions in production and following the changelog for updates.

---

The backend part of this project was generated from the [Python AI Kit](https://github.com/the-momentum/python-ai-kit).

Built with ❤️ by [Momentum](https://themomentum.ai/)
