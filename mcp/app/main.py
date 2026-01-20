"""Open Wearables MCP Server - Main entry point."""

import logging

from fastmcp import FastMCP

from app.config import settings
from app.tools.sleep import get_sleep_records
from app.tools.users import list_users

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastMCP server instance
mcp = FastMCP(
    "open-wearables",
    instructions="""
    Enables the model to query data describing user health states and general wellness metrics.
    Data is acquired from users' wearable devices (Garmin, Whoop, Polar, Suunto, etc.),
    covering all user-connected devices and providers, aggregated into a single unified format.

    Available tools:
    - list_users: Discover users accessible via your API key
    - get_sleep_records: Get sleep data for a user over a specified time period

    Workflow:
    1. If you don't know the user's ID, call list_users first to discover accessible users
    2. Use the user's ID (or name) to query their health data with the appropriate tool
    3. Present the data in a human-friendly format, highlighting key insights

    The API key determines which users you can access (personal, team, or enterprise scope).
    All data is returned in a normalized format regardless of the original wearable provider.
    """,
)

# Register tools
mcp.tool(list_users)
mcp.tool(get_sleep_records)

logger.info(f"Open Wearables MCP server initialized. API URL: {settings.open_wearables_api_url}")


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
