"""Food and water items deleted on the phone and sent in an SDK sync's data.deletions."""

from datetime import date, datetime
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.models import DataSource, SeriesAggregate, SeriesSample
from app.repositories.series_rollup_repository import SeriesRollupRepository
from app.schemas.enums.series_types import get_series_type_from_id
from app.services.sdk.import_service import ImportService
from tests.factories import UserFactory


class TestSDKImportIntakeDeletions:
    """Food and water items the user deleted on the phone are removed by their id; an edit is a deletion plus a new
    item, as HealthKit gives the edited item a new id."""

    ENERGY = "HKQuantityTypeIdentifierDietaryEnergyConsumed"

    @pytest.fixture
    def import_service(self) -> ImportService:
        return ImportService()

    @staticmethod
    def _sync(
        db: Session,
        import_service: ImportService,
        user_id: UUID,
        records: list[dict[str, Any]] | None = None,
        deletions: list[dict[str, Any]] | None = None,
        provider: str = "apple",
    ) -> Any:
        payload = {
            "provider": provider,
            "sdkVersion": "1.2.0",
            "syncTimestamp": "2026-09-18T12:00:00Z",
            "data": {"records": records or [], "deletions": deletions or []},
        }
        return import_service.load_data(db, payload, str(user_id))

    @staticmethod
    def _values(db: Session, user_id: UUID) -> dict[str, list[float]]:
        """Stored values per series, for one user, smallest first."""
        values: dict[str, list[float]] = {}
        for sample in db.query(SeriesSample).join(DataSource).filter(DataSource.user_id == user_id):
            series = get_series_type_from_id(sample.series_type_definition_id).value
            values.setdefault(series, []).append(float(sample.value))
        return {series: sorted(found) for series, found in values.items()}

    @staticmethod
    def _item(external_id: str, metric_type: str, value: float, unit: str, at: str = "12:30") -> dict[str, Any]:
        """A food or water item logged on 18 Sep 2026 at ``at`` (UTC)."""
        return {
            "id": external_id,
            "type": metric_type,
            "value": value,
            "unit": unit,
            "startDate": f"2026-09-18T{at}:00Z",
            "endDate": f"2026-09-18T{at}:00Z",
            "source": {"name": "MyFitnessPal", "bundleIdentifier": "com.myfitnesspal.mfp"},
        }

    @classmethod
    def _deleted(cls, external_id: str, metric_type: str | None = None) -> dict[str, Any]:
        return {"id": external_id, "type": metric_type or cls.ENERGY}

    def _meals(self) -> list[dict[str, Any]]:
        return [
            self._item("breakfast-kcal", self.ENERGY, 520, "Cal", at="08:00"),
            self._item("lunch-kcal", self.ENERGY, 610, "Cal"),
        ]

    def test_a_deleted_item_is_removed(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())

        result = self._sync(db, import_service, user.id, deletions=[self._deleted("lunch-kcal")])

        assert self._values(db, user.id) == {"dietary_energy_consumed": [520.0]}
        assert result["records_deleted"] == 1

    def test_an_edited_item_replaces_the_old_one(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())

        self._sync(
            db,
            import_service,
            user.id,
            records=[self._item("lunch-kcal-edited", self.ENERGY, 450, "Cal")],
            deletions=[self._deleted("lunch-kcal")],
        )

        assert self._values(db, user.id) == {"dietary_energy_consumed": [450.0, 520.0]}

    def test_an_item_deleted_in_the_batch_that_carries_it_stays_deleted(
        self, db: Session, import_service: ImportService
    ) -> None:
        user = UserFactory()

        self._sync(db, import_service, user.id, self._meals(), deletions=[self._deleted("lunch-kcal")])

        assert self._values(db, user.id) == {"dietary_energy_consumed": [520.0]}

    def test_an_item_deleted_in_its_own_batch_leaves_the_item_stored_at_its_instant(
        self, db: Session, import_service: ImportService
    ) -> None:
        """Written first, the item would replace the lunch stored at its instant and its deletion remove the row."""
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())

        self._sync(
            db,
            import_service,
            user.id,
            records=[self._item("snack-kcal", self.ENERGY, 180, "Cal")],
            deletions=[self._deleted("snack-kcal")],
        )

        assert self._values(db, user.id) == {"dietary_energy_consumed": [520.0, 610.0]}

    def test_an_item_deleted_in_its_own_batch_is_not_sent_to_webhooks(
        self, db: Session, import_service: ImportService
    ) -> None:
        """The timeseries webhook reports the samples a batch writes."""
        user = UserFactory()
        series = import_service.timeseries_service

        with patch.object(series, "bulk_create_samples", wraps=series.bulk_create_samples) as written:
            self._sync(db, import_service, user.id, self._meals(), deletions=[self._deleted("lunch-kcal")])

        assert [s.external_id for call in written.call_args_list for s in call.args[1]] == ["breakfast-kcal"]

    def test_a_deletion_queues_the_day_for_the_rollup(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())
        source_id = db.query(DataSource.id).filter(DataSource.user_id == user.id).scalar()

        with patch("app.repositories.data_point_series_repository.mark_dirty_days") as mark_dirty_days:
            self._sync(db, import_service, user.id, deletions=[self._deleted("lunch-kcal")])

        mark_dirty_days.assert_called_once()
        assert set(mark_dirty_days.call_args.args[1]) == {(source_id, datetime(2026, 9, 18).date())}

    def _day_totals(self, db: Session, user_id: UUID, day: date = date(2026, 9, 18)) -> list[float]:
        source_id = db.query(DataSource.id).filter(DataSource.user_id == user_id).scalar()
        SeriesRollupRepository().roll_up(db, source_id, [day])
        rows = db.query(SeriesAggregate).filter(SeriesAggregate.data_source_id == source_id).all()
        return [float(row.sum) for row in rows]

    def test_deleting_one_of_the_items_of_a_day_lowers_its_total(
        self, db: Session, import_service: ImportService
    ) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())
        assert self._day_totals(db, user.id) == [1130.0]

        self._sync(db, import_service, user.id, deletions=[self._deleted("lunch-kcal")])

        assert self._day_totals(db, user.id) == [520.0]

    def test_an_unknown_id_changes_nothing(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())

        result = self._sync(db, import_service, user.id, deletions=[self._deleted("never-synced")])

        assert self._values(db, user.id) == {"dietary_energy_consumed": [520.0, 610.0]}
        assert result["records_deleted"] == 0

    def test_other_series_are_not_deleted(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        heart_rate = "HKQuantityTypeIdentifierHeartRate"
        self._sync(db, import_service, user.id, [self._item("hr-1", heart_rate, 70, "count/min")])

        self._sync(db, import_service, user.id, deletions=[self._deleted("hr-1", heart_rate)])

        assert self._values(db, user.id) == {"heart_rate": [70.0]}

    def test_a_deletion_only_reaches_its_own_user(self, db: Session, import_service: ImportService) -> None:
        owner, other = UserFactory(), UserFactory()
        self._sync(db, import_service, owner.id, self._meals())
        self._sync(db, import_service, other.id, self._meals())

        self._sync(db, import_service, other.id, deletions=[self._deleted("lunch-kcal")])

        assert self._values(db, owner.id) == {"dietary_energy_consumed": [520.0, 610.0]}
        assert self._values(db, other.id) == {"dietary_energy_consumed": [520.0]}

    def test_a_deletion_only_reaches_its_own_provider(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())
        self._sync(db, import_service, user.id, self._meals(), provider="samsung")

        self._sync(db, import_service, user.id, deletions=[self._deleted("lunch-kcal")], provider="samsung")

        assert self._values(db, user.id) == {"dietary_energy_consumed": [520.0, 520.0, 610.0]}

    def test_a_deletion_only_reaches_its_own_type(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        protein = "HKQuantityTypeIdentifierDietaryProtein"
        self._sync(db, import_service, user.id, [self._item("item-1", self.ENERGY, 520, "Cal")])
        self._sync(db, import_service, user.id, [self._item("item-1", protein, 24, "g")])

        self._sync(db, import_service, user.id, deletions=[self._deleted("item-1")])

        assert self._values(db, user.id) == {"dietary_protein": [24.0]}

    def test_an_invalid_deletion_is_dropped_and_the_rest_kept(self, db: Session, import_service: ImportService) -> None:
        user = UserFactory()
        self._sync(db, import_service, user.id, self._meals())

        result = self._sync(
            db,
            import_service,
            user.id,
            deletions=[{"type": self.ENERGY}, self._deleted(""), self._deleted("x" * 101), self._deleted("lunch-kcal")],
        )

        assert self._values(db, user.id) == {"dietary_energy_consumed": [520.0]}
        assert [(d["collection"], d["index"]) for d in result["dropped"]] == [
            ("deletions", 0),
            ("deletions", 1),
            ("deletions", 2),
        ]
