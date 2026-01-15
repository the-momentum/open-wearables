module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo '⚠️  This will delete all data and reset the database!'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo 'Stopping services...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local down -v"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🗑️  Removing Docker volumes...'"
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
        message: "echo '✅ Database reset complete. Click Start to reinitialize.'"
      }
    }
  ]
};

