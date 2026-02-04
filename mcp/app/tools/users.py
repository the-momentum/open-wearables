"""MCP tools for user management."""

import logging

from fastmcp import FastMCP

from app.services.api_client import client

logger = logging.getLogger(__name__)

# Create router for user-related tools
users_router = FastMCP(name="Users Tools")


@users_router.tool
async def get_users(search: str | None = None, limit: int = 10) -> dict:
    """
    Get users accessible via the configured API key.

    Use this tool to discover available Open Wearables users before querying their health data.
    The API key determines which users are visible (personal, team, or enterprise scope).

    Args:
        search: Optional search term to filter users by first name, last name, or email.
                Example: "John" will match users with "John" in their name.
        limit: Maximum number of users to return (default: 10).
               Use the 'search' parameter to find specific users in large organizations
               rather than increasing this limit.

    Returns:
        A dictionary containing:
        - users: List of user objects with id, first_name, last_name, email (up to 'limit' users)
        - total: Total number of users matching the query (may be greater than returned users)

    Example response:
        {
            "users": [
                {"id": "uuid-1", "first_name": "John", "last_name": "Doe", "email": "john@example.com"},
                {"id": "uuid-2", "first_name": "Jane", "last_name": "Smith", "email": "jane@example.com"}
            ],
            "total": 2
        }

    Notes for LLMs:
        - Call this tool first if you don't know the user's ID
        - Use the 'search' parameter to filter by name if the user mentions a specific person
        - The 'id' field is a UUID that can be used with other tools like get_sleep_summary, get_workout_events
        - If only ONE user is returned: use that user automatically (this indicates a personal API key)
        - If MULTIPLE users are returned and user says "my/me": ask which user they mean
        - If MULTIPLE users are returned with a name hint: match by name or use 'search'
        - If 'total' exceeds the number of returned users, use 'search' to narrow results
    """
    try:
        response = await client.get_users(search=search, limit=limit)

        # Extract user data from paginated response
        users = response.get("items", [])

        return {
            "users": [
                {
                    "id": str(user.get("id")),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "email": user.get("email"),
                }
                for user in users
            ],
            "total": response.get("total", len(users)),
        }

    except ValueError as e:
        logger.error(f"API error in get_users: {e}")
        return {"error": str(e), "users": [], "total": 0}
    except Exception as e:
        logger.exception(f"Unexpected error in get_users: {e}")
        return {"error": f"Failed to fetch users: {e}", "users": [], "total": 0}
