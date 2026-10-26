"""One-off copy of the history into the aggregate tables, run by Celery step by step within a time budget."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from logging import getLogger
from typing import cast
from uuid import UUID

from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.repositories.aggregate_backfill_repository import AggregateBackfillRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.schemas.enums import ProviderName, SeriesType
from app.utils.structured_logging import log_structured

# Set once every step is done; retention and the later cleanup wait for it.
BACKFILL_MIGRATION = "aggregate_backfill"

_CURSOR_KEY = "aggregate_backfill:cursor:{step}"
_SOURCES_PER_QUERY = 50
_FIRST = UUID(int=0)

logger = getLogger(__name__)


@dataclass(frozen=True)
class BackfillStep:
    name: str
    # Returns True once the step is done, False when the deadline (a time.monotonic() value) came first.
    run: Callable[[DbSession, float], bool]


class AggregateBackfillService:
    """Steps run in order, each recorded in data_migration when done. A step that runs out of time keeps its place
    in Redis (the last data source it finished) and the next run goes on from there. Every step is safe to repeat,
    except the Suunto speed fix, which commits together with its completion marker."""

    def __init__(self) -> None:
        self.repo = AggregateBackfillRepository()
        self.migrations = DataMigrationRepository()

    @property
    def steps(self) -> list[BackfillStep]:
        return [
            BackfillStep("suunto_speed", self._suunto_speed),
            BackfillStep("workout_details", self._workout_details),
            BackfillStep("garmin_epoch_windows", self._garmin_epoch_windows),
            BackfillStep("archive_days", self._archive_days),
        ]

    def is_done(self, db: DbSession) -> bool:
        """Every step done: a step a later release adds still runs where the earlier ones finished long ago."""
        return all(self.migrations.is_completed(db, f"{BACKFILL_MIGRATION}:{step.name}") for step in self.steps)

    def run(self, db: DbSession, budget_seconds: float) -> bool:
        """Run the pending steps until all are done (True) or the budget is spent (False)."""
        deadline = time.monotonic() + budget_seconds
        for step in self.steps:
            name = f"{BACKFILL_MIGRATION}:{step.name}"
            if self.migrations.is_completed(db, name):
                continue
            started = time.monotonic()
            done = step.run(db, deadline)
            log_structured(
                logger,
                "info",
                f"Aggregate backfill: {step.name} {'done' if done else 'paused'}",
                step=step.name,
                seconds=round(time.monotonic() - started, 1),
            )
            if not done:
                return False
            self.migrations.mark_completed(db, name)
            db.commit()
        self.migrations.mark_completed(db, BACKFILL_MIGRATION)
        db.commit()
        return True

    def _suunto_speed(self, db: DbSession, _deadline: float) -> bool:
        # Not committed here: run() commits it with the step's marker, so it can never apply twice.
        self.repo.divide_suunto_speed(db)
        return True

    def _workout_details(self, db: DbSession, deadline: float) -> bool:
        energy_series = _workout_energy_series()

        def mirror(source: tuple[UUID, str]) -> bool:
            source_id, provider = source
            self.repo.mirror_workout_details(db, source_id, energy_series.get(ProviderName(provider)))
            return True

        return self._each_source(db, deadline, "workout_details", self.repo.sources_with_workouts, mirror)

    def _garmin_epoch_windows(self, db: DbSession, deadline: float) -> bool:
        # Imported here: the providers package pulls in the Celery tasks, which import this module.
        from app.services.providers.garmin.coverage import EPOCHS_SERIES

        epoch_types = list(EPOCHS_SERIES.values())

        def widen(source_id: UUID) -> bool:
            while time.monotonic() < deadline:
                if not self.repo.set_garmin_epoch_windows(db, source_id, epoch_types):
                    return True
                db.commit()
            return False

        return self._each_source(db, deadline, "garmin_epoch_windows", self.repo.garmin_sources, widen)

    def _archive_days(self, db: DbSession, deadline: float) -> bool:
        def copy(source_id: UUID) -> bool:
            self.repo.copy_archive_days(db, source_id)
            return True

        return self._each_source(db, deadline, "archive_days", self.repo.archive_sources, copy)

    def _each_source[S](
        self,
        db: DbSession,
        deadline: float,
        step: str,
        sources: Callable[[DbSession, UUID, int], list[S]],
        handle: Callable[[S], bool],
    ) -> bool:
        """Hand each data source to ``handle`` in id order, committing after each, from where the last run stopped."""
        key = _CURSOR_KEY.format(step=step)
        redis = get_redis_client()
        after = UUID(cast(str, redis.get(key))) if redis.get(key) else _FIRST
        while time.monotonic() < deadline:
            batch = sources(db, after, _SOURCES_PER_QUERY)
            if not batch:
                redis.delete(key)
                return True
            for source in batch:
                if not handle(source):
                    db.rollback()
                    return False
                db.commit()
                after = source[0] if isinstance(source, tuple) else cast(UUID, source)
                redis.set(key, str(after))
                if time.monotonic() >= deadline:
                    return False
        return False


def _workout_energy_series() -> dict[ProviderName, SeriesType]:
    """The providers whose workout energy has an established series, as their coverage declares it."""
    # Imported here: the providers package pulls in the Celery tasks, which import this module.
    from app.services.providers.garmin.coverage import WORKOUT_ENERGY_SERIES as GARMIN
    from app.services.providers.google_health.coverage import WORKOUT_ENERGY_SERIES as GOOGLE_HEALTH
    from app.services.providers.whoop.coverage import WORKOUT_ENERGY_SERIES as WHOOP
    from app.services.providers.withings.coverage import WORKOUT_ENERGY_SERIES as WITHINGS

    return {
        ProviderName.GARMIN: GARMIN,
        ProviderName.GOOGLE_HEALTH: GOOGLE_HEALTH,
        ProviderName.WHOOP: WHOOP,
        ProviderName.WITHINGS: WITHINGS,
    }


aggregate_backfill_service = AggregateBackfillService()
