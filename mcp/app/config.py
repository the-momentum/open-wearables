"""Configuration settings for Open Wearables MCP server."""

import sys
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the absolute path to the .env file
# This ensures it works regardless of the current working directory
_ENV_FILE = (Path(__file__).parent.parent / "config" / ".env").resolve()


class Settings(BaseSettings):
    """MCP server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required settings
    open_wearables_api_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for Open Wearables backend API",
    )
    open_wearables_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="API key for authenticating with Open Wearables backend",
    )

    # Optional settings
    log_level: str = Field(default="INFO", description="Logging level")
    request_timeout: int = Field(default=30, description="HTTP request timeout in seconds")

    def is_configured(self) -> bool:
        """Check if the API key is configured."""
        return bool(self.open_wearables_api_key.get_secret_value())


try:
    settings = Settings()
    if not settings.is_configured():
        print(
            f"Warning: OPEN_WEARABLES_API_KEY not set. Expected .env file at: {_ENV_FILE}",
            file=sys.stderr,
        )
except ValidationError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    settings = Settings(open_wearables_api_key=SecretStr(""))
