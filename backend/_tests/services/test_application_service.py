"""Tests for Application service."""

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.application_service import application_service
from _tests.factories import DeveloperFactory


class TestApplicationServiceCreate:
    """Tests for creating applications."""

    def test_create_application_generates_app_id_prefix(self, db: Session) -> None:
        """Should generate app_id with 'app_' prefix."""
        developer = DeveloperFactory()
        app, plain_secret = application_service.create_application(db, developer.id, "Test App")

        assert app.app_id.startswith("app_")
        assert len(app.app_id) > 10

    def test_create_application_generates_secret_prefix(self, db: Session) -> None:
        """Should generate app_secret with 'secret_' prefix."""
        developer = DeveloperFactory()
        app, plain_secret = application_service.create_application(db, developer.id, "Test App")

        assert plain_secret.startswith("secret_")
        assert len(plain_secret) > 20

    def test_create_application_hashes_secret(self, db: Session) -> None:
        """Should store hashed secret, not plaintext."""
        developer = DeveloperFactory()
        app, plain_secret = application_service.create_application(db, developer.id, "Test App")

        # The stored hash should not equal the plain secret
        assert app.app_secret_hash != plain_secret
        # Should start with hashed_ (our test mock) or be a bcrypt hash
        assert app.app_secret_hash.startswith("hashed_") or "$2b$" in app.app_secret_hash

    def test_create_application_sets_developer_id(self, db: Session) -> None:
        """Should set developer_id correctly."""
        developer = DeveloperFactory()
        app, _ = application_service.create_application(db, developer.id, "Test App")

        assert app.developer_id == developer.id

    def test_create_application_sets_name(self, db: Session) -> None:
        """Should set name correctly."""
        developer = DeveloperFactory()
        app, _ = application_service.create_application(db, developer.id, "My Custom App")

        assert app.name == "My Custom App"

    def test_create_application_sets_timestamps(self, db: Session) -> None:
        """Should set created_at and updated_at."""
        developer = DeveloperFactory()
        app, _ = application_service.create_application(db, developer.id, "Test App")

        assert app.created_at is not None
        assert app.updated_at is not None


class TestApplicationServiceValidate:
    """Tests for validating application credentials."""

    def test_validate_credentials_success(self, db: Session) -> None:
        """Should validate correct credentials."""
        developer = DeveloperFactory()
        app, plain_secret = application_service.create_application(db, developer.id, "Test App")

        validated = application_service.validate_credentials(db, app.app_id, plain_secret)

        assert validated.id == app.id

    def test_validate_credentials_wrong_secret_raises_401(self, db: Session) -> None:
        """Should raise 401 for wrong secret."""
        developer = DeveloperFactory()
        app, _ = application_service.create_application(db, developer.id, "Test App")

        with pytest.raises(HTTPException) as exc_info:
            application_service.validate_credentials(db, app.app_id, "wrong_secret")

        assert exc_info.value.status_code == 401

    def test_validate_credentials_nonexistent_app_raises_401(self, db: Session) -> None:
        """Should raise 401 for non-existent app."""
        with pytest.raises(HTTPException) as exc_info:
            application_service.validate_credentials(db, "nonexistent_app", "secret")

        assert exc_info.value.status_code == 401


class TestApplicationServiceList:
    """Tests for listing applications."""

    def test_list_applications_returns_developer_apps(self, db: Session) -> None:
        """Should return applications for specific developer."""
        developer1 = DeveloperFactory()
        developer2 = DeveloperFactory()
        application_service.create_application(db, developer1.id, "App 1")
        application_service.create_application(db, developer1.id, "App 2")
        application_service.create_application(db, developer2.id, "App 3")

        apps = application_service.list_applications(db, developer1.id)

        assert len(apps) == 2
        assert all(app.developer_id == developer1.id for app in apps)

    def test_list_applications_empty(self, db: Session) -> None:
        """Should return empty list when no applications."""
        developer = DeveloperFactory()

        apps = application_service.list_applications(db, developer.id)

        assert apps == []


class TestApplicationServiceDelete:
    """Tests for deleting applications."""

    def test_delete_application_success(self, db: Session) -> None:
        """Should delete application."""
        developer = DeveloperFactory()
        app, _ = application_service.create_application(db, developer.id, "Test App")
        app_id = app.app_id

        application_service.delete_application(db, app_id, developer.id)

        # Verify it's deleted
        assert application_service.crud.get_by_app_id(db, app_id) is None

    def test_delete_application_not_owner_raises_404(self, db: Session) -> None:
        """Should raise 404 when deleting another developer's app."""
        developer1 = DeveloperFactory()
        developer2 = DeveloperFactory()
        app, _ = application_service.create_application(db, developer1.id, "Test App")

        with pytest.raises(HTTPException) as exc_info:
            application_service.delete_application(db, app.app_id, developer2.id)

        assert exc_info.value.status_code == 404


class TestApplicationServiceRotateSecret:
    """Tests for rotating application secrets."""

    def test_rotate_secret_returns_new_secret(self, db: Session) -> None:
        """Should return new secret after rotation."""
        developer = DeveloperFactory()
        app, old_secret = application_service.create_application(db, developer.id, "Test App")

        updated_app, new_secret = application_service.rotate_secret(db, app.app_id, developer.id)

        assert new_secret != old_secret
        assert new_secret.startswith("secret_")

    def test_rotate_secret_old_secret_invalid(self, db: Session) -> None:
        """Old secret should not work after rotation."""
        developer = DeveloperFactory()
        app, old_secret = application_service.create_application(db, developer.id, "Test App")

        # Rotate secret
        updated_app, new_secret = application_service.rotate_secret(db, app.app_id, developer.id)

        # Old secret should fail
        with pytest.raises(HTTPException) as exc_info:
            application_service.validate_credentials(db, app.app_id, old_secret)

        assert exc_info.value.status_code == 401

    def test_rotate_secret_not_owner_raises_404(self, db: Session) -> None:
        """Should raise 404 when rotating another developer's app secret."""
        developer1 = DeveloperFactory()
        developer2 = DeveloperFactory()
        app, _ = application_service.create_application(db, developer1.id, "Test App")

        with pytest.raises(HTTPException) as exc_info:
            application_service.rotate_secret(db, app.app_id, developer2.id)

        assert exc_info.value.status_code == 404
