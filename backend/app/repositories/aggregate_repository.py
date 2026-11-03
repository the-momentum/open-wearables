from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Table, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.mappings import SERIES_VALUE_SCALE
from app.models import EventRecordAggregate, SeriesAggregate

_STATISTICS = ("sum", "avg", "min", "max", "last")


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
        self.written = ("id", *self.key_columns, *self.refreshed)
        # A session's extremes add up across writes: a night's lowest heart rate reported per sleep segment,
        # a workout's max cadence from an SDK statistic next to its mean from the details. A day row is
        # written whole by one provider call, so a later call may correct it either way.
        self.extremes_accumulate = model is EventRecordAggregate

    def upsert(self, db_session: DbSession, rows: list[dict[str, Any]]) -> int:
        """Insert or refresh one row per upsert key; rows sharing a key merge their statistics."""
        unique = self._one_per_key(rows)
        if unique:
            stmt = insert(self.model)
            stmt = stmt.on_conflict_do_update(
                constraint=self.upsert_key,
                # A value absent from this write keeps the stored one, e.g. a workout's mean cadence from its
                # details and its max cadence from an SDK statistic, written by separate calls.
                set_={column: self._refreshed_value(stmt, column) for column in self.refreshed},
            )
            self._execute_many(db_session, stmt, unique)
        return len(unique)

    def _execute_many(self, db_session: DbSession, stmt: Any, unique: dict[tuple, dict[str, Any]]) -> Any:
        """One statement compiled once for every row, sent in pages: no statement is rebuilt per batch of rows."""
        rows = [{column: row.get(column) for column in self.written} for row in self._in_key_order(unique)]
        return db_session.connection().execute(stmt, rows)

    def _in_key_order(self, unique: dict[tuple, dict[str, Any]]) -> list[dict[str, Any]]:
        """Two writers upserting overlapping keys in different orders can deadlock; one order for everyone."""
        return [unique[key] for key in sorted(unique, key=lambda key: tuple(str(part) for part in key))]

    def _refreshed_value(self, stmt: Any, column: str) -> Any:
        excluded, stored = stmt.excluded[column], self.model.__table__.c[column]
        if self.extremes_accumulate and column == "min":
            return func.least(excluded, stored)
        if self.extremes_accumulate and column == "max":
            return func.greatest(excluded, stored)
        return func.coalesce(excluded, stored)

    def move_record(self, db_session: DbSession, from_record_id: Any, to_record_id: Any) -> int:
        """One event record's session rows go onto another, combining with the rows it already holds."""
        rows = [
            {column: getattr(row, column) for column in (*self.key_columns, *self.refreshed)}
            | {"record_id": to_record_id}
            for row in db_session.query(self.model).filter(self.model.record_id == from_record_id)  # ty: ignore[unresolved-attribute]
        ]
        return self.upsert(db_session, rows) if rows else 0

    def insert_missing(self, db_session: DbSession, rows: list[dict[str, Any]]) -> int:
        """Insert the rows whose key is not stored yet; a stored row is left exactly as it is."""
        unique = self._one_per_key(rows)
        if not unique:
            return 0
        stmt = insert(self.model).on_conflict_do_nothing(constraint=self.upsert_key).returning(self.model.id)
        return len(self._execute_many(db_session, stmt, unique).all())

    def _one_per_key(self, rows: list[dict[str, Any]]) -> dict[tuple, dict[str, Any]]:
        unique: dict[tuple, dict[str, Any]] = {}
        for row in rows:
            row = row | {
                column: round(row[column], SERIES_VALUE_SCALE) for column in _STATISTICS if row.get(column) is not None
            }
            key = tuple(row[column] for column in self.key_columns)
            known = unique.get(key) or {column: None for column in self.refreshed} | {"id": uuid4()}
            merged = known | {column: value for column, value in row.items() if value is not None}
            if self.extremes_accumulate:
                # As the database merges them: two of a session's extremes in one write keep the more extreme.
                for column, pick in (("min", min), ("max", max)):
                    stored, written = known.get(column), row.get(column)
                    if isinstance(stored, Decimal) and isinstance(written, Decimal):
                        merged[column] = pick(stored, written)
            unique[key] = merged
        return unique
