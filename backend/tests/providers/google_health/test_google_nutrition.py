"""Google Health API nutrition-log handler.

Each nutrition-log DataPoint becomes its own meal (EventRecord + MealDetails with nutrients),
keyed by Google's per-DataPoint resource ``name`` as ``external_id``. No real database here.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.enums import SeriesType
from app.services.providers.google_health.data_247 import GoogleHealth247Data
from app.services.providers.google_health.nutrition import GoogleHealthApiNutrition, civil_start_filter
from app.services.providers.google_health.webhook_handler import GoogleWebhookHandler

USER_ID = uuid4()
START = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 10, 8, 30, tzinfo=timezone.utc)
WINDOW = (START - timedelta(hours=1), END + timedelta(hours=1))
PIXEL = {"platform": "ANDROID", "device": {"displayName": "Pixel Fold"}}


def _interval(start: datetime, minutes: int = 30) -> dict:
    return {"startTime": start.isoformat(), "endTime": (start + timedelta(minutes=minutes)).isoformat()}


def _point(name: str = "abc123", data_source: dict | None = None, **overrides: object) -> dict:
    """A realistic nutrition-log DataPoint (see developers.google.com/health/data-types/nutrition)."""
    nutrition = {
        "interval": {"startTime": START.isoformat(), "endTime": END.isoformat(), "startUtcOffset": "7200s"},
        "mealType": "LUNCH",
        "foodDisplayName": "Grilled Chicken Breast",
        "energy": {"kcal": 165},
        "totalCarbohydrate": {"grams": 0},
        "totalFat": {"grams": 3.6},
        "nutrients": [
            {"nutrient": "PROTEIN", "quantity": {"grams": 31}},
            {"nutrient": "SODIUM", "quantity": {"grams": 0.074}},
            {"nutrient": "TRANS_FAT", "quantity": {"grams": 0.1}},
        ],
    }
    nutrition.update(overrides)
    return {
        "name": f"users/me/dataTypes/nutrition-log/dataPoints/{name}",
        "dataSource": data_source if data_source is not None else PIXEL,
        "nutritionLog": nutrition,
    }


@pytest.fixture
def nutrition() -> GoogleHealthApiNutrition:
    return GoogleHealthApiNutrition(
        oauth=MagicMock(),
        connection_repo=MagicMock(),
        api_base_url="https://health.googleapis.com",
    )


class TestNutrients:
    """Value extraction and unit conversion from Google's typed-quantity wire shape."""

    def test_extracts_primary_and_nutrient_fields(self, nutrition: GoogleHealthApiNutrition) -> None:
        values = nutrition._nutrients(_point()["nutritionLog"])

        assert values[SeriesType.dietary_energy_consumed] == Decimal("165")
        assert values[SeriesType.dietary_fat_total] == Decimal("3.6")
        assert values[SeriesType.dietary_protein] == Decimal("31")

    def test_converts_gram_denominated_nutrients_to_the_series_unit(self, nutrition: GoogleHealthApiNutrition) -> None:
        """Google reports every nutrient mass in grams; sodium/potassium/cholesterol store mg."""
        values = nutrition._nutrients(_point()["nutritionLog"])

        assert values[SeriesType.dietary_sodium] == Decimal("74.000")

    def test_trans_fat_is_not_converted(self, nutrition: GoogleHealthApiNutrition) -> None:
        values = nutrition._nutrients(_point()["nutritionLog"])

        assert values[SeriesType.dietary_fat_trans] == Decimal("0.1")

    def test_absent_fields_are_skipped_not_zeroed(self, nutrition: GoogleHealthApiNutrition) -> None:
        """A carb value of 0 is real data and must be kept; a genuinely missing field must not appear."""
        values = nutrition._nutrients(_point()["nutritionLog"])

        assert SeriesType.dietary_carbohydrates in values  # explicit 0, not missing
        assert SeriesType.dietary_fiber not in values  # never present in the payload
        assert SeriesType.dietary_potassium not in values

    def test_malformed_nutrient_entries_are_ignored(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point(nutrients=["not-a-dict", {"quantity": {"grams": 5}}, {"nutrient": "PROTEIN"}])["nutritionLog"]

        values = nutrition._nutrients(payload)

        # A nutrient entry with no quantity yields no reading, but must not crash the rest.
        assert SeriesType.dietary_protein not in values

    def test_maps_the_api_nutrient_enum_and_scales_to_each_series_unit(
        self, nutrition: GoogleHealthApiNutrition
    ) -> None:
        payload = _point(
            energyFromFat={"kcal": 32},
            nutrients=[
                {"nutrient": "DIETARY_FIBER", "quantity": {"grams": 7.5}},
                {"nutrient": "CALCIUM", "quantity": {"grams": 0.2753}},
                {"nutrient": "VITAMIN_D", "quantity": {"grams": 0.000005}},
                {"nutrient": "CAFFEINE", "quantity": {"grams": 0.095}},
            ],
        )["nutritionLog"]

        values = nutrition._nutrients(payload)

        assert values[SeriesType.dietary_energy_from_fat] == Decimal("32")
        assert values[SeriesType.dietary_fiber] == Decimal("7.5")
        assert values[SeriesType.dietary_calcium] == Decimal("275.3")
        assert values[SeriesType.dietary_vitamin_d] == Decimal("5")
        assert values[SeriesType.dietary_caffeine] == Decimal("95")

    def test_top_level_carbohydrate_wins_over_the_nutrients_entry(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point(
            totalCarbohydrate={"grams": 40},
            nutrients=[{"nutrient": "CARBOHYDRATES", "quantity": {"grams": 39.8}}],
        )["nutritionLog"]

        assert nutrition._nutrients(payload)[SeriesType.dietary_carbohydrates] == Decimal("40")


class TestParsePoint:
    """Every nutrition-log DataPoint becomes its own, independent meal - no folding across points."""

    def test_a_point_becomes_a_meal_with_its_own_name_as_external_id(self, nutrition: GoogleHealthApiNutrition) -> None:
        point = _point("a", foodDisplayName="Chicken", mealType="LUNCH")

        meal = nutrition._parse_point(point, *WINDOW)

        assert meal is not None
        assert meal.external_id == point["name"]
        assert meal.title == "Chicken"
        assert meal.meal_type == "lunch"
        assert meal.device_model == "Pixel Fold"
        assert meal.zone_offset == "+02:00"
        assert meal.start == START
        assert meal.nutrients[SeriesType.dietary_energy_consumed] == Decimal("165")
        assert meal.nutrients[SeriesType.dietary_protein] == Decimal("31")

    def test_two_points_with_identical_start_device_and_meal_type_are_two_separate_meals(
        self, nutrition: GoogleHealthApiNutrition
    ) -> None:
        """Even when start, device, and mealType all match, each DataPoint keeps its own identity."""
        a = _point("a", foodDisplayName="Chicken")
        b = _point("b", foodDisplayName="Rice")

        meal_a = nutrition._parse_point(a, *WINDOW)
        meal_b = nutrition._parse_point(b, *WINDOW)

        assert meal_a is not None
        assert meal_b is not None
        assert meal_a.external_id != meal_b.external_id
        assert meal_a.external_id == a["name"]
        assert meal_b.external_id == b["name"]
        assert meal_a.title == "Chicken"
        assert meal_b.title == "Rice"
        # No summing across points - each nutrient set is that point's own.
        assert meal_a.nutrients[SeriesType.dietary_energy_consumed] == Decimal("165")
        assert meal_b.nutrients[SeriesType.dietary_energy_consumed] == Decimal("165")

    def test_skips_a_point_outside_the_window(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point(interval=_interval(START - timedelta(days=1)))

        assert nutrition._parse_point(payload, *WINDOW) is None

    def test_skips_a_point_with_a_malformed_nutrition_log(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point()
        payload["nutritionLog"] = "not-a-dict"

        assert nutrition._parse_point(payload, *WINDOW) is None

    def test_title_is_capped_to_the_column_length(self, nutrition: GoogleHealthApiNutrition) -> None:
        """A name over MealDetails.title's 255 chars must not fail the meal on every sync."""
        payload = _point(foodDisplayName="x" * 300)

        meal = nutrition._parse_point(payload, *WINDOW)

        assert meal is not None
        assert len(meal.title) == 255

    def test_no_title_yields_none_not_empty_string(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point()
        del payload["nutritionLog"]["foodDisplayName"]

        meal = nutrition._parse_point(payload, *WINDOW)

        assert meal is not None
        assert meal.title is None


class TestFetch:
    def test_filters_on_civil_start_day_widened_a_day_each_way(self) -> None:
        """Session types can only be filtered on civil start time (no offset), so the fetch
        widens the window by a day and trims to the physical window client-side."""
        member = "nutrition_log.interval.civil_start_time"

        assert civil_start_filter(START, END) == f'{member} >= "2026-09-09" AND {member} < "2026-09-11"'

    def test_passes_the_filter_to_every_page_request(self, nutrition: GoogleHealthApiNutrition) -> None:
        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                side_effect=[{"dataPoints": [], "nextPageToken": "t"}, {"dataPoints": []}],
            ) as request,
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
        ):
            nutrition._fetch(MagicMock(), USER_ID, START, END)

        assert request.call_count == 2
        for call in request.call_args_list:
            assert call.kwargs["params"]["filter"] == civil_start_filter(START, END)
        assert request.call_args_list[1].kwargs["params"]["pageToken"] == "t"


class TestLoadAndSave:
    """Fetch -> parse -> one batch upsert, with the service layer mocked out."""

    def _run(self, nutrition: GoogleHealthApiNutrition, points: list[dict], db: MagicMock) -> MagicMock:
        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": points},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.event_record_service") as event_record_service,
        ):
            event_record_service.upsert_meals.side_effect = lambda _db, meals: len(meals)
            self.count = nutrition.load_and_save(db, USER_ID, *WINDOW)
        return event_record_service.upsert_meals

    def test_upserts_every_point_as_its_own_meal_in_one_batch(self, nutrition: GoogleHealthApiNutrition) -> None:
        upsert = self._run(nutrition, [_point("a"), _point("b"), _point("c")], MagicMock())

        upsert.assert_called_once()
        meals = upsert.call_args.args[1]
        assert [record.external_id for record, _ in meals] == [
            f"users/me/dataTypes/nutrition-log/dataPoints/{name}" for name in "abc"
        ]
        assert self.count == 3

    def test_nutrients_go_to_the_meal_detail(self, nutrition: GoogleHealthApiNutrition) -> None:
        upsert = self._run(nutrition, [_point()], MagicMock())

        record, detail = upsert.call_args.args[1][0]
        assert detail.record_id == record.id
        assert detail.meal_type == "lunch"
        assert detail.nutrients[SeriesType.dietary_protein] == 31.0
        assert detail.nutrients[SeriesType.dietary_sodium] == 74.0

    def test_never_commits_or_rolls_back(self, nutrition: GoogleHealthApiNutrition) -> None:
        """The 24/7 sync wraps the handler in its own savepoint and commits after it."""
        db = MagicMock()

        self._run(nutrition, [_point()], db)

        db.commit.assert_not_called()
        db.rollback.assert_not_called()

    def test_no_points_skip_the_upsert(self, nutrition: GoogleHealthApiNutrition) -> None:
        upsert = self._run(nutrition, [], MagicMock())

        upsert.assert_not_called()
        assert self.count == 0


class TestWebhookRouting:
    """nutrition-log notifications are routed to the nutrition handler, like sleep/exercise."""

    def test_a_nutrition_log_notification_is_routed_to_the_nutrition_handler(self) -> None:
        db = MagicMock()
        data_247 = GoogleHealth247Data(
            oauth=MagicMock(), connection_repo=MagicMock(), api_base_url="https://health.googleapis.com"
        )
        handler = GoogleWebhookHandler(data_247=data_247, workouts=MagicMock())

        with (
            patch.object(data_247.nutrition, "load_and_save", return_value=2) as nutrition_load,
            patch.object(data_247, "sync_data_type") as sync_data_type,
        ):
            saved = handler._fetch_and_save(db, USER_ID, "nutrition-log", START, END)

        assert saved == 2
        nutrition_load.assert_called_once_with(db, USER_ID, START, END)
        sync_data_type.assert_not_called()
        # Nothing wraps the handler on this path, so the batch must be committed here.
        db.commit.assert_called_once()
