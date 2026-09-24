"""Tests for the startup backfill that re-resolves NULL/'other' data_source.device_type."""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.schemas.enums import ProviderName
from tests.factories import DataSourceFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "backfill_device_types.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backfill_device_types", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backfill_device_types = _load_module().backfill_device_types


class TestBackfillDeviceTypes:
    def test_upgrades_null_and_other_rows(self, db: Session) -> None:
        watch = DataSourceFactory(
            provider=ProviderName.SAMSUNG, device_model="SM-L315F", source="Galaxy Watch7", device_type="other"
        )
        whoop = DataSourceFactory(provider=ProviderName.WHOOP, device_model=None, source="whoop", device_type=None)

        backfill_device_types(db, dry_run=False)

        assert watch.device_type == "watch"
        assert whoop.device_type == "band"

    def test_never_overwrites_concrete_type(self, db: Session) -> None:
        ds = DataSourceFactory(
            provider=ProviderName.APPLE, device_model="Watch6,12", source="AirPods Pro", device_type="phone"
        )

        backfill_device_types(db, dry_run=False)

        assert ds.device_type == "phone"

    def test_dry_run_changes_nothing(self, db: Session) -> None:
        ds = DataSourceFactory(provider=ProviderName.WHOOP, device_model=None, source="whoop", device_type=None)

        changes = backfill_device_types(db, dry_run=True)

        assert changes["whoop: None -> band"] == 1
        assert ds.device_type is None
