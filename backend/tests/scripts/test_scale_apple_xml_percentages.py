import importlib.util
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import ModuleType

from sqlalchemy.orm import Session

from app.integrations.rollup_queue import pop_dirty_days
from app.models import DataSource, SeriesSample, SeriesTypeDefinition
from app.schemas.enums import ProviderName, SeriesType
from tests.factories import DataPointSeriesFactory, DataSourceFactory

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data_migrations" / "scale_apple_xml_percentages.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scale_apple_xml_percentages", _SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scale_apple_xml_percentages = _load_module().scale_apple_xml_percentages

AT = datetime(2025, 3, 1, 23, 30, tzinfo=timezone.utc)


def _xml_source() -> DataSource:
    return DataSourceFactory(provider=ProviderName.APPLE, source="apple_health_xml")


def _sample(db: Session, source: DataSource, series_type: SeriesType, value: str) -> SeriesSample:
    definition = db.query(SeriesTypeDefinition).filter_by(code=series_type.value).one()
    return DataPointSeriesFactory(
        data_source=source, series_type=definition, value=Decimal(value), recorded_at=AT, zone_offset="+01:00"
    )


def _value(db: Session, sample: SeriesSample) -> Decimal:
    db.expire_all()
    return db.get(SeriesSample, sample.id).value


class TestScaleAppleXmlPercentages:
    def test_scales_the_xml_fractions_of_percent_series(self, db: Session) -> None:
        source = _xml_source()
        oxygen = _sample(db, source, SeriesType.oxygen_saturation, "0.97")
        asymmetry = _sample(db, source, SeriesType.walking_asymmetry_percentage, "0.05")

        assert scale_apple_xml_percentages(db, dry_run=False) == 2
        assert _value(db, oxygen) == Decimal("97")
        assert _value(db, asymmetry) == Decimal("5")

    def test_leaves_other_sources_series_and_scaled_values_alone(self, db: Session) -> None:
        source = _xml_source()
        sdk = _sample(db, DataSourceFactory(source="apple_health_sdk"), SeriesType.oxygen_saturation, "0.97")
        heart_rate = _sample(db, source, SeriesType.heart_rate, "1")
        scaled = _sample(db, source, SeriesType.body_fat_percentage, "21.5")

        assert scale_apple_xml_percentages(db, dry_run=False) == 0
        assert _value(db, sdk) == Decimal("0.97")
        assert _value(db, heart_rate) == Decimal("1")
        assert _value(db, scaled) == Decimal("21.5")

    def test_queues_the_local_days_for_the_rollup(self, db: Session) -> None:
        source = _xml_source()
        _sample(db, source, SeriesType.oxygen_saturation, "0.97")
        pop_dirty_days(100)

        scale_apple_xml_percentages(db, dry_run=False)
        db.commit()

        assert pop_dirty_days(100) == [(source.id, date(2025, 3, 2))]

    def test_dry_run_changes_nothing(self, db: Session) -> None:
        oxygen = _sample(db, _xml_source(), SeriesType.oxygen_saturation, "0.97")

        assert scale_apple_xml_percentages(db, dry_run=True) == 1
        assert _value(db, oxygen) == Decimal("0.97")
