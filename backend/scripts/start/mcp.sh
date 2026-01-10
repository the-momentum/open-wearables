#!/bin/bash
# Start the Open Wearables MCP Server
#
# Usage:
#   ./scripts/start/mcp.sh
#
# The MCP server uses stdio transport (stdin/stdout).
# It is spawned by MCP clients (e.g., Claude Desktop) as a subprocess.
#
# Environment variables:
#   - All database and config variables from the main app are supported
#   - See config/.env for available settings

set -e

cd "$(dirname "$0")/../.."

# Note: No echo statements here - stdout is reserved for MCP protocol messages
# Any debug output should go to stderr
uv run python -m mcp_server
