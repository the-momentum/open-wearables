"""Open Wearables MCP Server.

A Model Context Protocol server that enables LLM clients to query
health and wearable data from the Open Wearables platform.

Usage:
    python -m mcp_server.server
"""

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastmcp import FastMCP

from app.database import SessionLocal
from mcp_server.tools.users import register_user_tools

# Initialize FastMCP server
mcp = FastMCP(
    name="Open Wearables MCP",
    instructions="""
    Open Wearables MCP Server provides access to health and wearable data.

    To query data, you need a user_id. Use list_users to find available users,
    then use get_user to get details about a specific user.
    """,
)


@contextmanager
def get_db_session() -> Iterator:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()


# Register user tools
register_user_tools(mcp, get_db_session)


if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8001)
