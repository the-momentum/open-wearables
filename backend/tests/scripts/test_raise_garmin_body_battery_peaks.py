"""Tests for raising Garmin body battery scores to the highest sample of their day."""

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, HealthScore, SeriesTypeDefinition, User
from app.schemas.enums import HealthScoreCategory, ProviderName, SeriesType, get_series_type_id
from tests.factories import DataPointSeriesFactory, DataSourceFactory, HealthScoreFactory, UserFactory

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "raise_garmin_body_battery_peaks.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("raise_garmin_body_battery_peaks", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
raise_garmin_body_battery_peaks = module.raise_garmin_body_battery_peaks

DAY = datetime(2026, 10, 27, 23, tzinfo=timezone.utc)  # a stressDetails day starting at local midnight, +01:00


def _garmin(user: User) -> DataSource:
    return DataSourceFactory(user=user, provider=ProviderName.GARMIN, source="garmin")


def _samples(db: Session, source: DataSource, day: datetime, values: dict[float, int]) -> None:
    """Body battery samples at `day` plus each offset in hours."""
    series_type = db.get_one(SeriesTypeDefinition, get_series_type_id(SeriesType.garmin_body_battery))
    for hours, value in values.items():
        DataPointSeriesFactory(
            data_source=source, series_type=series_type, recorded_at=day + timedelta(hours=hours), value=value
        )


def _peak(user: User, day: datetime, value: str) -> HealthScore:
    return HealthScoreFactory(
        user_id=user.id,
        data_source_id=None,
        provider=ProviderName.GARMIN,
        category=HealthScoreCategory.BODY_BATTERY,
        value=Decimal(value),
        recorded_at=day,
        qualifier=None,
    )


def _value(db: Session, score: HealthScore) -> Decimal:
    db.expire_all()
    return db.get_one(HealthScore, score.id).value


class TestRaiseGarminBodyBatteryPeaks:
    def test_raises_a_score_to_its_days_highest_sample(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(module, "_BATCH_SIZE", 1)
        user = UserFactory()
        source = _garmin(user)
        _samples(db, source, DAY, {1: 20, 7: 78, 15: 40})
        _samples(db, source, DAY + timedelta(days=1), {7: 95})  # the next day's peak doesn't count
        low = _peak(user, DAY, "46")
        _samples(db, source, DAY - timedelta(days=1), {7: 81})
        other_low = _peak(user, DAY - timedelta(days=1), "30")

        raised = raise_garmin_body_battery_peaks(db, dry_run=False)

        assert raised == 2
        assert _value(db, low) == Decimal("78")
        assert _value(db, other_low) == Decimal("81")

    def test_a_day_ends_where_the_next_one_starts(self, db: Session) -> None:
        # A 23-hour day (spring forward, or travelling east): the next day's samples don't count
        user = UserFactory()
        source = _garmin(user)
        next_day = DAY + timedelta(hours=23)
        _samples(db, source, DAY, {7: 60})
        _samples(db, source, next_day, {0.5: 90})
        short_day = _peak(user, DAY, "46")
        _peak(user, next_day, "95")

        raise_garmin_body_battery_peaks(db, dry_run=False)

        assert _value(db, short_day) == Decimal("60")

    def test_a_day_without_a_next_one_lasts_24_hours(self, db: Session) -> None:
        user = UserFactory()
        _samples(db, _garmin(user), DAY, {23.5: 60, 24.5: 90})
        score = _peak(user, DAY, "46")

        raise_garmin_body_battery_peaks(db, dry_run=False)

        assert _value(db, score) == Decimal("60")

    def test_never_lowers_a_score(self, db: Session) -> None:
        user = UserFactory()
        _samples(db, _garmin(user), DAY, {7: 78})
        score = _peak(user, DAY, "80")

        assert raise_garmin_body_battery_peaks(db, dry_run=False) == 0
        assert _value(db, score) == Decimal("80")

    def test_reads_only_the_users_garmin_samples(self, db: Session) -> None:
        user = UserFactory()
        _samples(db, _garmin(UserFactory()), DAY, {7: 90})
        _samples(db, DataSourceFactory(user=user, provider=ProviderName.APPLE), DAY, {7: 90})
        score = _peak(user, DAY, "46")

        assert raise_garmin_body_battery_peaks(db, dry_run=False) == 0
        assert _value(db, score) == Decimal("46")

    def test_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        user = UserFactory()
        _samples(db, _garmin(user), DAY, {7: 78})
        score = _peak(user, DAY, "46")

        assert raise_garmin_body_battery_peaks(db, dry_run=True) == 1
        assert _value(db, score) == Decimal("46")
