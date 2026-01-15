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
        message: "echo '⏳ Waiting for services to be ready...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "sleep 10"
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
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local exec -T app uv run python scripts/init/main.py || echo 'Database already initialized'"
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
        message: "echo '📱 Dashboard: http://localhost:3000'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '📚 API Docs:  http://localhost:8000/docs'"
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

