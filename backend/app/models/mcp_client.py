from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKApiKey, PrimaryKey, Unique, str_255


class McpClient(BaseDbModel):
    """An OAuth client dynamically registered against the self-hosted MCP server.

    Bearer-token auth has no per-client identity to record, so this only ever fills
    up for MCP deployments running MCP_OAUTH_PASSWORD.
    """

    __tablename__ = "mcp_client"

    id: Mapped[PrimaryKey[UUID]]
    client_id: Mapped[Unique[str_255]]  # OAuth client_id issued by the MCP server's SinglePasswordOAuthProvider
    client_name: Mapped[str_255 | None]
    api_key_id: Mapped[FKApiKey]  # which API key the MCP server authenticates its backend calls with
    last_seen_at: Mapped[datetime]
