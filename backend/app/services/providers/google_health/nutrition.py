"""Google Health API nutrition handler.

Fetches ``nutrition-log`` sessions via the dataPoints ``list`` operation and stores them
as ``EventRecord(category="meal")`` + ``MealDetails``, with every present nutrient
written as a ``DataPointSeries`` sample linked back via ``event_record_id`` - the same
model the SDK/HealthKit meal-correlation import path already uses (see
``app/services/sdk/import_service.py``). Composed into GoogleHealth247Data.load_and_save_all.

Google emits one DataPoint per *food item* (``foodDisplayName``), and food loggers give
every item of a meal the same interval and meal type. Items sharing a source, start time and
meal type are folded into one meal here - titles joined, nutrients summed - because both ``EventRecord``
(unique on data source + interval) and ``DataPointSeries`` (unique on data source +
series + time) can hold only one row per such key; stored one-by-one, later items would
silently overwrite earlier ones.

Google wraps every nutrient value in a typed quantity object (``{"kcal": ...}`` for
energy, ``{"grams": ...}`` for everything else - including sodium/potassium/cholesterol,
which the unified series stores in mg). Only the fields Google actually returns are
mapped; most micronutrients (calcium, iron, vitamins, ...) aren't exposed by this API and
are simply absent from the payload - see the nutrition-fields matrix in the repo root for
the full cross-provider comparison.
"""

import logging
from dataclasses import dataclass, field
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

# MealDetails.title is str_255; a longer joined title would fail the whole meal on every sync.
_TITLE_MAX_LEN = 255
_TITLE_SEPARATOR = ", "

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
class MealGroup:
    """Every nutrition-log item that shares a data source and start time, folded into one meal."""

    source_name: str
    device_model: str | None
    start: datetime
    end: datetime
    zone_offset: str | None
    external_id: str | None
    titles: list[str] = field(default_factory=list)
    meal_type: str | None = None
    nutrients: dict[SeriesType, Decimal] = field(default_factory=dict)

    @property
    def title(self) -> str | None:
        return _TITLE_SEPARATOR.join(self.titles)[:_TITLE_MAX_LEN] or None


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
        """Fetch nutrition-log entries starting in the window and store them as meals.

        Never commits or rolls back the session: the 24/7 sync runs this inside its own
        ``begin_nested()`` savepoint, and a commit in here would close that context and fail
        every statement after it. Each meal gets a savepoint of its own instead, so one bad
        meal is discarded without touching the others; the caller commits the batch.

        Returns the number of meals newly inserted; meals that already existed (re-sync)
        have their end, title, type and nutrient values refreshed but are not counted.
        """
        count = 0
        for group in self._group_entries(self._fetch(db, user_id, start_time, end_time), start_time, end_time):
            try:
                with db.begin_nested():
                    inserted = self._save_meal(db, user_id, group)
            except Exception as e:
                log_and_capture_error(
                    e,
                    self.logger,
                    f"Google nutrition sync failed for a meal: {e}",
                    extra={"user_id": str(user_id), "provider": self.provider_name, "external_id": group.external_id},
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

    def _group_entries(self, points: list[dict[str, Any]], start_time: datetime, end_time: datetime) -> list[MealGroup]:
        """Keep entries starting in the window and fold same-source, same-start, same-type items into one meal."""
        groups: dict[tuple[str | None, datetime, str | None], MealGroup] = {}
        # Sorted by resource name so which item lends the meal its external_id/offset is stable across syncs.
        for point in sorted(points, key=lambda p: str(p.get("name") or "")):
            nutrition = point.get("nutritionLog")
            if not isinstance(nutrition, dict):
                continue
            interval = nutrition.get("interval") or {}
            start, end = parse_interval(interval)
            if start is None or end is None or not (start_time <= start < end_time):
                continue
            source_name, device_model = extract_source(point.get("dataSource"))
            meal_type = (nutrition.get("mealType") or "").lower() or None

            key = (device_model, start, meal_type)
            group = groups.get(key)
            if group is None:
                group = MealGroup(
                    source_name=source_name,
                    device_model=device_model,
                    start=start,
                    end=end,
                    zone_offset=zone_offset_from(interval.get("startUtcOffset")),
                    external_id=point.get("name"),
                    meal_type=meal_type,
                )
                groups[key] = group

            group.end = max(group.end, end)
            title = nutrition.get("foodDisplayName")
            if title and title not in group.titles:
                group.titles.append(title)
            for series_type, value in self._nutrients(nutrition).items():
                group.nutrients[series_type] = group.nutrients.get(series_type, Decimal(0)) + value
        return list(groups.values())

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

    def _save_meal(self, db: DbSession, user_id: UUID, group: MealGroup) -> bool:
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
            source_name=group.source_name,
            device_model=group.device_model,
            external_id=group.external_id,
            start_datetime=group.start,
            end_datetime=group.end,
            duration_seconds=int((group.end - group.start).total_seconds()),
            zone_offset=group.zone_offset,
            user_id=user_id,
        )
        detail = MealDetailCreate(record_id=record.id, title=group.title, meal_type=group.meal_type)
        saved, inserted = event_record_service.create_or_update_meal(db, record, detail, nutrients=group.nutrients)

        if not inserted:
            # A nutrient the provider stopped reporting must not linger from the previous sync.
            timeseries_service.crud.delete_stale_for_event_record(db, saved.id, group.nutrients.keys())
        samples = self._build_samples(user_id, saved.id, group)
        if samples:
            timeseries_service.bulk_create_samples(db, samples)
        return inserted

    def _build_samples(self, user_id: UUID, meal_id: UUID, group: MealGroup) -> list[TimeSeriesSampleCreate]:
        return [
            TimeSeriesSampleCreate(
                id=uuid4(),
                user_id=user_id,
                provider=self.provider_name,
                source=GOOGLE_HEALTH_API_SOURCE,
                device_model=group.device_model,
                recorded_at=group.start,
                zone_offset=group.zone_offset,
                value=value,
                series_type=series_type,
                is_daily_total=daily_total_flag(series_type, is_daily=False),
                event_record_id=meal_id,
            )
            for series_type, value in group.nutrients.items()
        ]
