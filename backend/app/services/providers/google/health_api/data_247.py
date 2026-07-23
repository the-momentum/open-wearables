"""Google Health API 24/7 handler.

Drives Google's fetch operations from one registry. Granularity (default RAW) picks the
tier: DAILY/HOURLY use ``dataPoints:rollUp`` (windowed aggregates); RAW uses a
native-resolution operation chosen by ``google_use_reconcile`` — ``dataPoints:reconcile``
(one merged, deduplicated stream across sources, matching the native health app) or
``dataPoints`` list (raw per-source points with device attribution). Sleep and workouts
come from the sessions endpoint and are handled separately.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, NoReturn
from uuid import UUID, uuid4

from app.config import settings
from app.constants.google_health_endpoints import LIST_ENDPOINT, RECONCILE_ENDPOINT, ROLLUP_ENDPOINT
from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import GRANULARITY_WINDOW_SECONDS, DataGranularity, SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.schemas.providers.google import DataTypeMetric, ListSpec, RollupSpec, TimeShape
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.google.health_api.helpers import (
    GOOGLE_HEALTH_API_SOURCE,
    extract_source,
    parse_date,
    parse_rfc3339,
    physical_interval,
    read_number,
    zone_offset_from,
)
from app.services.providers.google.health_api.metrics import METRICS
from app.services.providers.google.health_api.sleep import GoogleHealthApiSleep
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.raw_payload_storage import store_raw_payload
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured


class GoogleHealth247Data(Base247DataTemplate):
    """Fetches Google 24/7 metrics (rollUp + list) and persists them as DataPointSeries."""

    # rollUp enforces windowSize * pageSize <= the data type's max range; list default page.
    MAX_PAGE_SIZE = 10_000
    LIST_PAGE_SIZE = 1_000

    def __init__(self, oauth: BaseOAuthTemplate, connection_repo: UserConnectionRepository, api_base_url: str):
        super().__init__(provider_name="google", api_base_url=api_base_url, oauth=oauth)
        self.connection_repo = connection_repo
        self.settings_repo = ProviderSettingsRepository()
        self.sleep = GoogleHealthApiSleep(oauth, connection_repo, api_base_url)

    # -- orchestration ---------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
        is_first_sync: bool = False,
    ) -> dict[str, WriteCounts]:
        """Fetch + persist every registered metric; failures are isolated per metric."""
        granularity = (
            self.settings_repo.get_data_granularity(db, self.provider_name) or settings.default_data_granularity
        )
        results: dict[str, WriteCounts] = {}

        for metric in METRICS:
            # Confine each metric (fetch + write) to a savepoint so a failed write rolls
            # back only that metric and leaves the transaction usable for the rest.
            try:
                with db.begin_nested():
                    if metric.use_list(granularity):
                        samples = self._native_samples(db, user_id, metric, start_time, end_time)
                    else:
                        samples = self._rollup_samples(db, user_id, metric, start_time, end_time, granularity)
                    counts = timeseries_service.bulk_create_samples(db, samples) if samples else None
            except Exception as e:
                self._log_metric_failure(metric.data_type, user_id, e)
                continue
            if counts is not None:
                results[metric.data_type] = counts

        try:
            sleep_count = self.sleep.load_and_save(db, user_id, start_time, end_time)
        except Exception as e:
            self._log_metric_failure("sleep", user_id, e)
            sleep_count = 0

        if results or sleep_count:
            db.commit()
        log_structured(
            self.logger,
            "info",
            "Google 24/7 sync complete",
            provider=self.provider_name,
            task="load_and_save_all",
            user_id=str(user_id),
            granularity=granularity.value,
            metrics_synced=len(results),
            sleep_sessions=sleep_count,
        )
        return results

    def sync_data_type(
        self,
        db: DbSession,
        user_id: UUID,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> WriteCounts | None:
        """Fetch + persist a single 24/7 metric over an explicit window (webhook-triggered).

        Returns None when ``data_type`` is not a registered metric. Sleep and exercise
        are owned by their own handlers and are routed there by the webhook handler
        before ever reaching here, so an unrecognised type is a safe no-op.
        """
        metric = next((m for m in METRICS if m.data_type == data_type), None)
        if metric is None:
            return None
        granularity = (
            self.settings_repo.get_data_granularity(db, self.provider_name) or settings.default_data_granularity
        )
        if metric.use_list(granularity):
            samples = self._native_samples(db, user_id, metric, start_time, end_time)
        else:
            samples = self._rollup_samples(db, user_id, metric, start_time, end_time, granularity)
        if not samples:
            return None
        counts = timeseries_service.bulk_create_samples(db, samples)
        db.commit()
        return counts

    def _log_metric_failure(self, data_type: str, user_id: UUID, error: Exception) -> None:
        log_and_capture_error(
            error,
            self.logger,
            f"Google 24/7 sync failed for data type {data_type}: {error}",
            extra={"user_id": str(user_id), "provider": self.provider_name, "data_type": data_type},
        )

    # -- rollUp operation ------------------------------------------------------

    def _rollup_samples(
        self,
        db: DbSession,
        user_id: UUID,
        metric: DataTypeMetric,
        start_time: datetime,
        end_time: datetime,
        granularity: DataGranularity,
    ) -> list[TimeSeriesSampleCreate]:
        """Roll up one metric at the granularity's window and map to samples."""
        spec = metric.rollup_spec
        if spec is None:
            return []
        # RAW falls back to the finest aggregate (hourly) for rollUp-only data types.
        window_seconds = GRANULARITY_WINDOW_SECONDS.get(granularity, GRANULARITY_WINDOW_SECONDS[DataGranularity.HOURLY])
        windows_per_day = GRANULARITY_WINDOW_SECONDS[DataGranularity.DAILY] // window_seconds
        page_size = min(spec.max_range_days * windows_per_day, self.MAX_PAGE_SIZE)
        is_daily_total = granularity == DataGranularity.DAILY

        endpoint = ROLLUP_ENDPOINT.format(data_type=metric.data_type)
        samples: list[TimeSeriesSampleCreate] = []
        for chunk_start, chunk_end in self._chunk_range(start_time, end_time, spec.max_range_days):
            for point in self._fetch_rollup_window(
                db, user_id, endpoint, chunk_start, chunk_end, window_seconds, page_size
            ):
                value_obj = point.get(metric.value_key)
                recorded_at = parse_rfc3339(point.get("startTime"))
                if not isinstance(value_obj, dict) or recorded_at is None:
                    continue
                for series_type, field, subfield, scale in self._bindings(metric.series_type, spec):
                    value = read_number(value_obj, field, subfield, scale)
                    if value is not None:
                        samples.append(self._sample(user_id, recorded_at, value, series_type, is_daily_total))
        return samples

    def _fetch_rollup_window(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        start_time: datetime,
        end_time: datetime,
        window_seconds: int,
        page_size: int,
    ) -> list[dict[str, Any]]:
        """Fetch one within-limit range, following pageToken to exhaustion."""
        points: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            body: dict[str, Any] = {
                "range": physical_interval(start_time, end_time),
                "windowSize": f"{window_seconds}s",
                "pageSize": page_size,
            }
            if page_token:
                body["pageToken"] = page_token
            response = make_authenticated_request(
                db=db,
                user_id=user_id,
                connection_repo=self.connection_repo,
                oauth=self.oauth,
                api_base_url=self.api_base_url,
                provider_name=self.provider_name,
                endpoint=endpoint,
                method="POST",
                json_data=body,
            )
            store_raw_payload(
                source="api_response",
                provider=self.provider_name,
                payload=response,
                user_id=str(user_id),
                trace_id=endpoint,
            )
            if not isinstance(response, dict):
                break
            points.extend(response.get("rollupDataPoints", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return points

    @staticmethod
    def _chunk_range(start: datetime, end: datetime, max_days: int) -> Iterator[tuple[datetime, datetime]]:
        """Split [start, end) into consecutive windows no longer than max_days."""
        window = timedelta(days=max_days)
        cursor = start
        while cursor < end:
            nxt = min(cursor + window, end)
            yield cursor, nxt
            cursor = nxt

    # -- native-resolution operation (reconcile / list) ------------------------

    def _native_samples(
        self,
        db: DbSession,
        user_id: UUID,
        metric: DataTypeMetric,
        start_time: datetime,
        end_time: datetime,
    ) -> list[TimeSeriesSampleCreate]:
        """Fetch native-resolution points and map those within the sync window to samples.

        Picks the operation per ``google_use_reconcile``: reconcile returns one merged,
        deduplicated stream across all sources (no dataSource, so no device attribution);
        list returns raw per-source points that carry a dataSource we attribute a device from.
        Both share the union-key payload shape and timestamp shapes; the fetch is bounded to
        the window server-side via the AIP-160 filter, and the client-side check below is the
        precise gate.
        """
        spec = metric.list_spec
        if spec is None:
            return []
        reconcile = settings.google_use_reconcile
        template = RECONCILE_ENDPOINT if reconcile else LIST_ENDPOINT
        endpoint = template.format(data_type=metric.data_type)
        time_filter = self._time_filter(metric.data_type, spec.time, start_time, end_time)

        samples: list[TimeSeriesSampleCreate] = []
        for point in self._fetch_points(db, user_id, endpoint, time_filter):
            # Both operations nest the payload under the type's union key.
            value_obj = point.get(metric.value_key)
            if not isinstance(value_obj, dict):
                continue
            recorded_at, zone_offset = self._point_time(value_obj, spec.time)
            if recorded_at is None or not (start_time <= recorded_at < end_time):
                continue
            # Only list points carry a dataSource; reconciled points are already merged.
            device_model = None if reconcile else extract_source(point.get("dataSource"))[1]
            for series_type, field, subfield, scale in self._bindings(metric.series_type, spec):
                value = read_number(value_obj, field, subfield, scale)
                if value is not None:
                    samples.append(
                        self._sample(
                            user_id, recorded_at, value, series_type, spec.is_daily_total, zone_offset, device_model
                        )
                    )
        return samples

    @staticmethod
    def _bindings(
        primary: SeriesType,
        spec: RollupSpec | ListSpec,
    ) -> Iterator[tuple[SeriesType, str, str | None, Decimal]]:
        """Yield (series, field, subfield, scale) for the spec's primary + extra series."""
        yield primary, spec.field, spec.subfield, spec.scale
        for sf in spec.extra or ():
            yield sf.series_type, sf.field, sf.subfield, sf.scale

    @staticmethod
    def _point_time(point: dict[str, Any], shape: TimeShape) -> tuple[datetime | None, str | None]:
        """Resolve a list data point's (timestamp, zone_offset) from its declared record shape."""
        match shape:
            case TimeShape.INTERVAL:
                interval = point.get("interval") or {}
                recorded_at = parse_rfc3339(interval.get("startTime") or interval.get("endTime"))
                return recorded_at, zone_offset_from(interval.get("startUtcOffset"))
            case TimeShape.SAMPLE:
                sample_time = point.get("sampleTime") or {}
                return parse_rfc3339(sample_time.get("physicalTime")), zone_offset_from(sample_time.get("utcOffset"))
            case TimeShape.DATE:
                return parse_date(point.get("date")), None

    @staticmethod
    def _time_filter(data_type: str, shape: TimeShape, start_time: datetime, end_time: datetime) -> str:
        """AIP-160 filter bounding the fetch to [start_time, end_time) for the type's time shape."""
        field = data_type.replace("-", "_")
        if shape == TimeShape.DATE:
            member = f"{field}.date"
            low = start_time.date().isoformat()
            high = (end_time.date() + timedelta(days=1)).isoformat()
        else:
            suffix = "interval.start_time" if shape == TimeShape.INTERVAL else "sample_time.physical_time"
            member = f"{field}.{suffix}"
            window = physical_interval(start_time, end_time)
            low, high = window["startTime"], window["endTime"]
        return f'{member} >= "{low}" AND {member} < "{high}"'

    def _fetch_points(
        self, db: DbSession, user_id: UUID, endpoint: str, time_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """GET a native-resolution endpoint (list or reconcile), following pageToken.

        Both return their points under ``dataPoints`` and paginate identically.
        """
        points: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": self.LIST_PAGE_SIZE}
            if time_filter:
                params["filter"] = time_filter
            if page_token:
                params["pageToken"] = page_token
            response = make_authenticated_request(
                db=db,
                user_id=user_id,
                connection_repo=self.connection_repo,
                oauth=self.oauth,
                api_base_url=self.api_base_url,
                provider_name=self.provider_name,
                endpoint=endpoint,
                method="GET",
                params=params,
            )
            store_raw_payload(
                source="api_response",
                provider=self.provider_name,
                payload=response,
                user_id=str(user_id),
                trace_id=endpoint,
            )
            if not isinstance(response, dict):
                break
            points.extend(response.get("dataPoints", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return points

    def _sample(
        self,
        user_id: UUID,
        recorded_at: datetime,
        value: Any,
        series_type: SeriesType,
        is_daily_total: bool,
        zone_offset: str | None = None,
        device_model: str | None = None,
    ) -> TimeSeriesSampleCreate:
        return TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user_id,
            source=GOOGLE_HEALTH_API_SOURCE,
            provider=self.provider_name,
            device_model=device_model,
            recorded_at=recorded_at,
            zone_offset=zone_offset,
            value=value,
            series_type=series_type,
            is_daily_total=is_daily_total,
        )

    # -- unused Base247DataTemplate hooks --------------------------------------
    # Google uses load_and_save_all(); the sleep/recovery/activity-sample split is unused.

    def _unsupported(self, feature: str) -> NoReturn:
        raise NotImplementedError(f"Google Health API 24/7 uses load_and_save_all(); {feature} is not used")

    def get_sleep_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict]:
        self._unsupported("get_sleep_data")

    def normalize_sleep(self, raw_sleep: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_sleep")

    def get_recovery_data(self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime) -> list[dict]:
        self._unsupported("get_recovery_data")

    def normalize_recovery(self, raw_recovery: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_recovery")

    def get_activity_samples(
        self, db: DbSession, user_id: UUID, start_time: datetime, end_time: datetime
    ) -> list[dict]:
        self._unsupported("get_activity_samples")

    def normalize_activity_samples(
        self, raw_samples: list[dict[str, Any]], user_id: UUID
    ) -> dict[str, list[dict[str, Any]]]:
        self._unsupported("normalize_activity_samples")

    def get_daily_activity_statistics(
        self, db: DbSession, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> list[dict]:
        self._unsupported("get_daily_activity_statistics")

    def normalize_daily_activity(self, raw_stats: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        self._unsupported("normalize_daily_activity")
