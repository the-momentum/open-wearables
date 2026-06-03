from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.enums.series_types import SeriesType
from app.services.fit_parser import FitParseResult, parse_fit_file

_FIXTURES = Path(__file__).parents[3] / ".debug" / "garmin"

USER_ID = uuid4()
DS_ID = uuid4()


def _load(rel: str) -> bytes:
    return (_FIXTURES / rel).read_bytes()


@pytest.fixture(scope="module")
def running() -> FitParseResult:
    return parse_fit_file(_load("running/22899105543.fit"), USER_ID, DS_ID, source="garmin")


@pytest.fixture(scope="module")
def indoor_cycling() -> FitParseResult:
    return parse_fit_file(_load("indoor_cycling/23008615039.fit"), USER_ID, DS_ID, source="garmin")


@pytest.fixture(scope="module")
def lap_swimming() -> FitParseResult:
    return parse_fit_file(_load("lap_swimming/22886328647.fit"), USER_ID, DS_ID, source="garmin")


class TestRunning:
    def test_sample_count(self, running: FitParseResult) -> None:
        assert len(running.samples) > 0

    def test_expected_series_types(self, running: FitParseResult) -> None:
        types = {s.series_type for s in running.samples}
        assert SeriesType.heart_rate in types
        assert SeriesType.speed in types
        assert SeriesType.cadence in types
        assert SeriesType.power in types
        assert SeriesType.running_vertical_oscillation in types
        assert SeriesType.running_ground_contact_time in types

    def test_granularity_one_second(self, running: FitParseResult) -> None:
        hr_samples = [s for s in running.samples if s.series_type == SeriesType.heart_rate]
        timestamps = sorted(s.recorded_at for s in hr_samples)
        gaps = [(timestamps[i + 1] - timestamps[i]).seconds for i in range(min(20, len(timestamps) - 1))]
        assert all(g == 1 for g in gaps)

    def test_heart_rate_values_in_range(self, running: FitParseResult) -> None:
        hr = [s.value for s in running.samples if s.series_type == SeriesType.heart_rate]
        assert all(Decimal(40) <= v <= Decimal(220) for v in hr)

    def test_speed_values_non_negative(self, running: FitParseResult) -> None:
        speeds = [s.value for s in running.samples if s.series_type == SeriesType.speed]
        assert all(v >= Decimal(0) for v in speeds)

    def test_running_vertical_oscillation_unit_cm(self, running: FitParseResult) -> None:
        # FIT stores in mm (scale 0.1), parser converts to cm — expect 4–15 cm range
        vals = [s.value for s in running.samples if s.series_type == SeriesType.running_vertical_oscillation]
        assert all(Decimal("0.1") <= v <= Decimal("30") for v in vals)

    def test_sample_fields_populated(self, running: FitParseResult) -> None:
        s = running.samples[0]
        assert s.user_id == USER_ID
        assert s.data_source_id == DS_ID
        assert s.source == "garmin"
        assert s.recorded_at is not None
        assert s.recorded_at.tzinfo is not None

    def test_no_gps_series_types(self, running: FitParseResult) -> None:
        types = {s.series_type for s in running.samples}
        # elevation/latitude/longitude not in map yet (#1074)
        assert "elevation" not in {t.value for t in types}
        assert "latitude" not in {t.value for t in types}

    def test_developer_fields_detected(self, running: FitParseResult) -> None:
        # Garmin proprietary unknown_XXX fields should be reported
        assert len(running.developer_fields_found) > 0


class TestIndoorCycling:
    def test_only_heart_rate(self, indoor_cycling: FitParseResult) -> None:
        types = {s.series_type for s in indoor_cycling.samples}
        assert types == {SeriesType.heart_rate}

    def test_no_crash_on_missing_fields(self, indoor_cycling: FitParseResult) -> None:
        assert len(indoor_cycling.samples) > 0


class TestLapSwimming:
    def test_only_heart_rate(self, lap_swimming: FitParseResult) -> None:
        types = {s.series_type for s in lap_swimming.samples}
        assert types == {SeriesType.heart_rate}


class TestInvalidInput:
    def test_empty_bytes_returns_no_samples(self) -> None:
        result = parse_fit_file(b"", uuid4(), uuid4())
        assert result.samples == []

    def test_garbage_bytes_raises(self) -> None:
        import fitdecode

        with pytest.raises(fitdecode.FitError):
            parse_fit_file(b"not a fit file at all", uuid4(), uuid4())
