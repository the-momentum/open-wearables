"""
API v1 specific fixtures.
"""

import pytest
from sqlalchemy.orm import Session

from app.models import ApiKey, Developer, User
from _tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from _tests.utils import api_key_headers, developer_auth_headers


@pytest.fixture
def developer(db: Session) -> Developer:
    """Create a test developer for authentication."""
    return DeveloperFactory(email="test@example.com", password="test_password")


@pytest.fixture
def api_key(db: Session, developer: Developer) -> ApiKey:
    """Create a test API key."""
    return ApiKeyFactory(developer=developer, name="Test API Key")


@pytest.fixture
def user(db: Session) -> User:
    """Create a test user."""
    return UserFactory()


@pytest.fixture
def auth_headers(developer: Developer) -> dict[str, str]:
    """Get authentication headers for the test developer."""
    return developer_auth_headers(developer.id)


@pytest.fixture
def api_key_header(api_key: ApiKey) -> dict[str, str]:
    """Get API key headers."""
    return api_key_headers(api_key.id)
