"""Configuration settings for Open Wearables MCP server."""

import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / "config" / ".env"),
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

    # Transport settings
    mcp_transport: Literal["stdio", "http"] = Field(
        default="stdio",
        description="Transport protocol: 'stdio' for local AI assistants, 'http' for remote deployment",
    )
    mcp_host: str = Field(
        default="0.0.0.0",
        description="Host to bind HTTP server to",
    )
    mcp_port: int = Field(
        default=8080,
        description="Port for HTTP server (Railway sets PORT env var)",
    )
    port: int | None = Field(
        default=None,
        description="Railway-injected PORT env var (takes precedence over mcp_port)",
    )

    # Base URL for OAuth (required for HTTP transport)
    mcp_base_url: str = Field(
        default="",
        description="Public URL of the MCP server (e.g. https://mcp.railway.app). Required for HTTP transport.",
    )

    # Optional settings
    log_level: str = Field(default="INFO", description="Logging level")
    request_timeout: int = Field(default=30, description="HTTP request timeout in seconds")

    @property
    def effective_port(self) -> int:
        """Return the port to use - Railway's PORT takes precedence."""
        return self.port if self.port is not None else self.mcp_port

    def is_configured(self) -> bool:
        """Check if the API key is configured."""
        return bool(self.open_wearables_api_key.get_secret_value())


try:
    settings = Settings()
    if not settings.is_configured():
        print(
            f"Warning: OPEN_WEARABLES_API_KEY not set. Expected .env file at: {Settings.model_config.get('env_file')}",
            file=sys.stderr,
        )
except ValidationError as e:
    print(f"Configuration error: {e}", file=sys.stderr)
    settings = Settings(open_wearables_api_key=SecretStr(""))
