from datetime import datetime
from typing import Any, NamedTuple, cast

from sqlalchemy import (
    ColumnClause,
    ColumnElement,
    CursorResult,
    TableClause,
    column,
    func,
    or_,
    select,
    update,
)
from sqlalchemy import table as table_clause

import app.models  # noqa: F401  (registers every model's table in BaseDbModel.metadata, read below)
from app.database import BaseDbModel, DbSession
from app.utils.token_encryption import ENCRYPTED_MARK, ENCRYPTED_PREFIX, EncryptedText, read_encryption_start


class SecretColumns(NamedTuple):
    """The columns of a table that hold provider secrets, and the key its rows are read by."""

    table: TableClause
    key: ColumnClause
    values: tuple[ColumnClause, ...]


def _secret_columns() -> tuple[SecretColumns, ...]:
    """Every model column stored with EncryptedText, by table. Untyped: values are read and written as stored."""
    found = []
    for model_table in sorted(BaseDbModel.metadata.tables.values(), key=lambda model_table: model_table.name):
        names = [value.name for value in model_table.columns if isinstance(value.type, EncryptedText)]
        if names:
            (key,) = model_table.primary_key.columns
            table = table_clause(model_table.name, column(key.name), *(column(name) for name in names))
            found.append(SecretColumns(table, table.c[key.name], tuple(table.c[name] for name in names)))
    return tuple(found)


SECRET_COLUMNS = _secret_columns()


def _encrypted(value: ColumnElement) -> ColumnElement[bool]:
    """Encrypted in this release's format."""
    return func.starts_with(value, ENCRYPTED_PREFIX)


def _plaintext(value: ColumnElement) -> ColumnElement[bool]:
    return ~func.starts_with(value, ENCRYPTED_MARK)


class StoredRow(NamedTuple):
    key: Any
    values: tuple[str | None, ...]


class ProviderTokenEncryptionRepository:
    """The encryption marker, and the provider secrets of ``SECRET_COLUMNS`` as stored (encrypted or plaintext)."""

    def get_encryption_start(self, db: DbSession) -> datetime | None:
        """From the marker (``read_encryption_start``); raises when it can't be read or has another SECRET_KEY."""
        return read_encryption_start(db.connection())

    def find_batch(
        self, db: DbSession, columns: SecretColumns, *, encrypted: bool, after_key: Any, limit: int
    ) -> list[StoredRow]:
        """Rows with at least one value stored encrypted (``encrypted``) or plaintext, by key after ``after_key``.

        NULL values match neither, and neither do values in a later release's format.
        """
        condition = or_(*(_encrypted(value) if encrypted else _plaintext(value) for value in columns.values))
        query = select(columns.key, *columns.values).where(condition)
        if after_key is not None:
            query = query.where(columns.key > after_key)
        return [StoredRow(key, tuple(values)) for key, *values in db.execute(query.order_by(columns.key).limit(limit))]

    def replace_values(
        self,
        db: DbSession,
        columns: SecretColumns,
        key: Any,
        stored: tuple[str | None, ...],
        replacement: tuple[str | None, ...],
    ) -> bool:
        """Store ``replacement`` unless the row no longer holds ``stored``: a write in between keeps its values."""
        result = cast(
            CursorResult,
            db.execute(
                update(columns.table)
                .where(
                    columns.key == key,
                    *(value.is_not_distinct_from(old) for value, old in zip(columns.values, stored, strict=True)),
                )
                .values(dict(zip(columns.values, replacement, strict=True))),
            ),
        )
        return result.rowcount == 1
