# Tests package for Open Wearables backend
import os

# Runs before conftest imports the app, so a developer's config/.env cannot change the
# log output the tests parse (environment variables take precedence over the .env file).
os.environ["LOG_FORMAT"] = "legacy"
os.environ["LOG_LEVEL"] = ""
os.environ["OTEL_ENABLED"] = "false"
