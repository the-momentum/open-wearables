module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo '🚀 Starting Open Wearables...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local up -d"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '⏳ Waiting for services to be ready (15 seconds)...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "sleep 15"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🌱 Initializing database with sample data...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local exec -T app uv run python scripts/init/main.py 2>/dev/null || echo 'ℹ️  Database already initialized or still starting'"
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
        message: "echo '✅ Open Wearables is running!'"
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
        message: "echo '📱 Dashboard: http://localhost:3001'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '📚 API Docs:  http://localhost:8001/docs'"
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
        message: "echo '👤 Default login: admin@admin.com / secret123'"
      }
    }
  ]
};
