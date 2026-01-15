module.exports = {
  run: [
    {
      method: "shell.run",
      params: {
        message: "echo ''"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '⚙️  Provider Configuration'"
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
        message: "echo ''"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '✅ AVAILABLE WITHOUT API KEYS:'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   • Apple Health - Sync via iOS app (no API key needed)'"
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
        message: "echo '🔐 REQUIRE DEVELOPER API ACCESS (Business accounts only):'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   • Garmin  - Requires Garmin Health API partnership'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   • Suunto  - Requires Suunto API partnership'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   • Polar   - Requires Polar AccessLink API access'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   • Whoop   - Requires Whoop API access'"
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
        message: "echo '📝 To configure providers with API keys:'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   1. Edit: backend/config/.env'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   2. Add your CLIENT_ID and CLIENT_SECRET for each provider'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo '   3. Restart Open Wearables (Stop → Start)'"
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
        message: "echo '💡 For personal use, Apple Health covers most fitness data!'"
      }
    },
    {
      method: "shell.run",
      params: {
        message: "echo ''"
      }
    }
  ]
};

