"""Tests for the normalized 24/7 sync result.

Covers the contract the sync orchestrator relies on:
- rows written, and the new-vs-updated split where a write path reports one
- per-data-type isolation: one failure doesn't take the rest of the run down
- status derivation (ok / partial / failed / skipped)
- the Mapping shim and the sync-log payload
"""

import logging
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.repositories.data_point_series_repository import WriteCounts
from app.services.providers.sync_247_result import (
    Sync247Result,
    Sync247Run,
    Sync247Status,
)


@pytest.fixture
def run() -> Sync247Run:
    return Sync247Run("testprovider", MagicMock(), uuid4(), logging.getLogger(__name__))


class TestWriteCountsArithmetic:
    """Accumulating counts must not silently drop the split."""

    def test_adding_two_write_counts_keeps_the_split(self) -> None:
        total = WriteCounts(3, 1) + WriteCounts(2, 4)

        assert isinstance(total, WriteCounts)
        assert (total.inserted, total.updated, int(total)) == (5, 5, 10)

    def test_sum_starts_from_zero_without_losing_the_split(self) -> None:
        total = sum([WriteCounts(2, 0), WriteCounts(1, 1)])

        assert isinstance(total, WriteCounts)
        assert (total.inserted, total.updated) == (3, 1)

    def test_adding_a_plain_int_degrades_to_int(self) -> None:
        # Those rows' split is unknown; claiming they were inserts would be a lie.
        assert not isinstance(WriteCounts(3, 1) + 2, WriteCounts)
        assert WriteCounts(3, 1) + 2 == 6


class TestSync247Result:
    def test_aggregates_written_and_split(self) -> None:
        result = Sync247Result(provider="p")
        result.record("heart_rate", WriteCounts(10, 2))
        result.record("sleep", 3)  # no split available from this write path

        assert result.rows_written == 15
        assert result.inserted == 10
        assert result.updated == 2
        assert not result.split_complete  # sleep can't report a split

    def test_split_complete_when_every_writing_type_reports_one(self) -> None:
        result = Sync247Result(provider="p")
        result.record("heart_rate", WriteCounts(10, 2))
        result.record("sleep", 0)  # wrote nothing, so nothing to split

        assert result.split_complete

    def test_status_is_derived_from_what_happened(self) -> None:
        result = Sync247Result(provider="p")
        result.record("heart_rate", WriteCounts(1, 0))
        result.record("spo2", 2)
        result.fail("spo2", "partial page failure")
        result.fail("steps", RuntimeError("boom"))
        result.skip("vo2_max", "not in window")

        assert result.outcomes["heart_rate"].status is Sync247Status.OK
        assert result.outcomes["spo2"].status is Sync247Status.PARTIAL
        assert result.outcomes["steps"].status is Sync247Status.FAILED
        assert result.outcomes["vo2_max"].status is Sync247Status.SKIPPED

    def test_all_failed_only_when_every_attempted_type_failed(self) -> None:
        result = Sync247Result(provider="p")
        result.fail("heart_rate", RuntimeError("401"))
        result.fail("sleep", RuntimeError("401"))
        result.skip("spo2")

        assert result.all_failed
        assert result.failures == {"heart_rate": "401", "sleep": "401"}

        result.record("steps", 5)
        assert not result.all_failed
        assert result.any_failed

    def test_empty_result_is_not_a_failure(self) -> None:
        # A provider whose data arrives by push attempts nothing at all.
        assert not Sync247Result(provider="p", note="push only").all_failed

    def test_add_accumulates_across_chunks(self) -> None:
        result = Sync247Result(provider="p")
        result.add("activity", WriteCounts(2, 1), skipped=1)
        result.add("activity", WriteCounts(3, 0), truncated=True)

        outcome = result.outcomes["activity"]
        assert outcome.rows_written == 6
        assert outcome.counts is not None
        assert (outcome.counts.inserted, outcome.counts.updated) == (5, 1)
        assert outcome.skipped == 1
        assert outcome.truncated
        assert result.truncated == ("activity",)

    def test_recording_keeps_earlier_failures_visible(self) -> None:
        result = Sync247Result(provider="p")
        result.fail("sleep", RuntimeError("page 2 failed"))
        result.record("sleep", 4)

        assert result.outcomes["sleep"].status is Sync247Status.PARTIAL
        assert result.failures == {"sleep": "page 2 failed"}

    def test_behaves_as_a_mapping_of_data_type_to_rows_written(self) -> None:
        result = Sync247Result(provider="p")
        result.record("heart_rate", WriteCounts(4, 0))
        result.record("sleep", 1)

        assert dict(result) == {"heart_rate": 4, "sleep": 1}
        assert result["heart_rate"] == 4
        assert len(result) == 2
        assert set(result) == {"heart_rate", "sleep"}

    def test_as_dict_carries_status_per_type_and_omits_defaults(self) -> None:
        result = Sync247Result(provider="p", note="partial window")
        result.record("heart_rate", WriteCounts(4, 1), truncated=True)
        result.fail("steps", RuntimeError("boom"))

        payload = result.as_dict()

        assert payload["provider"] == "p"
        assert payload["rows_written"] == 4 + 1
        assert payload["inserted"] == 4
        assert payload["updated"] == 1
        assert payload["truncated"] == ["heart_rate"]
        assert payload["note"] == "partial window"
        assert payload["types"]["heart_rate"] == {
            "status": "ok",
            "rows_written": 5,
            "inserted": 4,
            "updated": 1,
            "truncated": True,
        }
        assert payload["types"]["steps"] == {"status": "failed", "rows_written": 0, "error": "boom"}


class TestSync247RunStep:
    def test_step_records_what_the_body_reported(self, run: Sync247Run) -> None:
        with run.step("heart_rate") as step:
            step.record(WriteCounts(3, 1))

        assert run.result["heart_rate"] == 4
        assert run.result.inserted == 3

    def test_step_with_no_recording_counts_as_an_empty_success(self, run: Sync247Run) -> None:
        with run.step("spo2"):
            pass

        assert run.result.outcomes["spo2"].status is Sync247Status.OK
        assert run.result.rows_written == 0

    def test_failure_is_isolated_to_its_data_type(self, run: Sync247Run) -> None:
        with run.step("sleep") as step:
            step.record(2)

        with run.step("recovery"):
            raise RuntimeError("provider 500")

        with run.step("steps") as step:
            step.record(WriteCounts(1, 0))

        assert run.result.failures == {"recovery": "provider 500"}
        assert run.result.rows_written == 3
        assert not run.result.all_failed
        run.db.rollback.assert_called_once()

    def test_commit_only_on_success(self, run: Sync247Run) -> None:
        with run.step("sleep", commit=True) as step:
            step.record(1)
        run.db.commit.assert_called_once()

        with run.step("recovery", commit=True):
            raise RuntimeError("boom")
        run.db.commit.assert_called_once()  # not called again

    def test_failing_commit_is_contained_and_reported_as_failed(self, run: Sync247Run) -> None:
        """A commit that raises wrote nothing, so the step must not report rows."""
        run.db.commit.side_effect = RuntimeError("deferred constraint")

        with run.step("sleep", commit=True) as step:
            step.record(WriteCounts(5, 0))

        with run.step("recovery") as step:
            step.record(2)

        outcome = run.result.outcomes["sleep"]
        assert outcome.status is Sync247Status.FAILED
        assert outcome.rows_written == 0
        assert run.result.failures == {"sleep": "deferred constraint"}
        run.db.rollback.assert_called_once()
        # the next data type still ran
        assert run.result.outcomes["recovery"].status is Sync247Status.OK

    def test_savepoint_confines_the_write_without_a_full_rollback(self, run: Sync247Run) -> None:
        with run.step("heart_rate", savepoint=True):
            raise RuntimeError("bad write")

        run.db.begin_nested.assert_called_once()
        run.db.rollback.assert_not_called()
        assert run.result.outcomes["heart_rate"].status is Sync247Status.FAILED

    def test_fatal_errors_propagate_instead_of_being_recorded(self, run: Sync247Run) -> None:
        run.fatal = (HTTPException,)

        with pytest.raises(HTTPException), run.step("sleep"):
            raise HTTPException(status_code=401, detail="token expired")

        assert "sleep" not in run.result.outcomes

    def test_accumulating_steps_add_up_across_calls(self, run: Sync247Run) -> None:
        for _ in range(3):
            with run.step("activity", accumulate=True) as step:
                step.record(WriteCounts(2, 0))

        assert run.result["activity"] == 6
        assert run.result.inserted == 6

    def test_expect_keeps_untouched_data_types_in_the_result(self, run: Sync247Run) -> None:
        run.expect("sleep", "activity")

        with run.step("activity") as step:
            step.record(WriteCounts(2, 0))

        assert run.result.outcomes["sleep"].status is Sync247Status.SKIPPED
        assert run.result.outcomes["activity"].status is Sync247Status.OK
        assert run.result.rows_written == 2
        assert not run.result.all_failed
