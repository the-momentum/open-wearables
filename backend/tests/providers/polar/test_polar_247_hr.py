"""Tests for PolarData247Template continuous-heart-rate sync."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.providers.polar.data_247 import PolarData247Template
from app.services.providers.polar.strategy import PolarStrategy


@pytest.fixture
def data_247() -> PolarData247Template:
    return PolarStrategy().data_247


@pytest.fixture
def sample_polar_hr_day() -> dict[str, Any]:
    return {
        "polar_user": "https://polaraccesslink.com/v3/users/627139",
        "date": "2022-09-12",
        "heart_rate_samples": [
            {"heart_rate": 63, "sample_time": "00:02:08"},
            {"heart_rate": 62, "sample_time": "00:07:08"},
            {"heart_rate": 78, "sample_time": "12:15:42"},
        ],
    }


class TestPolarContinuousHRNormalization:
    def test_builds_timeseries_samples(
        self, data_247: PolarData247Template, sample_polar_hr_day: dict
    ) -> None:
        user_id = uuid4()
        samples = data_247.normalize_continuous_hr([sample_polar_hr_day], user_id)

        assert len(samples) == 3
        assert all(isinstance(s, TimeSeriesSampleCreate) for s in samples)
        assert all(s.series_type == SeriesType.heart_rate for s in samples)
        assert all(s.source == "polar" for s in samples)
        assert all(s.user_id == user_id for s in samples)

        # First sample: 2022-09-12 00:02:08 UTC, bpm 63
        assert samples[0].recorded_at == datetime(2022, 9, 12, 0, 2, 8, tzinfo=timezone.utc)
        assert samples[0].value == Decimal("63")
        # Third sample: 12:15:42 same day
        assert samples[2].recorded_at == datetime(2022, 9, 12, 12, 15, 42, tzinfo=timezone.utc)
        assert samples[2].value == Decimal("78")

    def test_skips_malformed_sample_time(self, data_247: PolarData247Template) -> None:
        user_id = uuid4()
        raw = {
            "date": "2022-09-12",
            "heart_rate_samples": [
                {"heart_rate": 60, "sample_time": "not-a-time"},
                {"heart_rate": 70, "sample_time": "05:00:00"},
            ],
        }
        samples = data_247.normalize_continuous_hr([raw], user_id)
        assert len(samples) == 1
        assert samples[0].value == Decimal("70")

    def test_skips_days_with_bad_date(self, data_247: PolarData247Template) -> None:
        """A day-level response with a malformed ``date`` is dropped entirely."""
        user_id = uuid4()
        raw = {"date": "bogus", "heart_rate_samples": [{"heart_rate": 60, "sample_time": "00:00:00"}]}
        samples = data_247.normalize_continuous_hr([raw], user_id)
        assert samples == []


class TestPolarContinuousHRFetchAndSave:
    def test_get_continuous_hr_iterates_days(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        captured: list[str] = []

        def fake_make_api_request(
            db, user_id, endpoint, params=None  # noqa: ANN001
        ) -> dict:
            captured.append(endpoint)
            # Return real data for the first day, empty for the rest
            if endpoint.endswith("2024-01-01"):
                return {"date": "2024-01-01", "heart_rate_samples": [{"heart_rate": 65, "sample_time": "00:00:00"}]}
            return {"date": endpoint.rsplit("/", 1)[-1], "heart_rate_samples": []}

        monkeypatch.setattr(data_247, "_make_api_request", fake_make_api_request)

        result = data_247.get_continuous_hr_data(
            db=None,  # type: ignore[arg-type]
            user_id=uuid4(),
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 1, 3, tzinfo=timezone.utc),
        )

        # Iterated three days, but only the one with samples is kept
        assert captured == [
            "/v3/users/continuous-heart-rate/2024-01-01",
            "/v3/users/continuous-heart-rate/2024-01-02",
            "/v3/users/continuous-heart-rate/2024-01-03",
        ]
        assert len(result) == 1
        assert result[0]["date"] == "2024-01-01"

    def test_save_continuous_hr_delegates_to_bulk_create(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        """``save_continuous_hr`` must hand samples to ``timeseries_service.bulk_create_samples``."""
        calls: list[list[TimeSeriesSampleCreate]] = []

        def fake_bulk_create(db, samples):  # noqa: ANN001
            calls.append(samples)

        from app.services.providers.polar import data_247 as mod

        monkeypatch.setattr(mod.timeseries_service, "bulk_create_samples", fake_bulk_create)

        user_id = uuid4()
        sample_one = TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user_id,
            source="polar",
            recorded_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            value=Decimal("72"),
            series_type=SeriesType.heart_rate,
        )
        count = data_247.save_continuous_hr(db=None, user_id=user_id, samples=[sample_one])  # type: ignore[arg-type]

        assert count == 1
        assert calls == [[sample_one]]

    def test_save_continuous_hr_skips_when_empty(
        self, data_247: PolarData247Template, monkeypatch
    ) -> None:
        called = False

        def fake_bulk_create(db, samples):  # noqa: ANN001
            nonlocal called
            called = True

        from app.services.providers.polar import data_247 as mod

        monkeypatch.setattr(mod.timeseries_service, "bulk_create_samples", fake_bulk_create)

        count = data_247.save_continuous_hr(db=None, user_id=uuid4(), samples=[])  # type: ignore[arg-type]
        assert count == 0
        assert called is False
