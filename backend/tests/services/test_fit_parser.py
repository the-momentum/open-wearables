from decimal import Decimal
from uuid import uuid4

import fitdecode
import pytest

from app.schemas.enums.series_types import SeriesType
from app.services.fit_parser import FitParseResult, parse_fit_file
from tests.fixtures.fit_builder import make_cycling_fit, make_running_fit, make_swimming_fit

USER_ID = uuid4()
DS_ID = uuid4()


@pytest.fixture(scope="module")
def running() -> FitParseResult:
    return parse_fit_file(make_running_fit(), USER_ID, DS_ID, source="garmin")


@pytest.fixture(scope="module")
def cycling() -> FitParseResult:
    return parse_fit_file(make_cycling_fit(), USER_ID, DS_ID, source="garmin")


@pytest.fixture(scope="module")
def swimming() -> FitParseResult:
    return parse_fit_file(make_swimming_fit(), USER_ID, DS_ID, source="garmin")


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
        assert SeriesType.latitude in types
        assert SeriesType.longitude in types
        assert SeriesType.elevation in types
        assert SeriesType.air_temperature in types
        assert SeriesType.running_vertical_ratio in types
        assert SeriesType.running_stance_time_balance in types

    def test_granularity_one_second(self, running: FitParseResult) -> None:
        hr = sorted(s.recorded_at for s in running.samples if s.series_type == SeriesType.heart_rate)
        gaps = [(hr[i + 1] - hr[i]).seconds for i in range(len(hr) - 1)]
        assert all(g == 1 for g in gaps)

    def test_heart_rate_values_in_range(self, running: FitParseResult) -> None:
        vals = [s.value for s in running.samples if s.series_type == SeriesType.heart_rate]
        assert all(Decimal(40) <= v <= Decimal(220) for v in vals)

    def test_speed_non_negative(self, running: FitParseResult) -> None:
        vals = [s.value for s in running.samples if s.series_type == SeriesType.speed]
        assert all(v >= Decimal(0) for v in vals)

    def test_vertical_oscillation_in_cm_range(self, running: FitParseResult) -> None:
        # FIT raw mm/10 → parser _scale(0.1) → cm; synthetic value 8.5 cm
        vals = [s.value for s in running.samples if s.series_type == SeriesType.running_vertical_oscillation]
        assert all(Decimal("0.1") <= v <= Decimal("30") for v in vals)

    def test_sample_metadata(self, running: FitParseResult) -> None:
        s = running.samples[0]
        assert s.user_id == USER_ID
        assert s.data_source_id == DS_ID
        assert s.source == "garmin"
        assert s.recorded_at is not None
        assert s.recorded_at.tzinfo is not None

    def test_gps_values_in_degree_range(self, running: FitParseResult) -> None:
        lats = [s.value for s in running.samples if s.series_type == SeriesType.latitude]
        lons = [s.value for s in running.samples if s.series_type == SeriesType.longitude]
        assert all(Decimal(-90) <= v <= Decimal(90) for v in lats)
        assert all(Decimal(-180) <= v <= Decimal(180) for v in lons)

    def test_elevation_in_meters(self, running: FitParseResult) -> None:
        vals = [s.value for s in running.samples if s.series_type == SeriesType.elevation]
        # synthetic: 200 m
        assert all(Decimal(0) <= v <= Decimal(9000) for v in vals)

    def test_temperature_in_celsius_range(self, running: FitParseResult) -> None:
        vals = [s.value for s in running.samples if s.series_type == SeriesType.air_temperature]
        # synthetic: 18°C
        assert all(Decimal(-50) <= v <= Decimal(60) for v in vals)

    def test_running_dynamics_in_range(self, running: FitParseResult) -> None:
        vr = [s.value for s in running.samples if s.series_type == SeriesType.running_vertical_ratio]
        stb = [s.value for s in running.samples if s.series_type == SeriesType.running_stance_time_balance]
        # synthetic: vertical_ratio=8.5%, stance_time_balance=49.5%
        assert all(Decimal(0) <= v <= Decimal(100) for v in vr)
        assert all(Decimal(0) <= v <= Decimal(100) for v in stb)


class TestCycling:
    def test_only_heart_rate(self, cycling: FitParseResult) -> None:
        assert {s.series_type for s in cycling.samples} == {SeriesType.heart_rate}

    def test_has_samples(self, cycling: FitParseResult) -> None:
        assert len(cycling.samples) > 0


class TestSwimming:
    def test_only_heart_rate(self, swimming: FitParseResult) -> None:
        assert {s.series_type for s in swimming.samples} == {SeriesType.heart_rate}


class TestInvalidInput:
    def test_empty_bytes_returns_no_samples(self) -> None:
        assert parse_fit_file(b"", uuid4(), uuid4()).samples == []

    def test_garbage_bytes_raises(self) -> None:
        with pytest.raises(fitdecode.FitError):
            parse_fit_file(b"not a fit file at all", uuid4(), uuid4())
