from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.responses.upload import Sync247Summary, Sync247TaskSummary
from app.schemas.sync_status import SyncStatus
from app.services.sync_status_service import run_status_from
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)


class SwallowedWriteError(Exception):
    """A write in a step failed and the provider code caught it, leaving the session unusable."""


def error_code_of(error: BaseException) -> str:
    """A short, value-free label for an error: the HTTP status when it has one, else its type.

    The exception text is left out: a database error carries the rows it failed on.
    """
    status_code = getattr(error, "status_code", None) or getattr(getattr(error, "response", None), "status_code", None)
    return f"http_{status_code}" if isinstance(status_code, int) else type(error).__name__


@dataclass(frozen=True, slots=True)
class Sync247TaskOutcome:
    """What one provider fetch task did; its status follows from the counters."""

    rows_written: int = 0
    counts: WriteCounts | None = None  # new-vs-updated split, when the write path reports one
    skipped: int = 0  # records deliberately not persisted (duplicates, unusable payloads)
    truncated: bool = False  # fetch stopped early (page cap / rate limit) — window is incomplete
    error_codes: tuple[str, ...] = ()
    attempted: bool = True

    @property
    def status(self) -> SyncStatus:
        if not self.attempted:
            return SyncStatus.SKIPPED
        if not self.error_codes:
            return SyncStatus.SUCCESS if self.rows_written else SyncStatus.SKIPPED
        return SyncStatus.PARTIAL if self.rows_written else SyncStatus.FAILED

    @property
    def error_code(self) -> str | None:
        return self.error_codes[0] if self.error_codes else None

    def summary(self) -> Sync247TaskSummary:
        split = self.counts
        return Sync247TaskSummary(
            status=self.status,
            items_inserted=split.inserted if split is not None else None,
            items_updated=split.updated if split is not None else None,
            items_reported=self.rows_written if split is None and self.attempted else None,
            items_skipped=self.skipped,
            truncated=self.truncated,
            error_code=self.error_code,
        )


@dataclass
class Sync247Result:
    """Outcome of one 24/7 sync, keyed by the provider's own task names.

    inserted/updated add up only the tasks that report the new-vs-updated split.
    """

    provider: str
    outcomes: dict[str, Sync247TaskOutcome] = field(default_factory=dict)

    def record(
        self,
        data_type: str,
        rows_written: WriteCounts | int = 0,
        *,
        skipped: int = 0,
        truncated: bool = False,
    ) -> None:
        """Record a successful write, replacing the counters recorded for the type so far."""
        self.outcomes[data_type] = replace(
            self._current(data_type),
            rows_written=int(rows_written),
            counts=rows_written if isinstance(rows_written, WriteCounts) else None,
            skipped=skipped,
            truncated=truncated,
            attempted=True,
        )

    def add(
        self,
        data_type: str,
        rows_written: WriteCounts | int = 0,
        *,
        skipped: int = 0,
        truncated: bool = False,
    ) -> None:
        """Accumulate into a data type — for providers that sync one chunk (e.g. day) at a time."""
        current = self._current(data_type)
        # The split stays known only while every chunk that wrote rows reported one.
        counts = current.counts
        split_known = counts is not None or not current.rows_written
        if isinstance(rows_written, WriteCounts) and split_known:
            counts = rows_written if counts is None else counts + rows_written
        elif rows_written:
            counts = None
        self.outcomes[data_type] = replace(
            current,
            rows_written=current.rows_written + int(rows_written),
            counts=counts,
            skipped=current.skipped + skipped,
            truncated=current.truncated or truncated,
            attempted=True,
        )

    def fail(self, data_type: str, error: BaseException) -> None:
        """Mark an attempt at ``data_type`` as failed, keeping any rows already written."""
        current = self._current(data_type)
        self.outcomes[data_type] = replace(
            current, error_codes=(*current.error_codes, error_code_of(error)), attempted=True
        )

    def skip(self, data_type: str) -> None:
        """Mark a data type as not attempted (unsupported, or no window to fetch)."""
        self.outcomes[data_type] = Sync247TaskOutcome(attempted=False)

    def _current(self, data_type: str) -> Sync247TaskOutcome:
        return self.outcomes.get(data_type, Sync247TaskOutcome())

    @property
    def rows_written(self) -> int:
        """Total rows persisted across all data types."""
        return sum(o.rows_written for o in self.outcomes.values())

    @property
    def inserted(self) -> int:
        """New rows, summed over the data types that report a split."""
        return sum(o.counts.inserted for o in self.outcomes.values() if o.counts is not None)

    @property
    def updated(self) -> int:
        """Rows refreshed in place, summed over the data types that report a split."""
        return sum(o.counts.updated for o in self.outcomes.values() if o.counts is not None)

    @property
    def synced(self) -> tuple[str, ...]:
        return tuple(k for k, o in self.outcomes.items() if o.attempted and not o.error_codes)

    @property
    def failures(self) -> dict[str, str]:
        """Data type -> its first error code, for types that failed outright or partially."""
        return {k: o.error_code for k, o in self.outcomes.items() if o.error_code is not None}

    @property
    def truncated(self) -> tuple[str, ...]:
        """Data types whose fetch stopped early, so the window is incomplete."""
        return tuple(k for k, o in self.outcomes.items() if o.truncated)

    @property
    def all_failed(self) -> bool:
        """The run failed by the same rule as ``summary().status`` — not an empty success."""
        return run_status_from(self.outcomes.values()) is SyncStatus.FAILED

    def summary(self) -> Sync247Summary:
        outcomes = list(self.outcomes.values())
        split = [o.counts for o in outcomes if o.counts is not None]
        unsplit = [o.rows_written for o in outcomes if o.counts is None and o.attempted]
        return Sync247Summary(
            status=run_status_from(outcomes) if outcomes else SyncStatus.SKIPPED,
            items_inserted=sum(c.inserted for c in split) if split else None,
            items_updated=sum(c.updated for c in split) if split else None,
            items_reported=sum(unsplit) if unsplit else None,
            tasks={k: o.summary() for k, o in self.outcomes.items()},
        )

    def __repr__(self) -> str:
        body = ", ".join(f"{k}={o.rows_written}({o.status.value})" for k, o in self.outcomes.items())
        return f"Sync247Result({self.provider}: {body or 'no data types'})"


class Sync247Step:
    """Handle passed to a ``Sync247Run.step`` body so it can report what it wrote."""

    __slots__ = ("rows_written", "skipped", "truncated")

    def __init__(self) -> None:
        self.rows_written: WriteCounts | int = 0
        self.skipped: int = 0
        self.truncated: bool = False

    def record(self, rows_written: WriteCounts | int, *, skipped: int = 0, truncated: bool = False) -> None:
        self.rows_written = rows_written
        self.skipped = skipped
        self.truncated = truncated


class Sync247Run:
    """Builds a Sync247Result, isolating failures to one task at a time.

    ``fatal`` exceptions propagate instead of being recorded: errors that end the whole
    run, such as an expired token.
    """

    def __init__(
        self,
        provider: str,
        db: DbSession,
        user_id: UUID,
        *,
        task: str = "load_and_save_all",
        fatal: tuple[type[BaseException], ...] = (),
    ) -> None:
        self.result = Sync247Result(provider=provider)
        self.db = db
        self.user_id = user_id
        self.task = task
        self.fatal = fatal

    @contextmanager
    def step(
        self,
        data_type: str,
        *,
        commit: bool = False,
        rollback_on_error: bool | None = None,
        savepoint: bool = False,
        capture: bool = False,
        accumulate: bool = False,
    ) -> Generator[Sync247Step]:
        """Run one data type's fetch + save, recording the outcome either way.

        commit: commit the session after a successful body.
        savepoint: wrap the body in a nested transaction so a failed write rolls
            back only this data type and leaves the session usable. Implies no
            full rollback on error, since the savepoint already undid the write.
        capture: also report failures to Sentry.
        accumulate: add to any counts already recorded for the type instead of
            replacing them (for providers that loop over chunks of the window).
        """
        step = Sync247Step()
        save = self.result.add if accumulate else self.result.record
        try:
            if savepoint:
                with self.db.begin_nested():
                    yield step
            else:
                yield step
            if not self.db.is_active:
                # Rows the body committed before the failure stay counted; the rest is rolled back.
                self.db.rollback()
                if not commit:
                    save(data_type, step.rows_written, skipped=step.skipped, truncated=step.truncated)
                self.fail(data_type, SwallowedWriteError(), capture=capture)
                return
            # Commit before recording: a failed commit wrote nothing, so the outcome must
            # come out FAILED rather than a success carrying rows that never landed.
            if commit:
                self.db.commit()
            save(data_type, step.rows_written, skipped=step.skipped, truncated=step.truncated)
        except self.fatal:
            raise
        except Exception as e:
            if rollback_on_error is None:
                rollback_on_error = not savepoint
            # An inactive session (failed flush/commit, savepoint never opened) must be reset regardless.
            if rollback_on_error or not self.db.is_active:
                self.db.rollback()
            self.fail(data_type, e, capture=capture)
            return

    def expect(self, *data_types: str) -> None:
        """List the tasks up front, so a conditional one that never ran shows as skipped."""
        for data_type in data_types:
            self.result.skip(data_type)

    def fail(self, data_type: str, error: Exception, *, capture: bool = False) -> None:
        """Record and log a failure outside a ``step`` — e.g. a shared fetch feeding several types."""
        self.result.fail(data_type, error)
        # The error's text stays out: a database error carries the rows it failed on.
        logger.error(
            "Failed to sync data type",
            exc_info=error if capture else None,
            provider=self.result.provider,
            task=self.task,
            data_type=data_type,
            user_id=str(self.user_id),
            error_code=error_code_of(error),
        )

    def log_summary(self, **extra: Any) -> None:
        """Emit one structured line summarizing the run."""
        logger.info(
            f"{self.result.provider} 24/7 sync complete",
            provider=self.result.provider,
            task=self.task,
            user_id=str(self.user_id),
            rows_written=self.result.rows_written,
            inserted=self.result.inserted,
            updated=self.result.updated,
            synced=list(self.result.synced),
            failures=self.result.failures or None,
            truncated=list(self.result.truncated) or None,
            **extra,
        )
