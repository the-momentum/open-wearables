from uuid import UUID

from fastapi import APIRouter, status

from app.database import DbSession
from app.schemas.model_crud.credentials import McpClientRead, McpClientTouch
from app.services import ApiKeyDep, DeveloperDep, mcp_client_service

router = APIRouter()


@router.get("/mcp-clients")
def list_mcp_clients(db: DbSession, developer: DeveloperDep) -> list[McpClientRead]:
    """List MCP OAuth clients that have registered or authenticated against this deployment.

    Bearer-token connections have no per-client identity, so only OAuth (claude.ai-style
    connectors) clients show up here.
    """
    return [McpClientRead.model_validate(client) for client in mcp_client_service.list_clients(db)]


@router.post("/mcp-clients/touch", status_code=status.HTTP_204_NO_CONTENT)
def touch_mcp_client(payload: McpClientTouch, db: DbSession, api_key_id: ApiKeyDep) -> None:
    """Record an MCP client registration or successful login.

    Called by the self-hosted MCP server itself (authenticating with its own configured
    API key), not by dashboard users - hence ApiKeyDep rather than DeveloperDep.
    """
    mcp_client_service.touch(db, UUID(api_key_id), payload.client_id, payload.client_name)


@router.delete("/mcp-clients/{id}", status_code=status.HTTP_204_NO_CONTENT)
def forget_mcp_client(id: UUID, db: DbSession, developer: DeveloperDep) -> None:
    """Remove an MCP client from this list.

    This only forgets the record here - it does not revoke the client's live OAuth
    registration/tokens on the MCP server, which keeps its own in-memory state. If the
    client reconnects, it will simply reappear.
    """
    mcp_client_service.delete(db, id, raise_404=True)
