from collections.abc import Callable

from app.database import DbSession
from app.repositories.data_migration_repository import DataMigrationRepository


class DataMigrationService:
    """Runs one-off data migration scripts at most once per instance.

    The scripts run at startup and report on stdout, so this prints rather than logs.
    """

    def __init__(self) -> None:
        self.repo = DataMigrationRepository()

    def run(self, db: DbSession, name: str, migrate: Callable[[], bool], *, dry_run: bool = False) -> None:
        """Run migrate unless it already completed here or another instance is running it.

        migrate returns True when it ran cleanly; only then is the migration recorded, so a failed
        or interrupted run is retried on the next startup. The session must stay on one connection,
        since the lock belongs to it.
        """
        if self.repo.is_completed(db, name):
            print(f"{name}: already completed, skipping.")
            return
        if dry_run:
            migrate()
            return
        if not self.repo.try_lock(db, name):
            print(f"{name}: running on another instance, skipping.")
            return
        try:
            # Another instance may have finished between the check above and taking the lock
            if self.repo.is_completed(db, name):
                print(f"{name}: already completed, skipping.")
                return
            if migrate():
                self.repo.mark_completed(db, name)
                db.commit()
        finally:
            db.rollback()
            self.repo.unlock(db, name)
            db.commit()


data_migration_service = DataMigrationService()
