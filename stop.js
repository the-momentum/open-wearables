module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo '🛑 Stopping Open Wearables...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local down"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '✅ Open Wearables stopped.'"
      }
    }
  ]
};

