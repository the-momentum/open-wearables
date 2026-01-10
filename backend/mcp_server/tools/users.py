"""MCP tools for querying user data."""

from typing import Callable
from uuid import UUID

from fastmcp import FastMCP

from app.schemas.user import UserQueryParams
from app.services.user_service import user_service


def register_user_tools(mcp: FastMCP, get_db_session: Callable) -> None:
    """Register user-related MCP tools."""

    @mcp.tool
    def list_users(
        limit: int = 20,
        page: int = 1,
        search: str | None = None,
    ) -> dict:
        """List users in the system.

        Use this tool to find user IDs that can be used with other tools.

        Args:
            limit: Maximum number of users to return (1-100, default 20)
            page: Page number for pagination (default 1)
            search: Optional search term to filter by name or email

        Returns:
            Dictionary with users list and pagination info.
        """
        with get_db_session() as db:
            params = UserQueryParams(
                page=page,
                limit=min(limit, 100),
                search=search,
            )
            result = user_service.get_users_paginated(db, params)

            return {
                "users": [
                    {
                        "id": str(user.id),
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    }
                    for user in result.items
                ],
                "pagination": {
                    "total": result.total,
                    "page": result.page,
                    "limit": result.limit,
                    "pages": (result.total + result.limit - 1) // result.limit if result.limit > 0 else 0,
                },
            }

    @mcp.tool
    def get_user(user_id: str) -> dict:
        """Get details for a specific user.

        Args:
            user_id: The UUID of the user

        Returns:
            User details including email, name, and creation date.
        """
        with get_db_session() as db:
            user = user_service.get(db, UUID(user_id), raise_404=True)
            return {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "external_user_id": user.external_user_id,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
