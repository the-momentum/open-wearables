"""
API v1 specific fixtures.
"""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models import ApiKey, Developer, User
from tests.factories import ApiKeyFactory, DeveloperFactory, UserFactory
from tests.utils import api_key_headers, developer_auth_headers


@pytest.fixture(autouse=True)
def _sdk_auth_on_test_session(db: Session) -> Iterator[None]:
    """Route the detached session of get_sdk_auth onto the test session, like the client's DbSession override."""
    with patch("app.utils.auth.SessionLocal", create=True) as session_local:
        session_local.return_value.__enter__.return_value = db
        yield


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
    return api_key_headers(api_key.plain_key)
