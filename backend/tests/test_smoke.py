"""
Smoke test — validates the testcontainers + polyfactory infrastructure.

Remove this file once real tests are in place.
"""

from sqlalchemy.orm import Session

from app.models import User
from tests.factories import UserFactory


def test_factory_creates_user(db: Session) -> None:
    user = UserFactory.create_sync(email="smoke@test.local")
    assert user.id is not None
    assert user.email == "smoke@test.local"
    found = db.get(User, user.id)
    assert found is not None
    assert found.email == "smoke@test.local"
