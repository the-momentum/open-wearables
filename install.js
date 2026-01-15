module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo '🔧 Checking Docker installation...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker --version || (echo '❌ Docker not found! Please install Docker Desktop first.' && exit 1)"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '📁 Setting up environment files...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "cp backend/config/.env.local.template backend/config/.env.local"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🔑 Generating secure secret key...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "node scripts/pinokio/generate-secrets.js"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '🐳 Building Docker images (this may take a few minutes)...'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "docker compose -f docker-compose.local.yml -p open-wearables-local build"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '✅ Installation complete! Click Start to launch Open Wearables.'"
      }
    }
  ]
};
