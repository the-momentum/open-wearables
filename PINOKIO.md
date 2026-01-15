# 🏃 Open Wearables - Pinokio Installation Guide

Open Wearables is a personal health data aggregation platform that lets you collect and analyze data from various wearable devices in your own local database.

## Prerequisites

1. **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop/)
2. **Pinokio** - [Download here](https://pinokio.computer/)

## Installation Steps

### Step 1: Install Docker Desktop

1. Download Docker Desktop for your OS (Mac/Windows/Linux)
2. Install and launch Docker Desktop
3. Make sure Docker is running (you should see the Docker whale icon in your system tray/menu bar)

### Step 2: Install via Pinokio

1. Open Pinokio
2. Click **"Discover"** or **"+"** to add a new app
3. Paste the repository URL:
   - **Main branch:** `https://github.com/YOUR_USERNAME/OpenWearables`
   - **Specific branch:** `https://github.com/YOUR_USERNAME/OpenWearables#branch-name`
   - **Test a PR:** Use the source branch URL, e.g. `https://github.com/USER/OpenWearables#feature/pinokio`
4. Click **"Download"**
5. Once downloaded, click **"Install"**
6. Wait for the installation to complete (this may take 5-10 minutes on first run)

### Step 3: Start Open Wearables

1. In Pinokio, find **"Open Wearables Local"**
2. Click **"Start"**
3. Wait for all services to initialize
4. Click **"Open Dashboard"** to access the web interface

## Default Login

- **Email:** `admin@admin.com`
- **Password:** `secret123`

## Available Features

### ✅ Works Out of the Box
- **Apple Health** - Sync your health data via the iOS companion app (no API keys needed!)
- Full data visualization dashboard
- Local PostgreSQL database for your data
- REST API for custom integrations

### 🔐 Requires API Keys (Business/Partnership Accounts)
These providers require developer API access that is typically only granted to businesses:
- Garmin Health API
- Suunto API
- Polar AccessLink API
- Whoop API

> **For personal use, Apple Health covers most fitness data including:**
> - Heart rate
> - Steps & distance
> - Workouts & exercises
> - Sleep tracking
> - And much more!

## Pinokio Menu Options

| Button | Description |
|--------|-------------|
| **Install** | Set up Docker images and configuration |
| **Start** | Launch all Open Wearables services |
| **Stop** | Shut down all services |
| **Open Dashboard** | Open the web interface (localhost:3000) |
| **Open API Docs** | View API documentation (localhost:8000/docs) |
| **Configure Providers** | Information about adding provider API keys |
| **Reset Database** | Delete all data and start fresh |

## Ports Used

Pinokio version uses different ports to avoid conflicts with the development setup:

| Service | Pinokio Port | Dev Port | URL |
|---------|--------------|----------|-----|
| Frontend Dashboard | 3001 | 3000 | http://localhost:3001 |
| Backend API | 8001 | 8000 | http://localhost:8001 |
| API Documentation | 8001 | 8000 | http://localhost:8001/docs |
| PostgreSQL | 5433 | 5432 | (internal) |
| Redis | 6380 | 6379 | (internal) |

## Troubleshooting

### "Docker is not running"
Make sure Docker Desktop is started and running before using Open Wearables.

### "Port already in use"
If you see port conflicts, make sure no other services are using ports 3001, 8001, 5433, or 6380.

Note: Pinokio uses different ports than the development setup, so both can run simultaneously.

### "Installation failed"
1. Make sure you have at least 4GB of free disk space
2. Check that Docker Desktop has sufficient resources allocated
3. Try running **Reset Database** and then **Install** again

### Slow first start
The first start takes longer as it needs to:
- Build Docker images
- Download dependencies
- Initialize the database
- Seed sample data

Subsequent starts will be much faster.

## Advanced: Adding Provider API Keys

If you have access to provider APIs (Garmin, Suunto, Polar, Whoop):

1. Stop Open Wearables
2. Edit `backend/config/.env.local`
3. Add your CLIENT_ID and CLIENT_SECRET for each provider
4. Start Open Wearables again

## Uninstalling

### From Pinokio:
1. Click **Stop** to shut down the services
2. Right-click on "Open Wearables Local" → **Delete** or **Remove**

### Complete cleanup (removes all data):
```bash
# Stop and remove containers
docker compose -f docker-compose.local.yml -p open-wearables-local down -v

# Remove Docker volumes
docker volume rm open-wearables-local_owlocal_postgres_data open-wearables-local_owlocal_redis_data

# Remove Docker images
docker rmi open-wearables-local:latest open-wearables-frontend-local:dev
```

## Data Location

Your data is stored in Docker volumes:
- **Database:** `open-wearables-local_owlocal_postgres_data`
- **Cache:** `open-wearables-local_owlocal_redis_data`

To backup your data, you can use Docker volume backup tools or export via the API.

## Testing Pull Requests

To test a PR before merging:

1. Find the **source branch name** from the PR (shown at the top of the PR page)
2. In Pinokio, use URL format: `https://github.com/REPO_OWNER/OpenWearables#branch-name`
3. If the PR is from a fork: `https://github.com/PR_AUTHOR/OpenWearables#branch-name`

Example: For PR from branch `feature/pinokio-setup`:
```
https://github.com/openwearables/OpenWearables#feature/pinokio-setup
```

## Support

- 📖 [Full Documentation](https://docs.openwearables.dev)
- 🐛 [Report Issues](https://github.com/YOUR_USERNAME/OpenWearables/issues)
- 💬 [Community Discussions](https://github.com/YOUR_USERNAME/OpenWearables/discussions)

