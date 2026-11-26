"""Tests for clearing the 0 kcal the SDK and Apple XML importers stored for workouts without calories."""

import importlib.util
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy.orm import Session

from app.models import WorkoutDetails
from app.schemas.enums import ProviderName
from tests.factories import DataSourceFactory, EventRecordFactory, UserFactory, WorkoutDetailsFactory

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "clear_sdk_zero_workout_calories.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("clear_sdk_zero_workout_calories", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
clear_sdk_zero_workout_calories = module.clear_sdk_zero_workout_calories


def _workout(provider: ProviderName, kcal: str, user: object) -> WorkoutDetails:
    source = DataSourceFactory(user=user, provider=provider, source=provider.value)
    return WorkoutDetailsFactory(
        event_record=EventRecordFactory(data_source=source, category="workout"), energy_burned=Decimal(kcal)
    )


def _kcal(db: Session, details: WorkoutDetails) -> Decimal | None:
    db.expire_all()
    return db.get(WorkoutDetails, details.record_id).energy_burned


class TestClearSdkZeroWorkoutCalories:
    def test_clears_sdk_zeros_and_keeps_the_rest(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(module, "_BATCH_SIZE", 1)
        user = UserFactory()
        health_connect = _workout(ProviderName.HEALTH_CONNECT, "0", user)
        apple = _workout(ProviderName.APPLE, "0", user)
        samsung = _workout(ProviderName.SAMSUNG, "0", user)
        reported = _workout(ProviderName.HEALTH_CONNECT, "250", user)
        cloud = _workout(ProviderName.GARMIN, "0", user)

        cleared = clear_sdk_zero_workout_calories(db, dry_run=False)

        assert cleared == 3
        assert [_kcal(db, details) for details in (health_connect, apple, samsung)] == [None, None, None]
        assert _kcal(db, reported) == Decimal("250")
        assert _kcal(db, cloud) == Decimal("0")

    def test_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        details = _workout(ProviderName.HEALTH_CONNECT, "0", UserFactory())

        assert clear_sdk_zero_workout_calories(db, dry_run=True) == 1
        assert _kcal(db, details) == Decimal("0")
