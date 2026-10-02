"""Google Health API nutrition handler.

Fetches ``nutrition-log`` sessions via the dataPoints ``list`` operation and stores them
as ``EventRecord(category="meal")`` + ``MealDetails``, with every present nutrient
written as a ``DataPointSeries`` sample linked back via ``event_record_id`` - the same
model the SDK/HealthKit meal-correlation import path already uses (see
``app/services/sdk/import_service.py``). Composed into GoogleHealth247Data.load_and_save_all.

Google emits one DataPoint per *food item* (``foodDisplayName``), and assigns every
DataPoint a stable, unique resource ``name`` (e.g.
``users/123/dataTypes/nutrition-log/dataPoints/3608527872883869712``). Each DataPoint is
stored as its own, independent meal, with that ``name`` used verbatim as ``external_id`` -
there is no grouping of multiple DataPoints into one meal.

Google wraps every nutrient value in a typed quantity object (``{"kcal": ...}`` for
energy, ``{"grams": ...}`` for everything else - including sodium/potassium/cholesterol,
which the unified series stores in mg). Only the fields Google actually returns are
mapped; most micronutrients (calcium, iron, vitamins, ...) aren't exposed by this API and
are simply absent from the payload - see the nutrition-fields matrix in the repo root for
the full cross-provider comparison.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.constants.google_health_endpoints import LIST_ENDPOINT as DATAPOINTS_LIST_ENDPOINT
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import ProviderName, SeriesType, daily_total_flag
from app.schemas.model_crud.activities import EventRecordCreate, MealDetailCreate, TimeSeriesSampleCreate
from app.services.event_record_service import event_record_service
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.google_health.helpers import (
    GOOGLE_HEALTH_API_SOURCE,
    extract_source,
    parse_interval,
    parse_page,
    read_number,
    zone_offset_from,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error

_G_TO_MG = Decimal(1000)

# MealDetails.title is str_255; a longer foodDisplayName would fail the whole meal on every sync.
_TITLE_MAX_LEN = 255

# (payload field, quantity subfield, unified series) for the value object's top-level fields.
NUTRITION_PRIMARY_FIELDS: tuple[tuple[str, str, SeriesType], ...] = (
    ("energy", "kcal", SeriesType.dietary_energy_consumed),
    ("totalCarbohydrate", "grams", SeriesType.dietary_carbohydrates),
    ("totalFat", "grams", SeriesType.dietary_fat_total),
)

# Google's `nutrients` Nutrient enum -> unified series, with the gram->mg scale the
# unified series needs (Google reports every nutrient mass in grams, regardless of the
# nutrient's conventional display unit).
NUTRIENT_FIELDS: dict[str, tuple[SeriesType, Decimal]] = {
    "FIBER": (SeriesType.dietary_fiber, Decimal(1)),
    "SUGAR": (SeriesType.dietary_sugar, Decimal(1)),
    "SATURATED_FAT": (SeriesType.dietary_fat_saturated, Decimal(1)),
    "MONOUNSATURATED_FAT": (SeriesType.dietary_fat_monounsaturated, Decimal(1)),
    "POLYUNSATURATED_FAT": (SeriesType.dietary_fat_polyunsaturated, Decimal(1)),
    "TRANS_FAT": (SeriesType.dietary_fat_trans, Decimal(1)),
    "CHOLESTEROL": (SeriesType.dietary_cholesterol, _G_TO_MG),
    "PROTEIN": (SeriesType.dietary_protein, Decimal(1)),
    "SODIUM": (SeriesType.dietary_sodium, _G_TO_MG),
    "POTASSIUM": (SeriesType.dietary_potassium, _G_TO_MG),
}

NUTRITION_SERIES_TYPES: frozenset[SeriesType] = frozenset(
    {series_type for _, _, series_type in NUTRITION_PRIMARY_FIELDS}
    | {series_type for series_type, _ in NUTRIENT_FIELDS.values()}
)


def civil_start_filter(start_time: datetime, end_time: datetime) -> str:
    """AIP-160 filter for the fetch window.

    Session types (excl. sleep/ECG) can only be filtered on civil start time, which carries
    no offset, so the window is widened a day each way and the caller trims to the physical
    [start_time, end_time) afterwards - same approach as data_247's session-interval metrics.
    """
    member = "nutrition_log.interval.civil_start_time"
    low = (start_time.date() - timedelta(days=1)).isoformat()
    high = (end_time.date() + timedelta(days=1)).isoformat()
    return f'{member} >= "{low}" AND {member} < "{high}"'


@dataclass
class _Meal:
    """One nutrition-log DataPoint, ready to be stored as its own meal."""

    external_id: str | None
    source_name: str
    device_model: str | None
    start: datetime
    end: datetime
    zone_offset: str | None
    title: str | None
    meal_type: str | None
    nutrients: dict[SeriesType, Decimal]


class GoogleHealthApiNutrition:
    """Fetches Google Health API nutrition-log sessions and stores them as meal EventRecords."""

    LIST_ENDPOINT = DATAPOINTS_LIST_ENDPOINT.format(data_type="nutrition-log")
    PAGE_SIZE = 1000

    def __init__(self, oauth: BaseOAuthTemplate, connection_repo: UserConnectionRepository, api_base_url: str):
        self.oauth = oauth
        self.connection_repo = connection_repo
        self.provider_name = "google_health"
        self.api_base_url = api_base_url
        self.logger = logging.getLogger(self.__class__.__name__)

    def load_and_save(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> int:
        """Fetch nutrition-log entries starting in the window and store each as its own meal.

        Never commits or rolls back the session: the 24/7 sync runs this inside its own
        ``begin_nested()`` savepoint, and a commit in here would close that context and fail
        every statement after it. Each meal gets a savepoint of its own instead, so one bad
        meal is discarded without touching the others; the caller commits the batch.

        Returns the number of meals newly inserted; meals that already existed (re-sync)
        have their end, title, type and nutrient values refreshed but are not counted.
        """
        count = 0
        for point in self._fetch(db, user_id, start_time, end_time):
            meal = self._parse_point(point, start_time, end_time)
            if meal is None:
                continue
            try:
                with db.begin_nested():
                    inserted = self._save_meal(db, user_id, meal)
            except Exception as e:
                log_and_capture_error(
                    e,
                    self.logger,
                    f"Google nutrition sync failed for a meal: {e}",
                    extra={"user_id": str(user_id), "provider": self.provider_name, "external_id": meal.external_id},
                )
                continue
            if inserted:
                count += 1
        return count

    def _fetch(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict[str, Any]]:
        points: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": self.PAGE_SIZE, "filter": civil_start_filter(start_time, end_time)}
            if page_token:
                params["pageToken"] = page_token
            response = make_authenticated_request(
                db=db,
                user_id=user_id,
                connection_repo=self.connection_repo,
                oauth=self.oauth,
                api_base_url=self.api_base_url,
                provider_name=self.provider_name,
                endpoint=self.LIST_ENDPOINT,
                method="GET",
                params=params,
            )
            store_raw_payload(
                source="api_response",
                provider=self.provider_name,
                payload=response,
                user_id=str(user_id),
                trace_id=self.LIST_ENDPOINT,
            )
            page = parse_page(response, self.LIST_ENDPOINT)
            points.extend(page.data_points)
            page_token = page.next_page_token
            if not page_token:
                break
        return points

    def _parse_point(self, point: dict[str, Any], start_time: datetime, end_time: datetime) -> "_Meal | None":
        """Turn one nutrition-log DataPoint into a meal, or None if it's malformed or outside the window."""
        nutrition = point.get("nutritionLog")
        if not isinstance(nutrition, dict):
            return None
        interval = nutrition.get("interval") or {}
        start, end = parse_interval(interval)
        if start is None or end is None or not (start_time <= start < end_time):
            return None
        source_name, device_model = extract_source(point.get("dataSource"))
        title = nutrition.get("foodDisplayName")
        return _Meal(
            external_id=point.get("name"),
            source_name=source_name,
            device_model=device_model,
            start=start,
            end=end,
            zone_offset=zone_offset_from(interval.get("startUtcOffset")),
            title=title[:_TITLE_MAX_LEN] if title else None,
            meal_type=(nutrition.get("mealType") or "").lower() or None,
            nutrients=self._nutrients(nutrition),
        )

    @staticmethod
    def _nutrients(nutrition: dict[str, Any]) -> dict[SeriesType, Decimal]:
        """Read every nutrient Google returned for one item, scaled to the unified series unit."""
        values: dict[SeriesType, Decimal] = {}
        for fld, subfield, series_type in NUTRITION_PRIMARY_FIELDS:
            value = read_number(nutrition, fld, subfield=subfield)
            if value is not None:
                values[series_type] = value

        nutrient_quantities: dict[str, Any] = {
            entry["nutrient"]: entry.get("quantity")
            for entry in nutrition.get("nutrients") or []
            if isinstance(entry, dict) and entry.get("nutrient")
        }
        for key, (series_type, scale) in NUTRIENT_FIELDS.items():
            value = read_number(nutrient_quantities, key, subfield="grams", scale=scale)
            if value is not None:
                values[series_type] = value
        return values

    def _save_meal(self, db: DbSession, user_id: UUID, meal: "_Meal") -> bool:
        """Write (or refresh) the meal record, its detail, and its nutrient samples.

        Only flushes - the caller's savepoint makes the three writes stand or fall together,
        so a failure partway through never leaves an orphaned meal without detail or nutrients.

        Returns True when the meal was newly inserted, False when an existing one was refreshed.
        """
        record = EventRecordCreate(
            id=uuid4(),
            category="meal",
            provider=ProviderName.GOOGLE_HEALTH.value,
            source=GOOGLE_HEALTH_API_SOURCE,
            source_name=meal.source_name,
            device_model=meal.device_model,
            external_id=meal.external_id,
            start_datetime=meal.start,
            end_datetime=meal.end,
            duration_seconds=int((meal.end - meal.start).total_seconds()),
            zone_offset=meal.zone_offset,
            user_id=user_id,
        )
        detail = MealDetailCreate(record_id=record.id, title=meal.title, meal_type=meal.meal_type)
        saved, inserted = event_record_service.create_or_update_meal(db, record, detail)
        if inserted:
            event_record_service.schedule_meal_webhook(db, saved.id, record, detail, meal.nutrients)

        if not inserted:
            # A nutrient the provider stopped reporting must not linger from the previous sync.
            timeseries_service.crud.delete_stale_for_event_record(db, saved.id, meal.nutrients.keys())
        samples = self._build_samples(user_id, saved.id, meal)
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return inserted

    def _build_samples(self, user_id: UUID, meal_id: UUID, meal: "_Meal") -> list[TimeSeriesSampleCreate]:
        return [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                provider=self.provider_name,
                source=GOOGLE_HEALTH_API_SOURCE,
                device_model=meal.device_model,
                recorded_at=meal.start,
                zone_offset=meal.zone_offset,
                value=value,
                series_type=series_type,
                is_daily_total=daily_total_flag(series_type, is_daily=False),
                event_record_id=meal_id,
            )
            for series_type, value in meal.nutrients.items()
        ]
