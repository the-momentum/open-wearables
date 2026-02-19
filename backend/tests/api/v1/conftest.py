"""
API v1 fixtures — authenticated developer, API key, test user.
"""

import pytest
from sqlalchemy.orm import Session

from app.models import ApiKey, Developer, User
from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils.auth import api_key_headers, developer_auth_headers


@pytest.fixture
def developer(db: Session) -> Developer:
    """Authenticated test developer."""
    return DeveloperFactory.create_sync(email="test@example.com", password="test_password")


@pytest.fixture
def api_key(db: Session, developer: Developer) -> ApiKey:
    """API key owned by the test developer."""
    return ApiKeyFactory.create_sync(developer=developer, name="Test API Key")


@pytest.fixture
def user(db: Session) -> User:
    """A plain test user (data owner)."""
    return UserFactory.create_sync()


@pytest.fixture
def auth_headers(developer: Developer) -> dict[str, str]:
    """JWT Bearer headers for ``developer``."""
    return developer_auth_headers(developer.id)


@pytest.fixture
def api_key_header(api_key: ApiKey) -> dict[str, str]:
    """X-Open-Wearables-API-Key headers."""
    return api_key_headers(api_key.id)
