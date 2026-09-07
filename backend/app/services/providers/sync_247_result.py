"""Normalized result of a provider 24/7 sync.

Every provider's ``load_and_save_all`` returns a :class:`Sync247Result`: one
:class:`DataTypeOutcome` per data type it attempted, plus run-level aggregates.
Providers build it through :class:`Sync247Run`, whose ``step`` context manager
carries the per-data-type isolation (log, roll back, mark failed, keep going)
that every provider used to hand-roll.

Rows written are reported as :class:`WriteCounts` wherever the write path knows
the new-vs-updated split, and as a plain int where it doesn't — ``inserted`` /
``updated`` aggregate only the known splits, so a provider that can't report one
yet shows up as unsplit rather than as zero new rows.
"""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured


class Sync247Status(StrEnum):
    """Per-data-type outcome of a 24/7 sync."""

    OK = "ok"
    PARTIAL = "partial"  # some records written, some attempts failed
    FAILED = "failed"  # attempted, nothing written
    SKIPPED = "skipped"  # not attempted (unsupported, or nothing to fetch)


@dataclass(frozen=True, slots=True)
class DataTypeOutcome:
    """What happened for a single data type.

    ``status`` is derived from the counters rather than set by hand, so a
    provider only has to report what it did.
    """

    rows_written: int = 0
    counts: WriteCounts | None = None  # new-vs-updated split, when the write path reports one
    skipped: int = 0  # records deliberately not persisted (duplicates, unusable payloads)
    truncated: bool = False  # fetch stopped early (page cap / rate limit) — window is incomplete
    errors: tuple[str, ...] = ()
    attempted: bool = True
    reason: str | None = None  # why a data type was skipped

    @property
    def status(self) -> Sync247Status:
        if not self.attempted:
            return Sync247Status.SKIPPED
        if not self.errors:
            return Sync247Status.OK
        return Sync247Status.PARTIAL if self.rows_written else Sync247Status.FAILED

    @property
    def error(self) -> str | None:
        """First error seen, the representative one for logs and the sync log."""
        return self.errors[0] if self.errors else None

    def as_dict(self) -> dict[str, Any]:
        """Compact payload for the sync log — default-valued fields are omitted."""
        payload: dict[str, Any] = {"status": self.status.value, "rows_written": self.rows_written}
        if self.counts is not None:
            payload["inserted"] = self.counts.inserted
            payload["updated"] = self.counts.updated
        if self.skipped:
            payload["skipped"] = self.skipped
        if self.truncated:
            payload["truncated"] = True
        if self.errors:
            payload["error"] = self.errors[0]
            if len(self.errors) > 1:
                payload["error_count"] = len(self.errors)
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass
class Sync247Result(Mapping[str, int]):
    """Outcome of one 24/7 sync, keyed by the provider's own data type names.

    Behaves as a ``Mapping[str, int]`` of data type -> rows written, so results
    stay spreadable into logs (``**result``) and comparable in tests. Callers
    that need the new-vs-updated split read :attr:`inserted` / :attr:`updated`
    instead of probing individual values for attributes.
    """

    provider: str
    outcomes: dict[str, DataTypeOutcome] = field(default_factory=dict)
    note: str | None = None  # free-text run-level remark (e.g. "data arrives via webhooks")

    # -- recording -------------------------------------------------------------

    def record(
        self,
        data_type: str,
        rows_written: WriteCounts | int = 0,
        *,
        skipped: int = 0,
        truncated: bool = False,
    ) -> None:
        """Record a successful write, replacing anything previously recorded for the type."""
        self.outcomes[data_type] = DataTypeOutcome(
            rows_written=int(rows_written),
            counts=rows_written if isinstance(rows_written, WriteCounts) else None,
            skipped=skipped,
            truncated=truncated,
            errors=self.outcomes[data_type].errors if data_type in self.outcomes else (),
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
        current = self.outcomes.get(data_type, DataTypeOutcome(rows_written=0))
        counts = current.counts
        if isinstance(rows_written, WriteCounts):
            counts = WriteCounts(
                (counts.inserted if counts else 0) + rows_written.inserted,
                (counts.updated if counts else 0) + rows_written.updated,
            )
        self.outcomes[data_type] = replace(
            current,
            rows_written=current.rows_written + int(rows_written),
            counts=counts,
            skipped=current.skipped + skipped,
            truncated=current.truncated or truncated,
            attempted=True,
        )

    def fail(self, data_type: str, error: BaseException | str) -> None:
        """Mark an attempt at ``data_type`` as failed, keeping any rows already written."""
        current = self.outcomes.get(data_type, DataTypeOutcome())
        self.outcomes[data_type] = replace(current, errors=(*current.errors, str(error)), attempted=True)

    def skip(self, data_type: str, reason: str | None = None) -> None:
        """Mark a data type as not attempted (unsupported, or no window to fetch)."""
        self.outcomes[data_type] = DataTypeOutcome(attempted=False, reason=reason)

    # -- aggregates ------------------------------------------------------------

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
    def split_complete(self) -> bool:
        """True when every data type that wrote rows reported its new-vs-updated split."""
        return all(o.counts is not None for o in self.outcomes.values() if o.rows_written)

    @property
    def synced(self) -> tuple[str, ...]:
        return tuple(k for k, o in self.outcomes.items() if o.status is Sync247Status.OK)

    @property
    def failures(self) -> dict[str, str]:
        """Data type -> representative error, for types that failed outright or partially."""
        return {
            k: o.error
            for k, o in self.outcomes.items()
            if o.error and o.status in (Sync247Status.FAILED, Sync247Status.PARTIAL)
        }

    @property
    def truncated(self) -> tuple[str, ...]:
        """Data types whose fetch stopped early, so the window is incomplete."""
        return tuple(k for k, o in self.outcomes.items() if o.truncated)

    @property
    def all_failed(self) -> bool:
        """Every attempted data type failed — the run is a failure, not an empty success."""
        attempted = [o for o in self.outcomes.values() if o.attempted]
        return bool(attempted) and all(o.status is Sync247Status.FAILED for o in attempted)

    @property
    def any_failed(self) -> bool:
        return any(o.errors for o in self.outcomes.values() if o.attempted)

    def as_dict(self) -> dict[str, Any]:
        """Payload for the sync log / API response — flat, JSON-safe, no provider-private keys."""
        payload: dict[str, Any] = {
            "provider": self.provider,
            "rows_written": self.rows_written,
            "types": {k: o.as_dict() for k, o in self.outcomes.items()},
        }
        if self.inserted or self.updated:
            payload["inserted"] = self.inserted
            payload["updated"] = self.updated
        if self.truncated:
            payload["truncated"] = list(self.truncated)
        if self.note:
            payload["note"] = self.note
        return payload

    # -- Mapping ---------------------------------------------------------------

    def __getitem__(self, data_type: str) -> int:
        return self.outcomes[data_type].rows_written

    def __iter__(self) -> Iterator[str]:
        return iter(self.outcomes)

    def __len__(self) -> int:
        return len(self.outcomes)

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
    """Builds a :class:`Sync247Result`, isolating failures to one data type at a time.

    ``fatal`` exception types propagate instead of being recorded — use it for
    errors that invalidate the whole run (an expired token, say) rather than one
    data type.
    """

    def __init__(
        self,
        provider: str,
        db: DbSession,
        user_id: UUID,
        logger: logging.Logger,
        *,
        task: str = "load_and_save_all",
        fatal: tuple[type[BaseException], ...] = (),
    ) -> None:
        self.result = Sync247Result(provider=provider)
        self.db = db
        self.user_id = user_id
        self.logger = logger
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
    ) -> Iterator[Sync247Step]:
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
        try:
            if savepoint:
                with self.db.begin_nested():
                    yield step
            else:
                yield step
            # Commit before recording: a failed commit wrote nothing, so the outcome must
            # come out FAILED rather than a success carrying rows that never landed.
            if commit:
                self.db.commit()
            writer = self.result.add if accumulate else self.result.record
            writer(data_type, step.rows_written, skipped=step.skipped, truncated=step.truncated)
        except self.fatal:
            raise
        except Exception as e:
            if rollback_on_error is None:
                rollback_on_error = not savepoint
            if rollback_on_error:
                self.db.rollback()
            self.fail(data_type, e, capture=capture)
            return

    def expect(self, *data_types: str) -> None:
        """Declare the data types this run covers, before any of them is attempted.

        Keeps the result shape stable across runs for providers whose steps are
        conditional: a type nothing was fetched for stays in the result as
        SKIPPED instead of vanishing from it.
        """
        for data_type in data_types:
            self.result.skip(data_type, "nothing to sync in window")

    def fail(self, data_type: str, error: Exception, *, capture: bool = False) -> None:
        """Record and log a failure outside a ``step`` — e.g. a shared fetch feeding several types."""
        self.result.fail(data_type, error)
        message = f"Failed to sync {data_type} data: {error}"
        extra = {
            "provider": self.result.provider,
            "task": self.task,
            "data_type": data_type,
            "user_id": str(self.user_id),
        }
        if capture:
            log_and_capture_error(error, self.logger, message, extra=extra)
        else:
            log_structured(self.logger, "error", message, **extra)

    def log_summary(self, **extra: Any) -> None:
        """Emit one structured line summarizing the run."""
        log_structured(
            self.logger,
            "info",
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
