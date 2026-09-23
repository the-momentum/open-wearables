"""Google Health nutrition handler against a real database.

The unit tests mock the session, so they cannot see how the handler behaves inside the
transaction the 24/7 sync puts it in: ``GoogleHealth247Data.load_and_save_all`` wraps
each handler in ``db.begin_nested()`` and commits afterwards. Any commit *inside* that
savepoint closes its context and fails every statement after it - which is exactly what
a data-source creation or a per-meal commit used to do. These tests run the handler the
way the sync does.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import DataPointSeries, EventRecord
from app.schemas.enums import SeriesType, get_series_type_id
from app.services.event_record_service import event_record_service
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.nutrition import GoogleHealthApiNutrition
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler
from tests.factories import DataSourceFactory, UserFactory

START = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
WINDOW = (START - timedelta(hours=1), START + timedelta(hours=5))
DEVICE = {"platform": "ANDROID", "device": {"displayName": "Pixel Fold"}}
API = "https://health.googleapis.com"


def _point(name: str, start: datetime = START, nutrients: list[dict] | None = None) -> dict:
    return {
        "name": f"users/me/dataTypes/nutrition-log/dataPoints/{name}",
        "dataSource": DEVICE,
        "nutritionLog": {
            "interval": {
                "startTime": start.isoformat(),
                "endTime": (start + timedelta(minutes=30)).isoformat(),
                "startUtcOffset": "7200s",
            },
            "mealType": "LUNCH",
            "foodDisplayName": name,
            "energy": {"kcal": 100},
            "nutrients": nutrients if nutrients is not None else [{"nutrient": "PROTEIN", "quantity": {"grams": 10}}],
        },
    }


def _existing_source(user) -> None:  # noqa: ANN001
    DataSourceFactory(user=user, device_model="Pixel Fold", source="google_health_api", provider="google_health")


def _sync_like_data_247(db: Session, user_id: UUID, points: list[dict]) -> tuple[int, list[Exception]]:
    """Run the handler exactly as load_and_save_all does: under a savepoint, commit after."""
    nutrition = GoogleHealthApiNutrition(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url=API)
    with (
        patch(
            "app.services.providers.google_health.nutrition.make_authenticated_request",
            return_value={"dataPoints": points},
        ),
        patch("app.services.providers.google_health.nutrition.store_raw_payload"),
        patch("app.services.providers.google_health.nutrition.log_and_capture_error") as capture,
    ):
        with db.begin_nested():
            count = nutrition.load_and_save(db, user_id, *WINDOW)
        db.commit()
    return count, [c.args[0] for c in capture.call_args_list]


def _meals(db: Session) -> list[EventRecord]:
    return db.query(EventRecord).filter(EventRecord.category == "meal").order_by(EventRecord.start_datetime).all()


def _series_of(db: Session, meal_id: UUID) -> set[int]:
    rows = db.query(DataPointSeries).filter(DataPointSeries.event_record_id == meal_id).all()
    return {r.series_type_definition_id for r in rows}


class TestInsideTheSyncSavepoint:
    def test_first_import_creates_the_data_source_without_breaking_the_savepoint(self, db: Session) -> None:
        """A brand-new device: the data source is created mid-handler and must only be flushed."""
        user = UserFactory()
        db.commit()

        count, swallowed = _sync_like_data_247(db, user.id, [_point("Chicken")])

        assert swallowed == []
        assert count == 1
        assert _meals(db)[0].meal_detail.title == "Chicken"

    def test_several_meals_in_one_sync_all_land(self, db: Session) -> None:
        """A commit after meal #1 would have failed meal #2 with 'closed transaction'."""
        user = UserFactory()
        _existing_source(user)
        db.commit()

        count, swallowed = _sync_like_data_247(
            db, user.id, [_point("Lunch"), _point("Snack", START + timedelta(hours=2))]
        )

        assert swallowed == []
        assert count == 2
        assert [m.meal_detail.title for m in _meals(db)] == ["Lunch", "Snack"]

    def test_a_meal_failing_after_its_record_was_flushed_is_discarded_whole(self, db: Session) -> None:
        """The per-meal savepoint must undo the flushed record and detail of the failing meal,
        while the meal before it and the meal after it both land."""
        user = UserFactory()
        _existing_source(user)
        db.commit()
        real = event_record_service.create_or_update_meal

        def flaky(db_: Session, record, detail):  # noqa: ANN001, ANN202
            result = real(db_, record, detail)  # record + detail are flushed by now
            if detail.title == "Bad":
                raise RuntimeError("boom")
            return result

        nutrition = GoogleHealthApiNutrition(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url=API)
        points = [
            _point("Good"),
            _point("Bad", START + timedelta(hours=1)),
            _point("Later", START + timedelta(hours=2)),
        ]
        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": points},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.log_and_capture_error") as capture,
            patch.object(event_record_service, "create_or_update_meal", side_effect=flaky),
        ):
            with db.begin_nested():
                count = nutrition.load_and_save(db, user.id, *WINDOW)
            db.commit()

        assert count == 2
        assert [type(c.args[0]) for c in capture.call_args_list] == [RuntimeError]
        assert [m.meal_detail.title for m in _meals(db)] == ["Good", "Later"]


class TestResync:
    def test_nutrients_google_stopped_reporting_are_removed(self, db: Session) -> None:
        user = UserFactory()
        _existing_source(user)
        db.commit()
        protein_id = get_series_type_id(SeriesType.dietary_protein)
        energy_id = get_series_type_id(SeriesType.dietary_energy_consumed)

        _sync_like_data_247(db, user.id, [_point("Chicken")])
        meal_id = _meals(db)[0].id
        assert _series_of(db, meal_id) == {energy_id, protein_id}

        count, swallowed = _sync_like_data_247(db, user.id, [_point("Chicken", nutrients=[])])

        assert swallowed == []
        assert count == 0  # refreshed, not inserted
        assert _series_of(db, meal_id) == {energy_id}
        assert len(_meals(db)) == 1


class TestWebhookPath:
    def test_the_webhook_route_commits_the_batch(self, db: Session) -> None:
        """No savepoint wraps the handler here, so _fetch_and_save must commit itself."""
        user = UserFactory()
        db.commit()
        data_247 = GoogleHealth247Data(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url=API)
        handler = GoogleWebhookHandler(data_247=data_247, workouts=MagicMock())

        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": [_point("Chicken")]},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.log_and_capture_error") as capture,
        ):
            saved = handler._fetch_and_save(db, user.id, "nutrition-log", *WINDOW)

        assert capture.call_args_list == []
        assert saved == 1
        db.expire_all()
        assert _meals(db)[0].meal_detail.title == "Chicken"
