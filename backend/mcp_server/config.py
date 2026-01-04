"""MCP Server configuration.

Reuses the main application settings for database and auth configuration.
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

# Re-export settings for use in MCP server
__all__ = ["settings"]
