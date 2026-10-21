from itertools import batched
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import EventRecordAggregate, SeriesAggregate


class AggregateRepository:
    """Upserts into an aggregate table on its unique key; key and refreshed columns come from the model."""

    def __init__(self, model: type[SeriesAggregate] | type[EventRecordAggregate]) -> None:
        table = cast(Table, model.__table__)
        self.model = model
        self.upsert_key = next(c for c in table.constraints if isinstance(c, UniqueConstraint))
        self.key_columns = tuple(column.name for column in self.upsert_key.columns)
        self.refreshed = tuple(
            column.name
            for column in table.columns
            if column.name not in self.key_columns and not column.primary_key and column.server_default is None
        )
        # Every column is a bind parameter; PostgreSQL allows 65535 per statement.
        self.rows_per_statement = 65535 // len(table.columns)

    def upsert(self, db_session: DbSession, rows: list[dict[str, Any]]) -> int:
        """Insert or refresh one row per upsert key; rows sharing a key merge their statistics."""
        unique: dict[tuple, dict[str, Any]] = {}
        for row in rows:
            key = tuple(row[column] for column in self.key_columns)
            known = unique.get(key) or {column: None for column in self.refreshed} | {"id": uuid4()}
            unique[key] = known | {column: value for column, value in row.items() if value is not None}
        for chunk in batched(unique.values(), self.rows_per_statement):
            stmt = insert(self.model).values(list(chunk))
            db_session.execute(
                stmt.on_conflict_do_update(
                    constraint=self.upsert_key,
                    # A value absent from this write keeps the stored one, e.g. a workout's mean cadence from its
                    # details and its max cadence from an SDK statistic, written by separate calls.
                    set_={
                        column: func.coalesce(stmt.excluded[column], self.model.__table__.c[column])
                        for column in self.refreshed
                    },
                )
            )
        return len(unique)
