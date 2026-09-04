"""`all_sources=True` returns every source's row instead of the priority winner.

The global provider-priority table cannot express a per-user preference — it has
no `user_id` column, and `ProviderPriority` documents itself as "not per-user".
A caller that needs one has no way to reach the losing source's numbers today:
the summaries endpoint returns only the row the global order picked.

These tests pin both directions of the flag, and the ordering guarantee the
cursor depends on once several rows can share a date.
"""

from datetime import date, datetime
from logging import getLogger
from typing import Any
from uuid import uuid4

import pytest

from app.schemas.responses.activity import ActivitySummary
from app.schemas.utils import PaginatedResponse
from app.services.summaries_service import SummariesService, activity_sort_key


@pytest.fixture
def service() -> SummariesService:
    return SummariesService(log=getLogger(__name__))


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _row(day: int, source: str, *, steps: int, device: str | None = None) -> dict[str, Any]:
    """One aggregate row as `get_daily_activity_aggregates` returns it."""
    return {
        "activity_date": date(2026, 1, day),
        "provider": source,
        "source": source,
        "device_model": device,
        "device_type": None,
        "steps_sum": steps,
        "active_energy_sum": float(steps) / 10,
        "basal_energy_sum": None,
        "distance_sum": None,
        "hr_avg": None,
        "hr_max": None,
        "hr_min": None,
    }


def _stub_reads(service: SummariesService, monkeypatch: pytest.MonkeyPatch, rows: list[dict]) -> None:
    """Feed fixed aggregate rows in and stub every other read the builder makes."""
    monkeypatch.setattr(service.data_point_repo, "get_daily_activity_aggregates", lambda *_a, **_k: list(rows))
    monkeypatch.setattr(service, "_merge_archive_activity", lambda *_a, **_k: list(rows))
    monkeypatch.setattr(service.event_record_repo, "get_daily_workout_aggregates", lambda *_a, **_k: [])
    monkeypatch.setattr(service.data_point_repo, "get_daily_active_minutes", lambda *_a, **_k: [])
    monkeypatch.setattr(service.data_point_repo, "get_daily_intensity_minutes", lambda *_a, **_k: [])
    monkeypatch.setattr(service, "_get_user_max_hr", lambda *_a, **_k: 190)


def _call(
    service: SummariesService,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[dict],
    **kwargs: Any,
) -> PaginatedResponse[ActivitySummary]:
    _stub_reads(service, monkeypatch, rows)
    return service.get_activity_summaries(
        db_session=None,
        user_id=uuid4(),
        start_date=_dt("2026-01-01T00:00:00+00:00"),
        end_date=_dt("2026-01-10T00:00:00+00:00"),
        cursor=None,
        limit=50,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# The flag itself
# ---------------------------------------------------------------------------


class TestAllSourcesFlag:
    def test_off_by_default_returns_one_row_per_day(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [_row(1, "garmin", steps=9000), _row(1, "apple", steps=40)]
        # Priority is a DB read; with no session, stub it to the documented
        # behaviour (one winner per date) rather than exercising the table.
        monkeypatch.setattr(service, "_filter_by_priority", lambda _s, _u, r, **_k: [r[0]])

        result = _call(service, monkeypatch, rows)

        assert len(result.data) == 1, "default must stay one row per day"

    def test_on_returns_every_source_for_the_day(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rows = [_row(1, "garmin", steps=9000), _row(1, "apple", steps=40)]

        result = _call(service, monkeypatch, rows, all_sources=True)

        assert len(result.data) == 2, "both sources must survive"
        assert {s.source.provider for s in result.data} == {"garmin", "apple"}

    def test_on_does_not_consult_the_priority_table_at_all(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point: the global order must not get a say."""
        called = False

        def _boom(*_a: Any, **_k: Any) -> list:
            nonlocal called
            called = True
            return []

        monkeypatch.setattr(service, "_filter_by_priority", _boom)
        _call(service, monkeypatch, [_row(1, "garmin", steps=9000)], all_sources=True)

        assert called is False, "all_sources must bypass the global priority filter"

    def test_the_losing_source_keeps_its_own_numbers(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rows must not be merged or summed — each keeps its own values.

        This is the failure that motivated the flag: an iPhone row with no
        activity outranked a Garmin holding the real numbers.
        """
        rows = [_row(1, "apple", steps=40), _row(1, "garmin", steps=9000)]

        result = _call(service, monkeypatch, rows, all_sources=True)

        by_source = {s.source.provider: s for s in result.data}
        assert by_source["garmin"].steps == 9000
        assert by_source["apple"].steps == 40
        assert sum(s.steps or 0 for s in result.data) == 9040, "no row may absorb another's steps"


# ---------------------------------------------------------------------------
# The ordering guarantee the cursor depends on
# ---------------------------------------------------------------------------


class TestCompoundOrdering:
    def test_rows_sharing_a_date_come_back_in_compound_key_order(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`get_daily_activity_aggregates` orders by DATE ONLY.

        That was sufficient while the priority filter collapsed each date to a
        single row. With several rows per date the cursor comparisons use the
        compound key, so an unsorted list makes forward pagination skip records.
        """
        rows = [
            _row(2, "whoop", steps=3),
            _row(1, "garmin", steps=2),
            _row(1, "apple", steps=1),
        ]

        result = _call(service, monkeypatch, rows, all_sources=True)

        keys = [(s.date, s.source.provider or "") for s in result.data]
        assert keys == sorted(keys), "rows must be ordered by (date, source, device)"

    def test_sort_key_matches_the_cursor_key_exactly(self) -> None:
        """The sort and the cursor comparisons share one expression.

        If they ever drift, pagination silently skips rows — so pin the
        normalisation `decode_activity_cursor` applies: a missing device becomes
        the empty string, never None (which would raise on comparison).
        """
        assert activity_sort_key({"activity_date": date(2026, 1, 1), "source": None, "device_model": None}) == (
            date(2026, 1, 1),
            "",
            "",
        )

        assert activity_sort_key({"activity_date": date(2026, 1, 1), "source": "garmin", "device_model": "Fenix"}) == (
            date(2026, 1, 1),
            "garmin",
            "Fenix",
        )

    def test_pagination_over_a_multi_source_day_loses_no_rows(
        self, service: SummariesService, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Page through a day with three sources and see all three, once each."""
        rows = [
            _row(1, "whoop", steps=3),
            _row(1, "garmin", steps=2),
            _row(1, "apple", steps=1),
        ]

        _stub_reads(service, monkeypatch, rows)
        page1 = service.get_activity_summaries(
            db_session=None,
            user_id=uuid4(),
            start_date=_dt("2026-01-01T00:00:00+00:00"),
            end_date=_dt("2026-01-10T00:00:00+00:00"),
            cursor=None,
            limit=2,
            all_sources=True,
        )
        assert len(page1.data) == 2
        assert page1.pagination.has_more is True

        _stub_reads(service, monkeypatch, rows)
        page2 = service.get_activity_summaries(
            db_session=None,
            user_id=uuid4(),
            start_date=_dt("2026-01-01T00:00:00+00:00"),
            end_date=_dt("2026-01-10T00:00:00+00:00"),
            cursor=page1.pagination.next_cursor,
            limit=2,
            all_sources=True,
        )

        seen = [s.source.provider for s in page1.data] + [s.source.provider for s in page2.data]
        assert sorted(seen) == ["apple", "garmin", "whoop"], "every source must appear exactly once across the pages"
