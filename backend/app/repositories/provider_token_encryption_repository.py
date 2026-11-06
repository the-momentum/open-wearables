from typing import NamedTuple, cast
from uuid import UUID

from sqlalchemy import ColumnElement, CursorResult, column, func, or_, select, table, update

from app.database import DbSession
from app.utils.token_encryption import ENCRYPTED_PREFIX

# Untyped columns: the values are read and written as stored, past the model's EncryptedText
_connections = table("user_connection", column("id"), column("access_token"), column("refresh_token"))
_columns = _connections.c


def _encrypted(value: ColumnElement) -> ColumnElement[bool]:
    return func.starts_with(value, ENCRYPTED_PREFIX)


class StoredTokens(NamedTuple):
    connection_id: UUID
    access_token: str | None
    refresh_token: str | None


class ProviderTokenEncryptionRepository:
    """The stored provider tokens of ``user_connection``, as they are in the row (encrypted or plaintext)."""

    def find_batch(self, db: DbSession, *, encrypted: bool, after_id: UUID | None, limit: int) -> list[StoredTokens]:
        """Connections with at least one token stored encrypted (``encrypted``) or plaintext, by id after ``after_id``.

        NULL tokens match neither.
        """
        if encrypted:
            condition = or_(_encrypted(_columns.access_token), _encrypted(_columns.refresh_token))
        else:
            condition = or_(~_encrypted(_columns.access_token), ~_encrypted(_columns.refresh_token))
        query = select(_columns.id, _columns.access_token, _columns.refresh_token).where(condition)
        if after_id is not None:
            query = query.where(_columns.id > after_id)
        return [StoredTokens(*row) for row in db.execute(query.order_by(_columns.id).limit(limit))]

    def replace_tokens(
        self,
        db: DbSession,
        connection_id: UUID,
        stored: tuple[str | None, str | None],
        replacement: tuple[str | None, str | None],
    ) -> bool:
        """Store ``replacement`` unless the tokens are no longer ``stored``: a refresh in between keeps its tokens."""
        result = cast(
            CursorResult,
            db.execute(
                update(_connections)
                .where(
                    _columns.id == connection_id,
                    _columns.access_token.is_not_distinct_from(stored[0]),
                    _columns.refresh_token.is_not_distinct_from(stored[1]),
                )
                .values(access_token=replacement[0], refresh_token=replacement[1]),
            ),
        )
        return result.rowcount == 1
