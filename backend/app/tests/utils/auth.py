"""
Authentication helpers for tests.
"""

from datetime import timedelta
from uuid import UUID

from app.utils.security import create_access_token


def developer_auth_headers(developer_id: UUID | str) -> dict[str, str]:
    """Generate JWT Bearer authorization headers for a developer."""
    token = create_access_token(subject=str(developer_id))
    return {"Authorization": f"Bearer {token}"}


def api_key_headers(api_key: str) -> dict[str, str]:
    """Generate X-API-Key headers for API key authentication."""
    return {"X-API-Key": api_key}


def create_test_token(
    developer_id: UUID | str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a custom JWT token for testing."""
    return create_access_token(subject=str(developer_id), expires_delta=expires_delta)
