
# Open Wearables

<div align="left">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-blue.svg)](https://github.com/the-momentum/open-wearables/issues)
![Built with: FastAPI + React + Tanstack](https://img.shields.io/badge/Built%20with-FastAPI%20%2B%20React%20%2B%20Tanstack-green.svg)
[![Discord](https://img.shields.io/badge/Discord-Join%20Chat-5865F2?logo=discord&logoColor=white)](https://discord.gg/qrcfFnNE6H)

</div>

Open-source platform that unifies wearable device data from multiple providers and enables AI-powered health insights through natural language automations. Build health applications faster with a single API, embeddable widgets, and intelligent webhook notifications.

## What It Does

Open Wearables provides a unified API and developer portal to connect and sync data from multiple wearable devices and fitness platforms. Instead of implementing separate integrations for Garmin, Fitbit, Oura, Whoop, Strava, and Apple Health, you can use a single platform to access normalized health data and build intelligent health insights through AI-powered automations.

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
- Significant development effort per provider (Garmin, Fitbit, Oura, etc.) to implement OAuth flows, data mapping, and sync logic
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

## Setup

1. **Create environment file**
   ```bash
   cp ./config/.env.example ./config/.env
   # Edit .env file with your configuration
   ```

## Running the Application

### Docker (Recommended)

```bash
# Start services
docker compose up -d
```

### Seed sample data (optional)

```bash
make init
```

This script seeds sample data. The admin account allows you to immediately access the developer portal without needing to register first.

**Default Admin Credentials:**
- Email: `admin@admin.com`
- Password: `secret123`

### Access the application
- 🌐 API: http://localhost:8000
- 📚 Swagger: http://localhost:8000/docs

Default credentials are provided in the `.env.example` file.

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
- ☁️ **Cloud-based**: Garmin, Suunto, Polar (more comming soon!)
- 📱 **SDK-based**: Apple Health (via XML export and webhooks)

### OAuth Flow Management
Simplified connection process for end users:
1. Generate a connection link for your user (or use the SDK widget)
2. User authenticates with their wearable provider
3. Data automatically syncs to your platform
4. Access via unified API

## Architecture

Built with:
- 🐍 **Backend**: FastAPI (Python)
- 🗄️ **Database**: PostgreSQL
- 🔐 **Authentication**: Self-contained (no external auth services required)
- 📡 **API Style**: RESTful with OpenAPI/Swagger documentation

The platform is designed for self-hosting, meaning each deployment serves a single organization. No multi-tenancy complexity.

## SDK & Widgets (coming soon)

- 🔌 **Connection Widget**: Allow users to connect their wearables directly from your app
- 🤖 **AI Health Assistant Widget**: Embed the AI chat interface for user health queries
- 🍏 **Flutter SDK**: Handles HealthKit permissions, background sync, and data normalization

## Development Roadmap

**✅ Available**:
- Developer portal
- User management (via API and developer portal)
- OAuth flow for Garmin, Polar, and Suunto
- Workout data sync and API access for Garmin, Polar, and Suunto

**In Development**:
- Core health data endpoints
- Health Insights automations
- AI Health Assistant
- Mobile SDK (Flutter)
- Enhanced widget integration

**Planned**:
- 📤 Advanced data export features
- 📚 Enhanced documentation site
- 📝 API request logging
- 🎨 Prompt-based view regeneration for user metrics

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

This project was generated from the [Python AI Kit](https://github.com/the-momentum/python-ai-kit).
