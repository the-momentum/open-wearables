# Tests package for Open Wearables backend
import os

# Runs before conftest imports the app. Tests use code defaults plus the variables below,
# never a developer's config/.env, so results match CI regardless of local setup.
os.environ["OW_IGNORE_ENV_FILE"] = "1"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("MASTER_KEY", "dGVzdC1tYXN0ZXIta2V5LWZvci10ZXN0aW5nLW9ubHk=")  # base64 test key
os.environ["LOG_FORMAT"] = "legacy"
os.environ["LOG_LEVEL"] = ""
os.environ["OTEL_ENABLED"] = "false"
