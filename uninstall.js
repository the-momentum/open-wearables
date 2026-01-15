module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo '🗑️  Uninstalling Open Wearables Local...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo ''"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '⏹️  Stopping containers...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local down -v 2>/dev/null || true"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🗄️  Removing Docker volumes...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker volume rm open-wearables-local_owlocal_postgres_data open-wearables-local_owlocal_redis_data 2>/dev/null || true"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🐳 Removing Docker images...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker rmi open-wearables-local:latest open-wearables-frontend-local:dev 2>/dev/null || true"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🧹 Cleaning up config files...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "rm -f backend/config/.env.local frontend/.env 2>/dev/null || true"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo ''"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '✅ Uninstall complete!'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo ''"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '💡 To remove this app from Pinokio, right-click → Delete'"
      }
    }
  ]
};

