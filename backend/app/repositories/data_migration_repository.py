from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.database import DbSession
from app.models import DataMigration

_LOCK_KEY = "data_migration:{name}"


class DataMigrationRepository:
    """Completion markers of one-off data migrations and the lock that keeps replicas from running one twice."""

    def is_completed(self, db: DbSession, name: str) -> bool:
        return db.get(DataMigration, name) is not None

    def mark_completed(self, db: DbSession, name: str) -> None:
        db.execute(insert(DataMigration).values(name=name).on_conflict_do_nothing())

    def try_lock(self, db: DbSession, name: str) -> bool:
        """Session-level lock, held across the migration's own commits until unlock."""
        statement = text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))")
        return bool(db.execute(statement, {"key": _LOCK_KEY.format(name=name)}).scalar())

    def unlock(self, db: DbSession, name: str) -> None:
        db.execute(text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"), {"key": _LOCK_KEY.format(name=name)})
