"""Google Health API nutrition-log handler.

A nutrition-log DataPoint carries one food item (mealType, foodDisplayName) plus a handful
of nutrient values. Items sharing a source and start time are folded into one meal - the
same shape the SDK/HealthKit "Food" correlation path already models as a meal EventRecord
+ linked DataPointSeries samples. These tests cover the mapping from Google's wire shape to
that model, without touching a real database.
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


def _db() -> MagicMock:
    """A session mock whose begin_nested() context manager lets exceptions propagate.

    MagicMock's default __exit__ returns a truthy mock, which would swallow the very
    errors the handler's per-meal savepoint is supposed to surface to its except block.
    """
    db = MagicMock()
    db.begin_nested.return_value.__exit__.return_value = False
    return db


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


class TestGrouping:
    """Google emits one point per food item; items of one meal share a source and start time."""

    def test_same_start_items_fold_into_one_meal_with_summed_nutrients(
        self, nutrition: GoogleHealthApiNutrition
    ) -> None:
        chicken = _point("a", foodDisplayName="Chicken", energy={"kcal": 165})
        rice = _point("b", foodDisplayName="Rice", energy={"kcal": 200})
        salad = _point("c", foodDisplayName="Salad", energy={"kcal": 35})

        groups = nutrition._group_entries([chicken, rice, salad], *WINDOW)

        assert len(groups) == 1
        meal = groups[0]
        assert meal.title == "Chicken, Rice, Salad"
        assert meal.nutrients[SeriesType.dietary_energy_consumed] == Decimal("400")
        assert meal.nutrients[SeriesType.dietary_protein] == Decimal("93")  # 31 x 3
        assert meal.meal_type == "lunch"

    def test_items_at_different_start_times_stay_separate_meals(self, nutrition: GoogleHealthApiNutrition) -> None:
        dinner = _point("b", interval=_interval(START + timedelta(hours=1)))

        groups = nutrition._group_entries([_point("a"), dinner], *WINDOW)

        assert len(groups) == 2

    def test_items_from_different_devices_stay_separate_meals(self, nutrition: GoogleHealthApiNutrition) -> None:
        watch = _point("b", data_source={"platform": "ANDROID", "device": {"displayName": "Pixel Watch"}})

        groups = nutrition._group_entries([_point("a"), watch], *WINDOW)

        assert {g.device_model for g in groups} == {"Pixel Fold", "Pixel Watch"}

    def test_items_with_different_meal_types_at_the_same_start_stay_separate_meals(
        self, nutrition: GoogleHealthApiNutrition
    ) -> None:
        """A food logger can record two distinct meals (e.g. breakfast and a snack) with the
        same source and start instant - their nutrients must not be summed into one meal."""
        lunch = _point("a", mealType="LUNCH", foodDisplayName="Chicken", energy={"kcal": 165})
        snack = _point("b", mealType="SNACK", foodDisplayName="Chips", energy={"kcal": 150})

        groups = nutrition._group_entries([lunch, snack], *WINDOW)

        assert len(groups) == 2
        by_type = {g.meal_type: g for g in groups}
        assert by_type.keys() == {"lunch", "snack"}
        assert by_type["lunch"].title == "Chicken"
        assert by_type["lunch"].nutrients[SeriesType.dietary_energy_consumed] == Decimal("165")
        assert by_type["snack"].title == "Chips"
        assert by_type["snack"].nutrients[SeriesType.dietary_energy_consumed] == Decimal("150")

    def test_meal_end_is_the_latest_item_end(self, nutrition: GoogleHealthApiNutrition) -> None:
        longer = _point("b", interval=_interval(START, minutes=45))

        groups = nutrition._group_entries([_point("a"), longer], *WINDOW)

        assert groups[0].end == END + timedelta(minutes=15)

    def test_external_id_and_offset_come_from_a_stable_item_regardless_of_order(
        self, nutrition: GoogleHealthApiNutrition
    ) -> None:
        a, b = _point("a"), _point("b")

        forward = nutrition._group_entries([a, b], *WINDOW)[0]
        backward = nutrition._group_entries([b, a], *WINDOW)[0]

        assert forward.external_id == backward.external_id == a["name"]
        assert forward.zone_offset == "+02:00"

    def test_skips_entries_outside_the_window(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point(interval=_interval(START - timedelta(days=1)))

        assert nutrition._group_entries([payload], *WINDOW) == []

    def test_title_is_capped_to_the_column_length(self, nutrition: GoogleHealthApiNutrition) -> None:
        """A name over MealDetails.title's 255 chars must not fail the meal on every sync."""
        payload = _point(foodDisplayName="x" * 300)

        assert len(nutrition._group_entries([payload], *WINDOW)[0].title) == 255

    def test_no_titles_yields_none_not_empty_string(self, nutrition: GoogleHealthApiNutrition) -> None:
        payload = _point()
        del payload["nutritionLog"]["foodDisplayName"]

        assert nutrition._group_entries([payload], *WINDOW)[0].title is None


class TestBuildSamples:
    def test_samples_carry_the_meal_link_time_device_and_offset(self, nutrition: GoogleHealthApiNutrition) -> None:
        """Without device_model unrelated meals collide on the sample upsert key; without
        zone_offset a 23:30 local dinner lands in the next UTC day's totals."""
        meal_id = uuid4()
        group = nutrition._group_entries([_point()], *WINDOW)[0]

        samples = nutrition._build_samples(USER_ID, meal_id, group)

        assert samples
        assert all(s.event_record_id == meal_id for s in samples)
        assert all(s.recorded_at == START for s in samples)
        assert all(s.device_model == "Pixel Fold" for s in samples)
        assert all(s.zone_offset == "+02:00" for s in samples)


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
    """End-to-end fetch -> group -> persist, with the DB/service layer mocked out."""

    def _run(self, nutrition: GoogleHealthApiNutrition, points: list[dict], db: MagicMock | None = None) -> int:
        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": points},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.event_record_service") as event_record_service,
            patch("app.services.providers.google_health.nutrition.timeseries_service"),
        ):
            # A fresh insert: the service hands back the record it was given.
            event_record_service.create_or_update_meal.side_effect = lambda _db, record, _detail, **_kwargs: (
                MagicMock(id=record.id),
                True,
            )
            return nutrition.load_and_save(db if db is not None else _db(), USER_ID, *WINDOW)

    def test_saves_a_meal_under_its_own_savepoint_without_committing(self, nutrition: GoogleHealthApiNutrition) -> None:
        """The 24/7 sync wraps the handler in begin_nested(); a commit in here would close it."""
        db = _db()

        assert self._run(nutrition, [_point()], db=db) == 1
        db.begin_nested.assert_called_once()
        db.commit.assert_not_called()
        db.rollback.assert_not_called()

    def test_a_new_meal_does_not_prune_samples(self, nutrition: GoogleHealthApiNutrition) -> None:
        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": [_point()]},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.event_record_service") as event_record_service,
            patch("app.services.providers.google_health.nutrition.timeseries_service") as timeseries_service,
        ):
            event_record_service.create_or_update_meal.side_effect = lambda _db, record, _detail, **_kwargs: (
                MagicMock(id=record.id),
                True,
            )
            nutrition.load_and_save(_db(), USER_ID, *WINDOW)

        timeseries_service.crud.delete_stale_for_event_record.assert_not_called()

    def test_three_items_of_one_meal_count_as_one_meal(self, nutrition: GoogleHealthApiNutrition) -> None:
        assert self._run(nutrition, [_point("a"), _point("b"), _point("c")]) == 1

    def test_an_already_stored_meal_is_refreshed_but_not_counted(self, nutrition: GoogleHealthApiNutrition) -> None:
        """On re-sync the service hands back the existing row; its samples are still re-linked."""
        existing_id = uuid4()
        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": [_point()]},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.event_record_service") as event_record_service,
            patch("app.services.providers.google_health.nutrition.timeseries_service") as timeseries_service,
        ):
            event_record_service.create_or_update_meal.return_value = (MagicMock(id=existing_id), False)

            count = nutrition.load_and_save(_db(), USER_ID, *WINDOW)

        assert count == 0
        samples = timeseries_service.bulk_create_samples.call_args.args[1]
        assert samples
        assert all(s.event_record_id == existing_id for s in samples)
        # Nutrients Google no longer reports for this meal are dropped, keeping the current set.
        prune = timeseries_service.crud.delete_stale_for_event_record
        prune.assert_called_once()
        assert prune.call_args.args[1] == existing_id
        assert set(prune.call_args.args[2]) == {s.series_type for s in samples}

    def test_a_failing_meal_does_not_stop_the_rest(self, nutrition: GoogleHealthApiNutrition) -> None:
        good = _point("a")
        bad = _point("b", interval=_interval(START + timedelta(hours=1)))

        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": [good, bad]},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.event_record_service") as event_record_service,
            patch("app.services.providers.google_health.nutrition.timeseries_service"),
            patch("app.services.providers.google_health.nutrition.log_and_capture_error") as capture,
        ):
            calls: list[int] = []

            def create_or_update_meal(
                _db: object, record: object, _detail: object, **_kwargs: object
            ) -> tuple[MagicMock, bool]:
                # First meal fails, the rest insert normally.
                calls.append(1)
                if len(calls) == 1:
                    raise RuntimeError("boom")
                return MagicMock(id=record.id), True  # type: ignore[attr-defined]

            event_record_service.create_or_update_meal.side_effect = create_or_update_meal

            count = nutrition.load_and_save(_db(), USER_ID, *WINDOW)

        assert count == 1
        capture.assert_called_once()

    def test_a_failing_meal_is_confined_to_its_savepoint(self, nutrition: GoogleHealthApiNutrition) -> None:
        """A failure after the record was flushed is discarded by the meal's own savepoint -
        not by a session-wide rollback, which would also close the sync's enclosing savepoint."""
        db = _db()

        with (
            patch(
                "app.services.providers.google_health.nutrition.make_authenticated_request",
                return_value={"dataPoints": [_point()]},
            ),
            patch("app.services.providers.google_health.nutrition.store_raw_payload"),
            patch("app.services.providers.google_health.nutrition.event_record_service") as event_record_service,
            patch("app.services.providers.google_health.nutrition.timeseries_service") as timeseries_service,
            patch("app.services.providers.google_health.nutrition.log_and_capture_error"),
        ):
            event_record_service.create_or_update_meal.side_effect = lambda _db, record, _detail, **_kwargs: (
                MagicMock(id=record.id),
                True,
            )
            timeseries_service.bulk_create_samples.side_effect = RuntimeError("boom")

            count = nutrition.load_and_save(db, USER_ID, *WINDOW)

        assert count == 0
        db.rollback.assert_not_called()
        db.commit.assert_not_called()
        exc_type = db.begin_nested.return_value.__exit__.call_args.args[0]
        assert exc_type is RuntimeError


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
