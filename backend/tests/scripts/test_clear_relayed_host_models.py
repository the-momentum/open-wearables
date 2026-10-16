"""Tests for the one-off clearing of relaying host models on third-party HealthKit sources."""

import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.models import DataSource
from app.schemas.enums import DeviceType, ProviderName
from tests.factories import DataSourceFactory, UserFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "clear_relayed_host_models.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("clear_relayed_host_models", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


clear_relayed_host_models = _load_module().clear_relayed_host_models


def _source(user: object, **fields: object) -> DataSource:
    return DataSourceFactory(user=user, provider=ProviderName.APPLE, **fields)


class TestClearRelayedHostModels:
    def test_clears_host_model_and_re_resolves_type(self, db: Session) -> None:
        user = UserFactory()
        oura = _source(
            user, device_model="iPhone16,1", device_type="phone", source="Oura", source_app_id="com.ouraring.oura"
        )

        counts = clear_relayed_host_models(db, dry_run=False)
        db.flush()
        db.refresh(oura)

        assert counts["cleared"] == 1
        assert oura.device_model is None
        assert oura.device_type == DeviceType.RING

    def test_leaves_apple_own_producer_and_legacy_rows(self, db: Session) -> None:
        user = UserFactory()
        watch = _source(user, device_model="Watch6,2", source="Apple Watch", source_app_id="com.apple.health.X")
        ring = _source(user, device_model="Oura Ring Gen3", source="Oura", source_app_id="com.ouraring.oura")
        legacy = _source(user, device_model="iPhone16,1", source="Zepp Life")

        counts = clear_relayed_host_models(db, dry_run=False)
        db.flush()

        assert counts["cleared"] == 0
        assert (watch.device_model, ring.device_model, legacy.device_model) == (
            "Watch6,2",
            "Oura Ring Gen3",
            "iPhone16,1",
        )

    def test_skips_writer_that_already_has_a_source_without_model(self, db: Session) -> None:
        user = UserFactory()
        relayed = _source(user, device_model="iPhone16,1", source="Oura", source_app_id="com.ouraring.oura")
        _source(user, device_model=None, source="Oura", source_app_id="com.ouraring.oura")

        counts = clear_relayed_host_models(db, dry_run=False)
        db.flush()

        assert counts == {"skipped": 1}
        assert relayed.device_model == "iPhone16,1"

    def test_dry_run_changes_nothing(self, db: Session) -> None:
        user = UserFactory()
        oura = _source(user, device_model="iPhone16,1", source="Oura", source_app_id="com.ouraring.oura")

        counts = clear_relayed_host_models(db, dry_run=True)

        assert counts["cleared"] == 1
        assert oura.device_model == "iPhone16,1"
