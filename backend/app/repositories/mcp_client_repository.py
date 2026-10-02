from app.database import DbSession
from app.models import McpClient
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.credentials import McpClientCreateInternal, McpClientUpdate


class McpClientRepository(CrudRepository[McpClient, McpClientCreateInternal, McpClientUpdate]):
    def __init__(self, model: type[McpClient]):
        super().__init__(model)

    def get_by_client_id(self, db_session: DbSession, client_id: str) -> McpClient | None:
        """Get an MCP client by the OAuth client_id the MCP server issued it."""
        return db_session.query(self.model).filter(self.model.client_id == client_id).one_or_none()

    def get_all_ordered(self, db_session: DbSession) -> list[McpClient]:
        """Get all MCP clients, most recently active first."""
        return db_session.query(self.model).order_by(self.model.last_seen_at.desc()).all()
