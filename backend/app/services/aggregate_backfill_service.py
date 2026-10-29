"""One-off copy of the history into the aggregate tables, run by Celery step by step within a time budget."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from logging import getLogger
from typing import cast
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.database import DbSession
from app.integrations import rollup_queue
from app.integrations.redis_client import get_redis_client
from app.repositories.aggregate_backfill_repository import SKIPPED_SOURCE, AggregateBackfillRepository
from app.repositories.archival_repository import ArchivalSettingRepository, DataPointSeriesArchiveRepository
from app.repositories.data_migration_repository import DataMigrationRepository
from app.repositories.local_day import utc_midnight
from app.repositories.series_rollup_repository import SeriesRollupRepository
from app.schemas.enums import ProviderName, SeriesType
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

# Set once every step is done; retention and the later cleanup wait for it.
BACKFILL_MIGRATION = "aggregate_backfill"

# The span the backfill fills before the rest of the history.
RECENT = timedelta(days=30)
# Days rolled up per statement and commit: a month of 1 Hz data is a few million rows.
ROLLUP_CHUNK_DAYS = 31
# Our day and session rows from the history's samples: off until a release decides to run it; the summaries
# count those days from the samples meanwhile, and a step added later runs where the others are long done.
ROLL_UP_HISTORY = False

_CURSOR_KEY = "aggregate_backfill:cursor:{step}"
_SOURCES_PER_QUERY = 50
# The span of one source's workouts or archive one statement covers, so none grows with the history's length.
_WINDOW_DAYS = 365
_FIRST = UUID(int=0)

logger = getLogger(__name__)


@dataclass(frozen=True)
class Budget:
    """A run stops once its time is up or its lock is no longer its own."""

    deadline: float
    keep_alive: Callable[[], bool]

    def spent(self) -> bool:
        return time.monotonic() >= self.deadline or not self.keep_alive()


@dataclass(frozen=True)
class BackfillStep:
    name: str
    # Returns True once the step is done, False when the budget ran out first.
    run: Callable[[DbSession, Budget], bool]


class AggregateBackfillService:
    """Steps run in order, each recorded in data_migration when done. A step that runs out of time keeps its place
    in Redis (the last data source it finished, and within it the last window of time) and the next run goes on from
    there. Every statement is bounded, a batch or one source's window of time, and safe to repeat."""

    def __init__(self) -> None:
        self.repo = AggregateBackfillRepository()
        self.samples = DataPointSeriesArchiveRepository()
        self.rollup_repo = SeriesRollupRepository()
        self.migrations = DataMigrationRepository()

    @property
    def steps(self) -> list[BackfillStep]:
        return [
            BackfillStep("suunto_speed", self._suunto_speed),
            BackfillStep("workout_details", self._workout_details),
            # The last month first: those are the days clients look at, so they come back before the rest.
            BackfillStep("history_recent", self._history(RECENT)),
            *([BackfillStep("rollup_recent", self._rollup(RECENT))] if ROLL_UP_HISTORY else []),
            BackfillStep("history_all", self._history(None)),
            *([BackfillStep("rollup_all", self._rollup(None))] if ROLL_UP_HISTORY else []),
            BackfillStep("garmin_epoch_windows", self._garmin_epoch_windows),
            BackfillStep("archive_days", self._archive_days),
        ]

    def is_done(self, db: DbSession) -> bool:
        """Every step done: a step a later release adds still runs where the earlier ones finished long ago."""
        return all(self.migrations.is_completed(db, f"{BACKFILL_MIGRATION}:{step.name}") for step in self.steps)

    def run(self, db: DbSession, budget_seconds: float, keep_alive: Callable[[], bool] = lambda: True) -> bool:
        """Run the pending steps until all are done (True) or the budget is spent (False); ``keep_alive`` extends
        the caller's lock and says whether it still holds it."""
        budget = Budget(time.monotonic() + budget_seconds, keep_alive)
        for step in self.steps:
            name = f"{BACKFILL_MIGRATION}:{step.name}"
            if self.migrations.is_completed(db, name):
                continue
            started = time.monotonic()
            done = step.run(db, budget)
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

    def _suunto_speed(self, db: DbSession, budget: Budget) -> bool:
        def divide(source_id: UUID) -> bool:
            while self.repo.divide_suunto_speed(db, source_id):
                db.commit()
                if budget.spent():
                    return False
            return True

        def sources(db: DbSession, after: UUID, limit: int) -> list[UUID]:
            return self.repo.provider_sources(db, ProviderName.SUUNTO, after, limit)

        return self._each_source(db, budget, "suunto_speed", sources, divide)

    def _workout_details(self, db: DbSession, budget: Budget) -> bool:
        energy_series = _workout_energy_series()

        def mirror(source: tuple[UUID, str]) -> bool:
            source_id, provider = source
            energy = energy_series.get(ProviderName(provider))
            first = self.repo.first_workout(db, source_id)

            def window(lo: datetime, hi: datetime) -> None:
                self.repo.mirror_workout_details(db, source_id, energy, lo, hi)

            return self._each_window(db, budget, "workout_details", source_id, first, window)

        return self._each_source(db, budget, "workout_details", self.repo.sources_with_workouts, mirror)

    def _history(self, period: timedelta | None) -> Callable[[DbSession, Budget], bool]:
        """Day and session values stored as samples before the aggregate tables, from the last ``period`` or all."""

        step = "history_recent" if period is not None else "history_all"

        def run(db: DbSession, budget: Budget) -> bool:
            def copy(source: tuple[UUID, str]) -> bool:
                source_id, provider = source
                first = self.samples.earliest_sample(db, source_id)
                if first is not None and period is not None:
                    first = max(first, datetime.now(timezone.utc) - period)

                def window(lo: datetime, hi: datetime) -> None:
                    self.repo.copy_history_values(db, source_id, provider, lo.date(), hi.date())

                return self._each_window(db, budget, step, source_id, first, window)

            return self._each_source(db, budget, step, self.repo.history_sources, copy)

        return run

    def _rollup(self, period: timedelta | None) -> Callable[[DbSession, Budget], bool]:
        """Our day and session rows from every source's samples, from the last ``period`` or all, newest days
        first, ROLLUP_CHUNK_DAYS calendar days at a time; a source left halfway goes on from its last finished
        chunk."""
        step = "rollup_recent" if period is not None else "rollup_all"
        day_key = _CURSOR_KEY.format(step=f"{step}:day")

        def run(db: DbSession, budget: Budget) -> bool:
            since = (datetime.now(timezone.utc) - period).date() if period is not None else None
            frozen_before = ArchivalSettingRepository().get(db).deleted_before
            redis = get_redis_client()
            self._roll_up_live_days(db)

            def roll_up(source_id: UUID) -> bool:
                saved = cast(str | None, redis.get(day_key))
                done_before = (
                    date.fromisoformat(saved.split("|")[1]) if saved and saved.startswith(f"{source_id}|") else None
                )
                first = self.samples.earliest_sample(db, source_id)
                if first is None:
                    return True
                # Every calendar day from the first sample's on: a day without samples costs one index probe, where
                # listing the days that have some read the source's whole history.
                start = max(first.date() - timedelta(days=1), since or date.min)
                end = done_before or _past_today()
                days = [start + timedelta(days=n) for n in range((end - start).days)]
                for chunk in _newest_first(days, ROLLUP_CHUNK_DAYS):
                    # Under the scheduled rollup's lock, a chunk at a time.
                    if budget.spent() or (token := rollup_queue.take_lock()) is None:
                        return False
                    try:
                        self.rollup_repo.roll_up(db, source_id, chunk, frozen_before)
                        db.commit()
                    finally:
                        rollup_queue.release_lock(token)
                    redis.set(day_key, f"{source_id}|{min(chunk).isoformat()}")
                redis.delete(day_key)
                return True

            return self._each_source(db, budget, step, self.rollup_repo.sources, roll_up)

        return run

    def _roll_up_live_days(self, db: DbSession) -> None:
        """The days live writes queued, rolled up here: between two chunks the scheduled rollup, trying once every
        15 minutes, hardly ever finds its lock free."""
        # Imported here: the archival service imports this module.
        from app.services.archival_service import archival_service

        token = rollup_queue.take_lock()
        if token is None:
            return
        try:
            archival_service.roll_up_queued_days(db)
        except SoftTimeLimitExceeded:
            raise
        except Exception as exc:
            db.rollback()
            log_and_capture_error(exc, logger, "Aggregate backfill: the queued days failed; the backfill goes on")
        finally:
            rollup_queue.release_lock(token)

    def _garmin_epoch_windows(self, db: DbSession, budget: Budget) -> bool:
        # Imported here: the providers package pulls in the Celery tasks, which import this module.
        from app.services.providers.garmin.coverage import EPOCHS_SERIES

        epoch_types = list(EPOCHS_SERIES.values())

        def widen(source_id: UUID) -> bool:
            for series_type in epoch_types:
                after: datetime | None = datetime.min.replace(tzinfo=timezone.utc)
                while after is not None:
                    after = self.repo.set_garmin_epoch_windows(db, source_id, series_type, after)
                    db.commit()
                    if budget.spent():
                        return False
            return True

        def sources(db: DbSession, after: UUID, limit: int) -> list[UUID]:
            return self.repo.provider_sources(db, ProviderName.GARMIN, after, limit)

        return self._each_source(db, budget, "garmin_epoch_windows", sources, widen)

    def _archive_days(self, db: DbSession, budget: Budget) -> bool:
        def copy(source_id: UUID) -> bool:
            def window(lo: datetime, hi: datetime) -> None:
                self.repo.copy_archive_days(db, source_id, lo, hi)

            return self._each_window(
                db, budget, "archive_days", source_id, self.repo.first_archived(db, source_id), window
            )

        return self._each_source(db, budget, "archive_days", self.repo.archive_sources, copy)

    def _each_window(
        self,
        db: DbSession,
        budget: Budget,
        step: str,
        source_id: UUID,
        first: datetime | None,
        handle: Callable[[datetime, datetime], None],
    ) -> bool:
        """Hand ``handle`` the source's time from ``first`` to now in windows of _WINDOW_DAYS, newest first, committing
        after each; a source left halfway goes on below its last finished window."""
        if first is None:
            return True
        key = _CURSOR_KEY.format(step=f"{step}:window")
        redis = get_redis_client()
        saved = cast(str | None, redis.get(key))
        end = date.fromisoformat(saved.split("|")[1]) if saved and saved.startswith(f"{source_id}|") else _past_today()
        while end > first.date():
            if budget.spent():
                return False
            start = max(first.date(), end - timedelta(days=_WINDOW_DAYS))
            handle(utc_midnight(start), utc_midnight(end))
            db.commit()
            redis.set(key, f"{source_id}|{start.isoformat()}")
            end = start
        redis.delete(key)
        return True

    def _each_source[S](
        self,
        db: DbSession,
        budget: Budget,
        step: str,
        sources: Callable[[DbSession, UUID, int], list[S]],
        handle: Callable[[S], bool],
    ) -> bool:
        """Hand each data source to ``handle`` in id order, committing after each, from where the last run stopped."""
        key = _CURSOR_KEY.format(step=step)
        redis = get_redis_client()
        after = UUID(cast(str, redis.get(key))) if redis.get(key) else _FIRST
        while not budget.spent():
            batch = sources(db, after, _SOURCES_PER_QUERY)
            if not batch:
                redis.delete(key)
                return True
            for source in batch:
                source_id = source[0] if isinstance(source, tuple) else cast(UUID, source)
                if not self._handle(db, step, source_id, lambda: handle(source)):
                    return False
                after = source_id
                redis.set(key, str(after))
                if budget.spent():
                    return False
        return False

    def _handle(self, db: DbSession, step: str, source_id: UUID, handle: Callable[[], bool]) -> bool:
        """``handle`` committed, or False when it ran out of budget. A source that fails twice is recorded as
        skipped and left behind, so it holds back neither the step nor the others' retention, which keeps its
        samples."""
        for attempt in (1, 2):
            try:
                if not handle():
                    db.rollback()
                    return False
                db.commit()
                return True
            except SoftTimeLimitExceeded:
                raise
            except Exception as exc:
                db.rollback()
                if attempt == 2:
                    log_and_capture_error(exc, logger, f"Aggregate backfill: {step} skips data source {source_id}")
        self.migrations.mark_completed(db, f"{SKIPPED_SOURCE}{source_id}")
        db.commit()
        return True


def _past_today() -> date:
    """A cutoff after every local day that has begun anywhere."""
    return datetime.now(timezone.utc).date() + timedelta(days=2)


def _newest_first(days: list[date], size: int) -> list[list[date]]:
    ordered = sorted(days, reverse=True)
    return [ordered[i : i + size] for i in range(0, len(ordered), size)]


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


def days_from_samples(db: DbSession) -> bool:
    """Until our rollup is on and has reached the history, readers count the days it has not written from the
    samples, as they did before it."""
    if not DataMigrationRepository().is_completed(db, f"{BACKFILL_MIGRATION}:rollup_all"):
        return True
    return not ArchivalSettingRepository().get(db).rollup_enabled


aggregate_backfill_service = AggregateBackfillService()
