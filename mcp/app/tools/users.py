"""MCP tool for listing users."""

import logging

from app.services.api_client import client

logger = logging.getLogger(__name__)


async def list_users(search: str | None = None) -> dict:
    """
    List all users accessible via the configured API key.

    Use this tool to discover available users before querying their health data.
    The API key determines which users are visible (personal, team, or enterprise scope).

    Args:
        search: Optional search term to filter users by first name, last name, or email.
                Example: "John" will match users with "John" in their name.

    Returns:
        A dictionary containing:
        - users: List of user objects with id, first_name, last_name, email
        - total: Total number of users matching the query

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
        - The 'id' field is a UUID that can be used with other tools like get_sleep_records
        - If only one user exists, you can proceed directly with their data
    """
    try:
        response = await client.get_users(search=search)

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
        logger.error(f"API error in list_users: {e}")
        return {"error": str(e), "users": [], "total": 0}
    except Exception as e:
        logger.exception(f"Unexpected error in list_users: {e}")
        return {"error": f"Failed to fetch users: {e}", "users": [], "total": 0}
