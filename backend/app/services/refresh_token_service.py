import secrets
from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import UUID

from fastapi import HTTPException, status

from app.database import DbSession
from app.models import RefreshToken
from app.repositories.refresh_token_repository import refresh_token_repository
from app.schemas.token import TokenResponse
from app.schemas.token_type import TokenType
from app.services.sdk_token_service import create_sdk_user_token
from app.utils.security import create_access_token


def _generate_refresh_token_id() -> str:
    """Generate an opaque refresh token ID with rt- prefix."""
    return f"rt-{secrets.token_hex(16)}"


class RefreshTokenService:
    """Service for managing refresh tokens."""

    def __init__(self, log: Logger) -> None:
        self.logger = log
        self.repo = refresh_token_repository

    def create_sdk_refresh_token(self, db_session: DbSession, user_id: UUID, app_id: str) -> str:
        """Create a refresh token for an SDK token.

        Args:
            db_session: Database session
            user_id: The OpenWearables User ID
            app_id: The application ID that created the token

        Returns:
            The refresh token string (rt-{hex})
        """
        token_id = _generate_refresh_token_id()
        token = RefreshToken(
            id=token_id,
            token_type=TokenType.SDK,
            user_id=user_id,
            app_id=app_id,
            developer_id=None,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        self.repo.create(db_session, token)
        self.logger.debug(f"Created SDK refresh token for user {user_id}, app {app_id}")
        return token_id

    def create_developer_refresh_token(self, db_session: DbSession, developer_id: UUID) -> str:
        """Create a refresh token for a developer token.

        Args:
            db_session: Database session
            developer_id: The developer ID

        Returns:
            The refresh token string (rt-{hex})
        """
        token_id = _generate_refresh_token_id()
        token = RefreshToken(
            id=token_id,
            token_type=TokenType.DEVELOPER,
            user_id=None,
            app_id=None,
            developer_id=developer_id,
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            revoked_at=None,
        )
        self.repo.create(db_session, token)
        self.logger.debug(f"Created developer refresh token for developer {developer_id}")
        return token_id

    def refresh_token(self, db_session: DbSession, refresh_token_str: str) -> TokenResponse:
        """Exchange a refresh token for a new access token.

        Implements refresh token rotation: the old refresh token is revoked and
        a new one is issued with each refresh request.

        Args:
            db_session: Database session
            refresh_token_str: The refresh token string

        Returns:
            TokenResponse with new access token and new refresh token

        Raises:
            HTTPException: If the refresh token is invalid or revoked
        """
        token = self.repo.get_valid_token(db_session, refresh_token_str)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Revoke the old refresh token (rotation)
        self.repo.revoke_token(db_session, token)

        # Generate new access token and refresh token based on token type
        if token.token_type == TokenType.SDK:
            access_token = create_sdk_user_token(
                app_id=token.app_id,  # type: ignore[arg-type]
                user_id=str(token.user_id),
            )
            new_refresh_token = self.create_sdk_refresh_token(
                db_session,
                user_id=token.user_id,  # type: ignore[arg-type]
                app_id=token.app_id,  # type: ignore[arg-type]
            )
            self.logger.debug(f"Refreshed SDK token for user {token.user_id} (rotated)")
        elif token.token_type == TokenType.DEVELOPER:
            access_token = create_access_token(subject=str(token.developer_id))
            new_refresh_token = self.create_developer_refresh_token(
                db_session,
                developer_id=token.developer_id,  # type: ignore[arg-type]
            )
            self.logger.debug(f"Refreshed developer token for developer {token.developer_id} (rotated)")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown token type: {token.token_type}",
            )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            refresh_token=new_refresh_token,
        )

    def revoke_token(self, db_session: DbSession, refresh_token_str: str) -> bool:
        """Revoke a refresh token.

        Args:
            db_session: Database session
            refresh_token_str: The refresh token string

        Returns:
            True if the token was revoked, False if not found

        Raises:
            HTTPException: If the refresh token is not found
        """
        token = self.repo.get_valid_token(db_session, refresh_token_str)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refresh token not found",
            )

        self.repo.revoke_token(db_session, token)
        self.logger.debug(f"Revoked refresh token {refresh_token_str[:10]}...")
        return True


refresh_token_service = RefreshTokenService(log=getLogger(__name__))
