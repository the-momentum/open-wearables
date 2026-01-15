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
        message: "docker --version"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '📁 Setting up environment files...'"
      }
    },
    {
      method: "fs.copy",
      params: {
        src: "backend/config/.env.local.template",
        dest: "backend/config/.env"
      }
    },
    {
      method: "fs.copy",
      params: {
        src: "frontend/.env.local.template",
        dest: "frontend/.env"
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

