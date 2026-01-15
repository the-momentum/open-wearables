module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo '📋 Open Wearables Logs (last 50 lines per service)'"
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
        message: "echo '═══════════════════════════════════════════════════════════════'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🔧 BACKEND LOGS:'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker logs owlocal-backend --tail 50 2>&1 || echo 'Backend not running'"
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
        message: "echo '═══════════════════════════════════════════════════════════════'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🎨 FRONTEND LOGS:'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker logs owlocal-frontend --tail 30 2>&1 || echo 'Frontend not running'"
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
        message: "echo '═══════════════════════════════════════════════════════════════'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '⚙️  WORKER LOGS:'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker logs owlocal-worker --tail 20 2>&1 || echo 'Worker not running'"
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
        message: "echo '═══════════════════════════════════════════════════════════════'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '📊 CONTAINER STATUS:'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker ps -a --filter 'name=owlocal' --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'"
      }
    }
  ]
};

