# Open Wearables

Open-source platform that unifies wearable device data from multiple providers and enables AI-powered health insights through natural language automations. Build health applications faster with a single API, embeddable widgets, and intelligent webhook notifications.

## What It Does

Open Wearables provides a unified API and developer portal to connect and sync data from multiple wearable devices and fitness platforms. Instead of implementing separate integrations for Garmin, Fitbit, Oura, Whoop, Strava, and Apple Health, you can use a single platform to access normalized health data and build intelligent health insights through AI-powered automations.

**Vision**: Health Insights automations unlock the potential of user data and allow you to drive businesses in a completely new way. By defining conditions in natural language, developers can create intelligent notifications and insights that respond to user health patterns, enabling new types of health applications and services.

> [!IMPORTANT]
> **For Individuals**: This platform can also be used by individuals who want to interact with their own wearable data. Connect your devices, use the AI Health Assistant to chat with your health data, and set up personal health insights automations - all while keeping your data on your own infrastructure.

## Why Use It

**For Developers Building Health Apps:**
- 🔌 Integrate multiple wearable providers through one API instead of maintaining separate implementations
- 📊 Access normalized health data across different devices (heart rate, sleep, activity, steps, etc.)
- 🤖 Build AI-powered health insights and automations using natural language
- 🏠 Self-hosted solution - deploy on your own infrastructure with full data control
- 🚀 No third-party dependencies for core functionality - run it locally with `docker compose up`
- 🧩 Embeddable widgets for easy integration into your applications

**The Problem It Solves:**

Building a health app that supports multiple wearables typically requires:
- ⏱️ Weeks of development per provider integration
- 🔐 Managing different OAuth flows and APIs for each service
- 📦 Handling various data formats and units
- 🔧 Maintaining multiple SDKs and dealing with API changes

Open Wearables handles this complexity so you can focus on building your product.

## Use Cases

- 👤 **Personal Use**: Individuals can self-host the platform to connect their own wearables, chat with their health data using the AI Health Assistant, and set up personal health insights - all with complete data privacy and control
- 🏃 **Fitness Coaching Apps**: Connect user wearables to provide personalized training recommendations. Running coaches can create users, share connection links via WhatsApp, and test AI insights capabilities
- 🏥 **Healthcare Platforms**: Aggregate patient health data from various devices and set up automations for health alerts
- 💪 **Wellness Applications**: Track and analyze user activity across different wearables with AI-powered insights
- 🔬 **Research Projects**: Collect standardized health data from multiple sources
- 🧪 **Product Pilots**: Non-technical product owners can test platform functionality by sharing connection links with users without needing their own app

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

# Create migration
docker compose exec app uv run alembic revision --autogenerate -m "Description"

# Run migrations
docker compose exec app uv run alembic upgrade head
```

### Local Development

```bash
# Install dependencies
uv sync

# Start PostgreSQL locally

# Create migration
uv run alembic revision --autogenerate -m "Description"

# Run migrations
uv run alembic upgrade head

# Start development server
uv run fastapi run app/main.py --reload
```

### Access the application
- 🌐 API: http://localhost:8000
- 📚 Swagger: http://localhost:8000/docs

Default credentials are provided in the `.env.example` file.

## Core Features

### Developer Portal Dashboard
Web-based dashboard for managing your integration:
- 📈 **General Statistics**: View number of users, API calls, and data points at a glance
- 💡 **Health Insights**: Manage AI-powered automations that unlock the potential of user data
- 👥 **User Management**: Add users via the portal or through the API
- 📋 **User Details**: View connected data sources, integration status, and user metrics with visualizations
- 🔑 **API Key Management**: Generate and manage credentials in the Credentials tab
- ⚡ **Quick Start Guide**: Copy-paste widget integration code directly from the portal

### Health Insights & Automations
The platform's most powerful feature - define intelligent health insights using natural language:
- 💬 **Natural Language Conditions**: Describe when notifications should be triggered in plain English
- 🔔 **Webhook Notifications**: Configure your backend endpoint to receive real-time health insights
- 🧪 **Test Automation**: Run dry runs on historical data to see how automations work in practice
- 👤 **Human-in-the-Loop**: Mark incorrect AI interpretations during testing to continuously improve the system
- ✨ **Improve Description**: AI-powered suggestions to refine your automation descriptions
- 📜 **Automation Logs**: Review past automation triggers and provide feedback

### AI Health Assistant
- 💬 Interactive chat interface for debugging and exploring user data
- 🧩 Embeddable widget that can be integrated into any app with just a few lines of code
- 🔄 Customizable AI models (swap models to match your needs)
- 🔍 Natural language queries about user health metrics

### Unified API
Access health data through a consistent REST API regardless of the source device:

```http
GET /v1/users/{userId}/heart-rate
GET /v1/users/{userId}/sleep
GET /v1/users/{userId}/activity
GET /v1/users/{userId}/steps
```

### Provider Support
- ☁️ **Cloud-based**: Garmin, Fitbit, Oura, Whoop, Strava
- 📱 **Device-based**: Apple Health (via XML export and webhooks)

### Data Ingestion
Two ways to connect user data:
1. 🧩 **SDK Widget**: Embed a dedicated widget in your app through the SDK
2. 🔗 **Shareable Link**: Share a connection link with users (perfect for non-technical testing and pilot programs)

### OAuth Flow Management
Simplified connection process for end users:
1. 🔗 Generate a connection link for your user (or use the SDK widget)
2. 🔐 User authenticates with their wearable provider
3. 🔄 Data automatically syncs to your platform
4. 🚀 Access via unified API or set up automations

## Architecture

Built with:
- 🐍 **Backend**: FastAPI (Python)
- 🗄️ **Database**: PostgreSQL
- 🔐 **Authentication**: Self-contained (no external auth services required)
- 📡 **API Style**: RESTful with OpenAPI/Swagger documentation

The platform is designed for self-hosting, meaning each deployment serves a single organization. No multi-tenancy complexity.

## SDK & Widgets

### Embeddable Widgets
The platform provides embeddable widgets that can be integrated into any app with just a few lines of code:
- 🔌 **Connection Widget**: Allow users to connect their wearables directly from your app
- 🤖 **AI Health Assistant Widget**: Embed the AI chat interface for user health queries

Quick start code is available directly in the Developer Portal's Credentials tab.

### Mobile SDK (Coming Soon)

Flutter SDK for embedding wearable connections directly in mobile apps:

```dart
import 'package:open_wearables/open_wearables.dart';

final openWearables = OpenWearables(apiKey: 'your_api_key');

// Show connection widget
await openWearables.connectWearable(
  userId: 'user123',
  provider: WearableProvider.garmin,
);
```

## Data Types Supported

- ❤️ Heart rate (BPM)
- 😴 Sleep (stages, duration, quality)
- 🏃 Activity (workouts, exercises)
- 👣 Steps and distance
- 🔥 Calories burned
- 📈 Heart rate variability (HRV)
- 🫁 Blood oxygen (SpO2)
- ⚖️ Body metrics (weight, BMI)
- 📍 GPS/location data
- 🍎 Nutrition data (where available)

## Configuration

Provider credentials are configured through environment variables:

```bash
# .env file
GARMIN_CLIENT_ID=your_client_id
GARMIN_CLIENT_SECRET=your_client_secret
FITBIT_CLIENT_ID=your_client_id
FITBIT_CLIENT_SECRET=your_client_secret
# ... etc
```

You'll need to register as a developer with each provider you want to support. The documentation includes guides for this process.

## Development Roadmap

**Current Status**:
- ✅ Backend API with authentication (fully functional)
- ✅ OAuth flow management

**In Development**:
- Core health data endpoints
- Support for major cloud providers
- Health Insights automations (backend implementation)
- AI Health Assistant (backend implementation)
- Developer portal frontend implementation
- Mobile SDK (Flutter)
- Enhanced widget integration
- Time-series database optimization (TimescaleDB)

**Planned**:
- 📤 Advanced data export features
- 📚 Enhanced documentation site
- 📝 API request logging
- 🎨 Prompt-based view regeneration for user metrics

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
