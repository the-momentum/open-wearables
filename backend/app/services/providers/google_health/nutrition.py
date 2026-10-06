"""Google Health API nutrition-log: each DataPoint is stored as its own meal, nutrients in MealDetails."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.constants.google_health_endpoints import LIST_ENDPOINT as DATAPOINTS_LIST_ENDPOINT
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import ProviderName, SeriesType, get_series_type_unit
from app.schemas.model_crud.activities import EventRecordCreate, MealDetailCreate
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

# MealDetails.title is str_255; a longer foodDisplayName would fail the whole meal on every sync.
_TITLE_MAX_LEN = 255

# NutritionLog top-level fields: (field, quantity subfield, series).
NUTRITION_PRIMARY_FIELDS: tuple[tuple[str, str, SeriesType], ...] = (
    ("energy", "kcal", SeriesType.dietary_energy_consumed),
    ("energyFromFat", "kcal", SeriesType.dietary_energy_from_fat),
    ("totalCarbohydrate", "grams", SeriesType.dietary_carbohydrates),
    ("totalFat", "grams", SeriesType.dietary_fat_total),
)

# NutrientQuantity.nutrient enum -> series. Google reports every nutrient in grams.
NUTRIENT_FIELDS: dict[str, SeriesType] = {
    "BIOTIN": SeriesType.dietary_biotin,
    "CAFFEINE": SeriesType.dietary_caffeine,
    "CALCIUM": SeriesType.dietary_calcium,
    "CARBOHYDRATES": SeriesType.dietary_carbohydrates,
    "CHLORIDE": SeriesType.dietary_chloride,
    "CHOLESTEROL": SeriesType.dietary_cholesterol,
    "CHROMIUM": SeriesType.dietary_chromium,
    "COPPER": SeriesType.dietary_copper,
    "DIETARY_FIBER": SeriesType.dietary_fiber,
    "FOLATE": SeriesType.dietary_folate,
    "FOLIC_ACID": SeriesType.dietary_folic_acid,
    "IODINE": SeriesType.dietary_iodine,
    "IRON": SeriesType.dietary_iron,
    "MAGNESIUM": SeriesType.dietary_magnesium,
    "MANGANESE": SeriesType.dietary_manganese,
    "MOLYBDENUM": SeriesType.dietary_molybdenum,
    "MONOUNSATURATED_FAT": SeriesType.dietary_fat_monounsaturated,
    "NIACIN": SeriesType.dietary_niacin,
    "PANTOTHENIC_ACID": SeriesType.dietary_pantothenic_acid,
    "PHOSPHORUS": SeriesType.dietary_phosphorus,
    "POLYUNSATURATED_FAT": SeriesType.dietary_fat_polyunsaturated,
    "POTASSIUM": SeriesType.dietary_potassium,
    "PROTEIN": SeriesType.dietary_protein,
    "RIBOFLAVIN": SeriesType.dietary_riboflavin,
    "SATURATED_FAT": SeriesType.dietary_fat_saturated,
    "SELENIUM": SeriesType.dietary_selenium,
    "SODIUM": SeriesType.dietary_sodium,
    "SUGAR": SeriesType.dietary_sugar,
    "THIAMIN": SeriesType.dietary_thiamin,
    "TRANS_FAT": SeriesType.dietary_fat_trans,
    "UNSATURATED_FAT": SeriesType.dietary_fat_unsaturated,
    "VITAMIN_A": SeriesType.dietary_vitamin_a,
    "VITAMIN_B12": SeriesType.dietary_vitamin_b12,
    "VITAMIN_B6": SeriesType.dietary_vitamin_b6,
    "VITAMIN_C": SeriesType.dietary_vitamin_c,
    "VITAMIN_D": SeriesType.dietary_vitamin_d,
    "VITAMIN_E": SeriesType.dietary_vitamin_e,
    "VITAMIN_K": SeriesType.dietary_vitamin_k,
    "ZINC": SeriesType.dietary_zinc,
}

_GRAMS_TO_UNIT: dict[str, Decimal] = {"g": Decimal(1), "mg": Decimal(1_000), "mcg": Decimal(1_000_000)}


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
        """Fetch nutrition-log entries starting in the window and upsert them as meals.

        Flushes only - the caller's savepoint and commit own the transaction. Returns the number of new meals.
        """
        meals = [
            self._meal_bundle(user_id, meal)
            for point in self._fetch(db, user_id, start_time, end_time)
            if (meal := self._parse_point(point, start_time, end_time)) is not None
        ]
        return event_record_service.upsert_meals(db, meals) if meals else 0

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
        """Read every nutrient Google returned for one item, scaled to the series unit."""
        values: dict[SeriesType, Decimal] = {}
        for fld, subfield, series_type in NUTRITION_PRIMARY_FIELDS:
            value = read_number(nutrition, fld, subfield=subfield)
            if value is not None:
                values[series_type] = value

        for entry in nutrition.get("nutrients") or []:
            if not isinstance(entry, dict) or (series_type := NUTRIENT_FIELDS.get(entry.get("nutrient") or "")) is None:
                continue
            scale = _GRAMS_TO_UNIT[get_series_type_unit(series_type)]
            value = read_number(entry, "quantity", subfield="grams", scale=scale)
            if value is not None:
                values.setdefault(series_type, value)
        return values

    def _meal_bundle(self, user_id: UUID, meal: "_Meal") -> tuple[EventRecordCreate, MealDetailCreate]:
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
        detail = MealDetailCreate(
            record_id=record.id,
            title=meal.title,
            meal_type=meal.meal_type,
            nutrients={series_type: float(value) for series_type, value in meal.nutrients.items()},
        )
        return record, detail
