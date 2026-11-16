from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult, select, update

from app.database import DbSession
from app.models import RefreshToken


class RefreshTokenRepository:
    """Repository for refresh token database operations."""

    def __init__(self) -> None:
        self.model = RefreshToken

    def create(self, db_session: DbSession, token: RefreshToken) -> RefreshToken:
        """Create a new refresh token."""
        db_session.add(token)
        db_session.commit()
        db_session.refresh(token)
        return token

    def claim_valid_token(self, db_session: DbSession, token_id: str) -> RefreshToken | None:
        """Revoke a token that is not revoked yet and return it, or None when there is none.

        The check and the write are one UPDATE, so of concurrent claims only one gets the token.
        Does not commit: the claim is committed together with the replacement token
        when that is stored, and the row stays locked until then.
        """
        stmt = (
            update(self.model)
            .where(self.model.id == token_id, self.model.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
            .returning(self.model)
            .execution_options(populate_existing=True)
        )
        return db_session.execute(stmt).scalar_one_or_none()

    def get_by_user_id(self, db_session: DbSession, user_id: UUID) -> list[RefreshToken]:
        """Get all refresh tokens for a user."""
        stmt = select(self.model).where(self.model.user_id == user_id, self.model.revoked_at.is_(None))
        return list(db_session.execute(stmt).scalars().all())

    def get_by_developer_id(self, db_session: DbSession, developer_id: UUID) -> list[RefreshToken]:
        """Get all refresh tokens for a developer."""
        stmt = select(self.model).where(self.model.developer_id == developer_id, self.model.revoked_at.is_(None))
        return list(db_session.execute(stmt).scalars().all())

    def revoke_all_for_user(self, db_session: DbSession, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user. Returns count of revoked tokens."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.user_id == user_id, self.model.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = cast(CursorResult[tuple[()]], db_session.execute(stmt))
        db_session.commit()
        return result.rowcount or 0

    def revoke_all_for_developer(self, db_session: DbSession, developer_id: UUID) -> int:
        """Revoke all refresh tokens for a developer. Returns count of revoked tokens."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(self.model)
            .where(self.model.developer_id == developer_id, self.model.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        result = cast(CursorResult[tuple[()]], db_session.execute(stmt))
        db_session.commit()
        return result.rowcount or 0

    def update_last_used(self, db_session: DbSession, token: RefreshToken) -> RefreshToken:
        """Update the last_used_at timestamp of a token."""
        token.last_used_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(token)
        return token


refresh_token_repository = RefreshTokenRepository()
