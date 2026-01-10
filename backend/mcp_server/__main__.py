"""Entry point for running the MCP server as a module.

Usage:
    python -m mcp_server

Note: When running in Docker, use --init flag to ensure proper signal
handling and clean shutdown when the MCP client disconnects.
"""

from mcp_server.server import mcp

if __name__ == "__main__":
    mcp.run()  # stdio transport (default) - spawned by MCP clients
