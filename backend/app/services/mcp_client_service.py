from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import McpClient
from app.repositories.mcp_client_repository import McpClientRepository
from app.schemas.model_crud.credentials import McpClientCreateInternal, McpClientUpdate
from app.services.services import AppService


class McpClientService(AppService[McpClientRepository, McpClient, McpClientCreateInternal, McpClientUpdate]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=McpClientRepository,
            model=McpClient,
            log=log,
            **kwargs,
        )

    def touch(self, db: DbSession, api_key_id: UUID, client_id: str, client_name: str | None) -> McpClient:
        """Record that an MCP OAuth client registered or authenticated successfully.

        Upserts by client_id: the MCP server's in-memory client registry is the source of
        truth for what a client can currently do, this table only mirrors it for display.
        """
        now = datetime.now(timezone.utc)
        if existing := self.crud.get_by_client_id(db, client_id):
            return self.crud.update(db, existing, McpClientUpdate(client_name=client_name, last_seen_at=now))

        created = self.create(
            db,
            McpClientCreateInternal(
                client_id=client_id,
                client_name=client_name,
                api_key_id=api_key_id,
                last_seen_at=now,
            ),
        )
        self.logger.debug(f"New MCP client registered: {client_id} ({client_name})")
        return created

    def list_clients(self, db: DbSession) -> list[McpClient]:
        """List all known MCP clients, most recently active first."""
        clients = self.crud.get_all_ordered(db)
        self.logger.debug(f"Listed {len(clients)} MCP clients")
        return clients


mcp_client_service = McpClientService(log=getLogger(__name__))
