
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

> [!TIP]
> **Curious what we're cooking right now?** Take a look at our [roadmap](https://openwearables.io/docs/roadmap) ✨

Open-source platform that unifies wearable device data from multiple providers behind a single API and makes it available to AI. Build health applications faster with normalized health data, webhooks, and mobile SDKs, and connect LLMs and AI agents to your users' wearable data through the built-in MCP server.

## What It Does

Open Wearables provides a unified API and developer portal to connect and sync data from multiple wearable devices and fitness platforms. Instead of implementing separate integrations for each provider (e.g., Garmin, Whoop, Apple Health), you can use a single platform to access normalized health data.

<div align="center">
<img width="597" height="449" alt="image" src="https://github.com/user-attachments/assets/b626405d-99a3-4ff7-b044-442483a3edea" />
</div>

> [!IMPORTANT]
> **For Individuals**: This platform isn't just for developers - individuals can self-host it to take control of their own wearable data, stored on their own infrastructure. Connect your devices, explore your health metrics through the unified API, or chat with your data in Claude or Cursor via the MCP server.

## Why Use It

**For Developers building health apps:**
- 🔌 Integrate multiple wearable providers through one API instead of maintaining separate implementations
- 📊 Access normalized health data across different devices (heart rate, sleep, activity, steps, etc.)
- 🏠 Self-hosted solution - deploy on your own infrastructure with full data control
- 🚀 No third-party dependencies for core functionality - run it locally with `docker compose up`
- 🔔 Get notified via webhooks when new data arrives for your users
- 🤖 Give LLMs and AI agents access to wearable data through the built-in MCP server

**The Problem It Solves:**

Building a health app that supports multiple wearables typically requires:
- Significant development effort per provider (Garmin, Whoop, Apple Health, etc.) to implement OAuth flows, data mapping, and sync logic
- Managing different OAuth flows and APIs for each service
- Handling various data formats and units
- Maintaining multiple SDKs and dealing with API changes

Open Wearables handles this complexity so you can focus on building your product 🚀

## Use Cases

- 🤖 **AI Health Agents & Coaches**: Ground LLM answers in users' real sleep, activity, and workout data instead of generic advice
- 🏃 **Fitness Coaching Apps**: Connect user wearables to provide personalized training recommendations. Running coaches can create users and share connection links via WhatsApp
- 🏥 **Healthcare Platforms**: Aggregate patient health data from various devices and get notified via webhooks when new data arrives
- 💪 **Wellness Applications**: Track and analyze user activity across different wearables
- 🔬 **Research Projects**: Collect standardized health data from multiple sources
- 🧪 **Product Pilots**: Non-technical product owners can test platform functionality by sharing connection links with users without needing their own app
- 👤 **Personal Use**: Individuals can self-host the platform to connect their own wearables, keep the data on their own infrastructure, chat with it through the MCP server, and build any kind of automation on top of webhooks and the API (e.g. with n8n)

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

   > **Production:** `docker compose up` builds from local source and is meant for development. For production, run the official [`themomentum/open-wearables-backend`](https://hub.docker.com/r/themomentum/open-wearables-backend) and [`themomentum/open-wearables-frontend`](https://hub.docker.com/r/themomentum/open-wearables-frontend) images pinned to a stable release tag (e.g. `0.7.0`), not `nightly` or a build of `main`. See [Deploying with Docker](https://openwearables.io/docs/deployment/docker).

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

### Provider Support
- **Cloud-based**: Garmin, Oura, Whoop, Suunto, Polar, Ultrahuman, Strava, Fitbit, Withings, Google Health
- **SDK-based**: Apple Health, Samsung Health, Google Health Connect
- **Apple Health XML import**: Upload a full Apple Health export, including large files via S3 multipart upload

See [supported providers](https://openwearables.io/docs/providers/supported) and [data coverage](https://openwearables.io/docs/providers/coverage) for details.

### AI Integration
Connect LLMs and AI agents to wearable data from any supported provider - Garmin, Oura, Whoop, Apple Health, and more - through one normalized data model.

- **MCP Server**: Built-in [Model Context Protocol](https://modelcontextprotocol.io) server that works with Claude Desktop, Cursor, and other MCP clients
- **Natural language queries**: Ask "How did John sleep last week?" or "Compare workouts of these two users" - the AI fetches the right data itself
- **Available data**: Users, activity summaries, sleep, workouts, time series (heart rate, HRV, SpO2, weight, and more), and menstrual cycles

More AI capabilities are on the way - see the [roadmap](https://openwearables.io/docs/roadmap).

### Unified Data Model & API
One REST API with consistent data regardless of the source device:
- **Daily summaries**: Activity, sleep, body, and recovery
- **Time series**: Heart rate, HRV, SpO2, weight, steps, and [many more data types](https://openwearables.io/docs/architecture/data-types)
- **Events**: Workouts and sleep sessions
- **Data priorities**: Decide which provider and device type wins when data from multiple sources overlaps
- **Multi-account sync**: One provider account can be linked to multiple user profiles

### Connections & Sync
- **OAuth flow management**: Generate a connection link or use the connect widget - users authenticate with their provider and data syncs automatically
- **Historical backfill**: Pull past data on first connection (within each provider's limits)
- **Sync status**: Live sync progress stream (SSE) plus sync run history via the API and the portal

### Webhooks
Register HTTPS endpoints to get notified when new data arrives for your users. Filter by event type or user, verify signatures, send test events, and inspect delivery attempts. See the [webhooks guide](https://openwearables.io/docs/api-reference/guides/webhooks).

### Mobile Sync SDKs
Native SDKs for push-based health data sync from on-device health stores:
- **[iOS SDK](https://github.com/the-momentum/open_wearables_ios_sdk)** (Swift) - Apple HealthKit
- **[Android SDK](https://github.com/the-momentum/open_wearables_android_sdk)** (Kotlin) - Samsung Health & Google Health Connect
- **[Flutter SDK](https://github.com/the-momentum/open_wearables_health_sdk)** (Dart) - Cross-platform Flutter wrapper around native SDKs
- **[React Native SDK](https://github.com/the-momentum/open-wearables-react-native-sdk)** (TypeScript) - Cross-platform React Native wrapper around native SDKs

### Developer Portal
Web-based dashboard for managing your deployment:
- **Dashboard**: Users and data points at a glance
- **Users**: Add users, view connected data sources, and explore their data with visualizations
- **Coverage & Syncs**: See which data types each provider delivers and monitor sync runs
- **Webhooks**: Manage endpoints and debug deliveries
- **Settings**: API keys and provider credentials, data priorities, data lifecycle (archival and retention), team invitations, and a seed data generator

## Architecture

Built with:
- 🐍 **Backend**: FastAPI (Python)
- ⚛️ **Frontend**: React + TanStack Start + TypeScript (Vite)
- 🗄️ **Database**: PostgreSQL + Redis
- ⚙️ **Task Queue**: Celery (background jobs for data syncing and processing)
- 🔐 **Authentication**: Self-contained (no external auth services required)
- 📡 **API Style**: RESTful with OpenAPI/Swagger documentation

The platform is designed for self-hosting, meaning each deployment serves a single organization. No multi-tenancy complexity.

## Join the Discord

Join our Discord community to connect with other developers, get help, share ideas, and stay updated on the latest developments:

[![Discord](https://img.shields.io/badge/Discord-Join%20Chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/qrcfFnNE6H)

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

**Note**: This is an early-stage project under active development. APIs may change before version 1.0. In production, pin the official images to a specific release version (see [Deploying with Docker](https://openwearables.io/docs/deployment/docker)) and follow the changelog for updates.

---

The backend part of this project was generated from the [Python AI Kit](https://github.com/the-momentum/python-ai-kit).

Built with ❤️ by [Momentum](https://themomentum.ai/)
