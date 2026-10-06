"""Google Health nutrition handler against a real database.

Runs the handler the way ``GoogleHealth247Data.load_and_save_all`` does: inside
``db.begin_nested()``, committing afterwards.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import EventRecord
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.nutrition import GoogleHealthApiNutrition
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler
from tests.factories import DataSourceFactory, UserFactory

START = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
WINDOW = (START - timedelta(hours=1), START + timedelta(hours=5))
DEVICE = {"platform": "ANDROID", "device": {"displayName": "Pixel Fold"}}
API = "https://health.googleapis.com"


def _point(name: str, start: datetime = START, nutrients: list[dict] | None = None, minutes: int = 30) -> dict:
    return {
        "name": f"users/me/dataTypes/nutrition-log/dataPoints/{name}",
        "dataSource": DEVICE,
        "nutritionLog": {
            "interval": {
                "startTime": start.isoformat(),
                "endTime": (start + timedelta(minutes=minutes)).isoformat(),
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


def _sync_like_data_247(db: Session, user_id: UUID, points: list[dict]) -> int:
    """Run the handler exactly as load_and_save_all does: under a savepoint, commit after."""
    nutrition = GoogleHealthApiNutrition(oauth=MagicMock(), connection_repo=MagicMock(), api_base_url=API)
    with (
        patch(
            "app.services.providers.google_health.nutrition.make_authenticated_request",
            return_value={"dataPoints": points},
        ),
        patch("app.services.providers.google_health.nutrition.store_raw_payload"),
    ):
        with db.begin_nested():
            count = nutrition.load_and_save(db, user_id, *WINDOW)
        db.commit()
    return count


def _meals(db: Session) -> list[EventRecord]:
    return db.query(EventRecord).filter(EventRecord.category == "meal").order_by(EventRecord.start_datetime).all()


def _nutrients_of(db: Session, meal_id: UUID) -> dict:
    db.expire_all()
    return db.get(EventRecord, meal_id).meal_detail.nutrients


class TestInsideTheSyncSavepoint:
    def test_first_import_creates_the_data_source_without_breaking_the_savepoint(self, db: Session) -> None:
        user = UserFactory()
        db.commit()

        assert _sync_like_data_247(db, user.id, [_point("Chicken")]) == 1
        assert _meals(db)[0].meal_detail.title == "Chicken"

    def test_meals_sharing_the_same_interval_all_land(self, db: Session) -> None:
        """MyFitnessPal logs every meal of a day with the same interval."""
        user = UserFactory()
        _existing_source(user)
        db.commit()

        count = _sync_like_data_247(db, user.id, [_point("Breakfast"), _point("Lunch"), _point("Dinner")])

        assert count == 3
        assert {m.meal_detail.title for m in _meals(db)} == {"Breakfast", "Lunch", "Dinner"}


class TestResync:
    def test_nutrients_are_replaced_with_the_latest_set(self, db: Session) -> None:
        user = UserFactory()
        _existing_source(user)
        db.commit()

        _sync_like_data_247(db, user.id, [_point("Chicken")])
        meal_id = _meals(db)[0].id
        assert _nutrients_of(db, meal_id) == {"dietary_energy_consumed": 100.0, "dietary_protein": 10.0}

        count = _sync_like_data_247(db, user.id, [_point("Chicken", nutrients=[])])

        assert count == 0
        assert len(_meals(db)) == 1
        assert _nutrients_of(db, meal_id) == {"dietary_energy_consumed": 100.0}

    def test_a_moved_window_updates_the_same_meal(self, db: Session) -> None:
        user = UserFactory()
        _existing_source(user)
        db.commit()

        _sync_like_data_247(db, user.id, [_point("Chicken")])
        count = _sync_like_data_247(db, user.id, [_point("Chicken", START + timedelta(minutes=15), minutes=45)])

        assert count == 0
        meals = _meals(db)
        assert len(meals) == 1
        db.refresh(meals[0])
        assert meals[0].start_datetime == START + timedelta(minutes=15)


class TestMealCreatedWebhook:
    def test_fires_once_after_the_sync_commits_with_the_meal_nutrients(self, db: Session) -> None:
        user = UserFactory()
        _existing_source(user)
        db.commit()

        with (
            patch("app.services.event_record_service.svix_service.is_enabled", return_value=True),
            patch("app.services.event_record_service.on_meal_created") as on_meal_created,
        ):
            _sync_like_data_247(db, user.id, [_point("Chicken")])
            _sync_like_data_247(db, user.id, [_point("Chicken")])

        on_meal_created.assert_called_once()
        kwargs = on_meal_created.call_args.kwargs
        assert kwargs["title"] == "Chicken"
        assert kwargs["calories_kcal"] == 100.0
        assert kwargs["macros"]["protein_g"] == 10.0


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
        ):
            saved = handler._fetch_and_save(db, user.id, "nutrition-log", *WINDOW)

        assert saved == 1
        db.expire_all()
        assert _meals(db)[0].meal_detail.title == "Chicken"
