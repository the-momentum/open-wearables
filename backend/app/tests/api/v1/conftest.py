"""
API v1 specific fixtures.
"""

import pytest
from sqlalchemy.orm import Session

from app.tests.utils import create_api_key, create_developer, create_user


@pytest.fixture
def developer(db: Session):
    """Create a test developer for authentication."""
    return create_developer(db, email="test@example.com", password="test_password")


@pytest.fixture
def api_key(db: Session, developer):
    """Create a test API key."""
    return create_api_key(db, developer=developer, name="Test API Key")


@pytest.fixture
def user(db: Session):
    """Create a test user."""
    return create_user(db)


@pytest.fixture
def auth_headers(developer):
    """Get authentication headers for the test developer."""
    from app.tests.utils import developer_auth_headers

    return developer_auth_headers(developer.id)


@pytest.fixture
def api_key_header(api_key):
    """Get API key headers."""
    from app.tests.utils import api_key_headers

    return api_key_headers(api_key.id)
