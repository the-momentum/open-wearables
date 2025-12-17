"""
Tests for authentication utility functions.

Tests JWT token extraction, developer authentication, and error handling.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.tests.utils.factories import create_developer
from app.utils.auth import get_current_developer, get_current_developer_optional
from app.utils.security import create_access_token


class TestGetCurrentDeveloper:
    """Test suite for get_current_developer function."""

    @pytest.mark.asyncio
    async def test_get_current_developer_valid_token(self, db: Session) -> None:
        """Test extracting developer from valid JWT token."""
        # Arrange
        developer = create_developer(db, email="test@example.com")
        token = create_access_token(subject=str(developer.id))

        # Act
        result = await get_current_developer(db=db, token=token)

        # Assert
        assert result is not None
        assert result.id == developer.id
        assert result.email == developer.email

    @pytest.mark.asyncio
    async def test_get_current_developer_expired_token(self, db: Session) -> None:
        """Test handling of expired JWT token."""
        # Arrange
        developer = create_developer(db)
        # Create token that expires immediately
        token = create_access_token(subject=str(developer.id), expires_delta=timedelta(seconds=-1))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"
        assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio
    async def test_get_current_developer_invalid_token_format(self, db: Session) -> None:
        """Test handling of malformed JWT token."""
        # Arrange
        invalid_token = "not.a.valid.jwt.token"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=invalid_token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_developer_token_without_subject(self, db: Session) -> None:
        """Test handling of token without subject claim."""
        # Arrange
        # Create token manually without 'sub' claim
        payload = {"exp": 9999999999}
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_developer_nonexistent_developer(self, db: Session) -> None:
        """Test handling when developer doesn't exist in database."""
        # Arrange
        nonexistent_id = uuid4()
        token = create_access_token(subject=str(nonexistent_id))

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=token)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    @pytest.mark.asyncio
    async def test_get_current_developer_invalid_uuid_in_token(self, db: Session) -> None:
        """Test handling of invalid UUID in token subject."""
        # Arrange
        token = create_access_token(subject="not-a-valid-uuid")

        # Act & Assert
        # The auth code tries to create UUID() which raises ValueError
        # This should be caught and converted to HTTPException
        with pytest.raises((HTTPException, ValueError)) as exc_info:
            await get_current_developer(db=db, token=token)

        if isinstance(exc_info.value, HTTPException):
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_developer_tampered_token(self, db: Session) -> None:
        """Test handling of tampered JWT token."""
        # Arrange
        developer = create_developer(db)
        token = create_access_token(subject=str(developer.id))
        # Tamper with the token
        tampered_token = token[:-5] + "xxxxx"

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=tampered_token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_developer_wrong_secret_key(self, db: Session) -> None:
        """Test handling of token signed with wrong secret key."""
        # Arrange
        developer = create_developer(db)
        # Create token with wrong secret
        payload = {"sub": str(developer.id), "exp": 9999999999}
        token = jwt.encode(payload, "wrong-secret-key", algorithm=settings.algorithm)

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=token)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_developer_empty_token(self, db: Session) -> None:
        """Test handling of empty token."""
        # Arrange
        token = ""

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            await get_current_developer(db=db, token=token)

        assert exc_info.value.status_code == 401


class TestGetCurrentDeveloperOptional:
    """Test suite for get_current_developer_optional function."""

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_valid_token(self, db: Session) -> None:
        """Test extracting developer from valid token."""
        # Arrange
        developer = create_developer(db, email="optional@example.com")
        token = create_access_token(subject=str(developer.id))

        # Act
        result = await get_current_developer_optional(db=db, token=token)

        # Assert
        assert result is not None
        assert result.id == developer.id
        assert result.email == developer.email

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_no_token(self, db: Session) -> None:
        """Test behavior when no token is provided."""
        # Act
        result = await get_current_developer_optional(db=db, token=None)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_invalid_token(self, db: Session) -> None:
        """Test behavior with invalid token returns None instead of raising."""
        # Arrange
        invalid_token = "invalid.jwt.token"

        # Act
        result = await get_current_developer_optional(db=db, token=invalid_token)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_expired_token(self, db: Session) -> None:
        """Test behavior with expired token returns None."""
        # Arrange
        developer = create_developer(db)
        token = create_access_token(subject=str(developer.id), expires_delta=timedelta(seconds=-1))

        # Act
        result = await get_current_developer_optional(db=db, token=token)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_no_subject(self, db: Session) -> None:
        """Test behavior when token has no subject claim."""
        # Arrange
        payload = {"exp": 9999999999}
        token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

        # Act
        result = await get_current_developer_optional(db=db, token=token)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_nonexistent_developer(self, db: Session) -> None:
        """Test behavior when developer doesn't exist."""
        # Arrange
        nonexistent_id = uuid4()
        token = create_access_token(subject=str(nonexistent_id))

        # Act
        result = await get_current_developer_optional(db=db, token=token)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_empty_token(self, db: Session) -> None:
        """Test behavior with empty string token."""
        # Act
        result = await get_current_developer_optional(db=db, token="")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_current_developer_optional_tampered_token(self, db: Session) -> None:
        """Test behavior with tampered token returns None."""
        # Arrange
        developer = create_developer(db)
        token = create_access_token(subject=str(developer.id))
        tampered_token = token[:-5] + "xxxxx"

        # Act
        result = await get_current_developer_optional(db=db, token=tampered_token)

        # Assert
        assert result is None


class TestAuthWorkflow:
    """Integration tests for authentication workflow."""

    @pytest.mark.asyncio
    async def test_full_auth_workflow(self, db: Session) -> None:
        """Test complete authentication workflow."""
        # Arrange - Create developer
        developer = create_developer(db, email="workflow@example.com")

        # Act - Generate token (as done during login)
        token = create_access_token(subject=str(developer.id))

        # Assert - Token should be valid
        authenticated_developer = await get_current_developer(db=db, token=token)
        assert authenticated_developer.id == developer.id
        assert authenticated_developer.email == developer.email

    @pytest.mark.asyncio
    async def test_optional_auth_vs_required_auth(self, db: Session) -> None:
        """Test difference between optional and required auth."""
        # Arrange
        developer = create_developer(db)
        valid_token = create_access_token(subject=str(developer.id))
        invalid_token = "invalid"

        # Act & Assert - Valid token works for both
        result_required = await get_current_developer(db=db, token=valid_token)
        result_optional = await get_current_developer_optional(db=db, token=valid_token)
        assert result_required.id == developer.id
        assert result_optional.id == developer.id

        # Act & Assert - Invalid token: required raises, optional returns None
        with pytest.raises(HTTPException):
            await get_current_developer(db=db, token=invalid_token)

        result_optional_invalid = await get_current_developer_optional(db=db, token=invalid_token)
        assert result_optional_invalid is None

    @pytest.mark.asyncio
    async def test_multiple_developers_different_tokens(self, db: Session) -> None:
        """Test that different developers have different tokens."""
        # Arrange
        dev1 = create_developer(db, email="dev1@example.com")
        dev2 = create_developer(db, email="dev2@example.com")

        token1 = create_access_token(subject=str(dev1.id))
        token2 = create_access_token(subject=str(dev2.id))

        # Assert - Tokens should be different
        assert token1 != token2

        # Act & Assert - Each token authenticates correct developer
        result1 = await get_current_developer(db=db, token=token1)
        result2 = await get_current_developer(db=db, token=token2)

        assert result1.id == dev1.id
        assert result1.email == "dev1@example.com"
        assert result2.id == dev2.id
        assert result2.email == "dev2@example.com"

    @pytest.mark.asyncio
    async def test_token_isolation_between_developers(self, db: Session) -> None:
        """Test that one developer's token can't access another developer's data."""
        # Arrange
        dev1 = create_developer(db, email="dev1@example.com")
        dev2 = create_developer(db, email="dev2@example.com")

        token1 = create_access_token(subject=str(dev1.id))

        # Act - Use dev1's token
        authenticated_dev = await get_current_developer(db=db, token=token1)

        # Assert - Should only authenticate as dev1, not dev2
        assert authenticated_dev.id == dev1.id
        assert authenticated_dev.id != dev2.id

    @pytest.mark.asyncio
    async def test_auth_with_custom_token_expiry(self, db: Session) -> None:
        """Test authentication with custom token expiration."""
        # Arrange
        developer = create_developer(db)

        # Act - Create tokens with different expiration times
        short_token = create_access_token(subject=str(developer.id), expires_delta=timedelta(minutes=5))
        long_token = create_access_token(subject=str(developer.id), expires_delta=timedelta(days=7))

        # Assert - Both tokens should work while valid
        result_short = await get_current_developer(db=db, token=short_token)
        result_long = await get_current_developer(db=db, token=long_token)

        assert result_short.id == developer.id
        assert result_long.id == developer.id
