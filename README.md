
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

   An admin account is automatically created on startup using the `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables (defaults: `admin@admin.com` / `your-secure-password`).

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
- ☁️ **Cloud-based**: Garmin, Suunto, Polar (more coming soon!)
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
