"""Tests for clearing the sleep stages SDK nights never reported."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import SleepDetails
from app.schemas.enums import ProviderName
from app.services.data_migration_service import data_migration_service
from tests.factories import DataSourceFactory, EventRecordFactory, SleepDetailsFactory, UserFactory

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "clear_sdk_unreported_sleep_stages.py"
)


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("clear_sdk_unreported_sleep_stages", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_module()
clear_sdk_unreported_sleep_stages = module.clear_sdk_unreported_sleep_stages

_NIGHT = datetime(2025, 3, 10, 23, 0, tzinfo=timezone.utc)


def _segments(*stages: str) -> list[dict[str, str]]:
    """One 30-minute segment per stage, back to back."""
    return [
        {
            "stage": stage,
            "start_time": (_NIGHT + timedelta(minutes=30 * i)).isoformat(),
            "end_time": (_NIGHT + timedelta(minutes=30 * (i + 1))).isoformat(),
        }
        for i, stage in enumerate(stages)
    ]


def _night(
    provider: ProviderName,
    user: object,
    *,
    stages: Any,
    deep: int = 0,
    light: int = 0,
    rem: int = 0,
    awake: int = 0,
) -> SleepDetails:
    source = DataSourceFactory(user=user, provider=provider, source=provider.value)
    return SleepDetailsFactory(
        event_record=EventRecordFactory(data_source=source, category="sleep", type_="sleep_session"),
        sleep_deep_minutes=deep,
        sleep_light_minutes=light,
        sleep_rem_minutes=rem,
        sleep_awake_minutes=awake,
        sleep_total_duration_minutes=420,
        sleep_stages=stages,
    )


def _stages(db: Session, details: SleepDetails) -> tuple[int | None, int | None, int | None, int | None]:
    db.expire_all()
    row = db.get(SleepDetails, details.record_id)
    assert row is not None
    assert row.sleep_total_duration_minutes == 420
    return row.sleep_deep_minutes, row.sleep_light_minutes, row.sleep_rem_minutes, row.sleep_awake_minutes


class TestClearSdkUnreportedSleepStages:
    def test_clears_sdk_nights_without_phases(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(module, "_BATCH_SIZE", 1)
        user = UserFactory()
        sleeping_only = _night(ProviderName.APPLE, user, stages=_segments("sleeping", "sleeping"))
        no_hypnogram = _night(ProviderName.SAMSUNG, user, stages=None)
        xml_import = _night(ProviderName.UNKNOWN, user, stages=_segments("in_bed"))
        with_awake = _night(
            ProviderName.HEALTH_CONNECT, user, stages=_segments("sleeping", "awake", "sleeping"), awake=30
        )

        cleared = clear_sdk_unreported_sleep_stages(db, dry_run=False)

        assert cleared == 4
        assert _stages(db, sleeping_only) == (None, None, None, None)
        assert _stages(db, no_hypnogram) == (None, None, None, None)
        assert _stages(db, xml_import) == (None, None, None, None)
        assert _stages(db, with_awake) == (None, None, None, 30)

    def test_keeps_measured_zeros(self, db: Session) -> None:
        user = UserFactory()
        # Detailed phases without REM: the zero is measured
        detailed = _night(ProviderName.APPLE, user, stages=_segments("light", "deep", "awake"), light=30, deep=30)
        # Short awake segments rounding down to 0 min are still a measured awake time
        brief_awake = _night(ProviderName.APPLE, user, stages=_segments("sleeping", "awake"))
        oura = _night(ProviderName.OURA, user, stages=None)
        garmin = _night(ProviderName.GARMIN, user, stages=_segments("sleeping"))

        clear_sdk_unreported_sleep_stages(db, dry_run=False)

        assert _stages(db, detailed) == (30, 30, 0, 0)
        assert _stages(db, brief_awake) == (None, None, None, 0)
        assert _stages(db, oura) == (0, 0, 0, 0)
        assert _stages(db, garmin) == (0, 0, 0, 0)

    def test_skips_a_night_rewritten_after_it_was_collected(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        details = _night(ProviderName.APPLE, UserFactory(), stages=_segments("sleeping"))
        # Stands in for a sync merging new phases into the night between collecting and clearing
        monkeypatch.setattr(
            module,
            "_INDEX",
            text(f"UPDATE sleep_details SET sleep_deep_minutes = 45 WHERE record_id = '{details.record_id}'"),
        )

        assert clear_sdk_unreported_sleep_stages(db, dry_run=False) == 0
        assert _stages(db, details) == (45, 0, 0, 0)

    def test_dry_run_counts_and_changes_nothing(self, db: Session) -> None:
        user = UserFactory()
        details = _night(ProviderName.APPLE, user, stages=_segments("sleeping"))
        _night(ProviderName.APPLE, user, stages=_segments("light", "deep"), light=30, deep=30)

        assert clear_sdk_unreported_sleep_stages(db, dry_run=True) == 1
        assert _stages(db, details) == (0, 0, 0, 0)

    def test_runs_once_per_instance(self, db: Session) -> None:
        user = UserFactory()
        first = _night(ProviderName.APPLE, user, stages=_segments("sleeping"))

        def run() -> None:
            data_migration_service.run(
                db, "clear_sdk_unreported_sleep_stages", lambda: module._migrate(db, dry_run=False)
            )

        run()
        later = _night(ProviderName.APPLE, user, stages=_segments("sleeping"))
        run()

        assert _stages(db, first) == (None, None, None, None)
        assert _stages(db, later) == (0, 0, 0, 0)
