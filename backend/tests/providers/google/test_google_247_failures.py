"""Failure-surfacing tests for GoogleHealth247Data.load_and_save_all.

A run where every unit (all registered metrics and sleep) fails must raise —
previously it returned an empty result indistinguishable from a linked
account with no data, so neither the sync task's FAILED/PARTIAL machinery
nor the manual sync route could ever report it (#1361). Partial failures
keep the existing per-metric isolation and return normally.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.providers.google.health_api import data_247 as data_247_module
from app.services.providers.google.health_api.data_247 import GoogleHealth247Data
from app.services.providers.google.strategy import GoogleStrategy

_END = datetime.now(timezone.utc)
_START = _END - timedelta(days=30)


def _fake_metric(name: str) -> MagicMock:
    metric = MagicMock()
    metric.data_type = name
    metric.use_list.return_value = False  # rollup path; _rollup_samples is stubbed either way
    return metric


@pytest.fixture
def sleep_mock() -> MagicMock:
    return MagicMock()


@pytest.fixture
def data_247(sleep_mock: MagicMock) -> GoogleHealth247Data:
    instance = GoogleStrategy().data_247
    assert isinstance(instance, GoogleHealth247Data)
    settings_repo = MagicMock()
    settings_repo.get_data_granularity.return_value = None  # fall back to default granularity
    instance.settings_repo = settings_repo
    instance.sleep = sleep_mock
    return instance


@pytest.fixture
def metrics(monkeypatch: pytest.MonkeyPatch) -> list[MagicMock]:
    fakes = [_fake_metric("steps"), _fake_metric("weight")]
    monkeypatch.setattr(data_247_module, "METRICS", fakes)
    return fakes


@pytest.fixture
def timeseries_service_mock(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr(data_247_module, "timeseries_service", mock)
    return mock


class TestLoadAndSaveAllFailureSurfacing:
    def test_all_units_failed_raises_instead_of_clean_empty_success(
        self, data_247: GoogleHealth247Data, metrics: list[MagicMock], sleep_mock: MagicMock
    ) -> None:
        db = MagicMock()
        boom = HTTPException(400, "Google API error: ACCOUNT_NOT_LINKED")
        data_247._rollup_samples = MagicMock(side_effect=boom)
        sleep_mock.load_and_save.side_effect = boom

        with pytest.raises(HTTPException) as exc_info:
            data_247.load_and_save_all(db, uuid4(), start_time=_START, end_time=_END)

        assert exc_info.value.status_code == 502
        assert "all 3 data types" in exc_info.value.detail
        for unit in ("steps", "weight", "sleep"):
            assert unit in exc_info.value.detail
        assert "ACCOUNT_NOT_LINKED" in exc_info.value.detail
        db.commit.assert_not_called()

    def test_sleep_success_alone_prevents_the_raise(
        self, data_247: GoogleHealth247Data, metrics: list[MagicMock], sleep_mock: MagicMock
    ) -> None:
        db = MagicMock()
        data_247._rollup_samples = MagicMock(side_effect=HTTPException(500, "boom"))
        sleep_mock.load_and_save.return_value = 0  # succeeded, found nothing

        result = data_247.load_and_save_all(db, uuid4(), start_time=_START, end_time=_END)

        assert result == {}

    def test_one_metric_success_keeps_partial_isolation(
        self,
        data_247: GoogleHealth247Data,
        metrics: list[MagicMock],
        timeseries_service_mock: MagicMock,
        sleep_mock: MagicMock,
    ) -> None:
        db = MagicMock()
        counts = MagicMock()
        # First metric yields samples, second fails — existing isolation behavior.
        data_247._rollup_samples = MagicMock(side_effect=[[MagicMock()], HTTPException(500, "boom")])
        timeseries_service_mock.bulk_create_samples.return_value = counts
        sleep_mock.load_and_save.side_effect = HTTPException(500, "boom")

        result = data_247.load_and_save_all(db, uuid4(), start_time=_START, end_time=_END)

        assert result == {"steps": counts}
        db.commit.assert_called_once()

    def test_all_units_empty_but_successful_is_not_a_failure(
        self, data_247: GoogleHealth247Data, metrics: list[MagicMock], sleep_mock: MagicMock
    ) -> None:
        """Empty results ≠ failed run — a linked account with no data must not raise."""
        db = MagicMock()
        data_247._rollup_samples = MagicMock(return_value=[])
        sleep_mock.load_and_save.return_value = 0

        result = data_247.load_and_save_all(db, uuid4(), start_time=_START, end_time=_END)

        assert result == {}
        db.commit.assert_not_called()
