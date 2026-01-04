#!/bin/bash
# Start the Open Wearables MCP Server
#
# Usage:
#   ./scripts/start/mcp.sh
#
# The MCP server uses SSE (HTTP) transport on port 8001.
# Connect via: http://localhost:8001/sse
#
# Environment variables:
#   - All database and config variables from the main app are supported
#   - See config/.env for available settings

set -e

cd "$(dirname "$0")/../.."

echo "Starting Open Wearables MCP Server on port 8001..."
uv run python -m mcp_server
