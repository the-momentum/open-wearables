"""Google Health API 24/7 handler.

Drives both Google fetch operations from one registry: ``dataPoints:rollUp`` (windowed
aggregates) and ``dataPoints`` list (raw points). The operation + window per data type
follow the provider's configured granularity (DAILY/HOURLY/RAW), defaulting to DAILY.
Sleep and workouts come from the sessions endpoint and are handled separately.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any, NoReturn
from uuid import UUID, uuid4

from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import DataGranularity, SeriesType
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.schemas.providers.google import DataTypeMetric, TimeShape
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.google.health_api.extract import parse_date, parse_rfc3339, physical_interval, read_number
from app.services.providers.google.health_api.metrics import METRICS
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

# windowSize (seconds) per aggregating granularity. RAW uses the list op instead.
_WINDOW_SECONDS: dict[DataGranularity, int] = {
    DataGranularity.DAILY: 86_400,
    DataGranularity.HOURLY: 3_600,
}
_DEFAULT_GRANULARITY = DataGranularity.DAILY
_DAY_SECONDS = 86_400


class GoogleHealth247Data(Base247DataTemplate):
    """Fetches Google 24/7 metrics (rollUp + list) and persists them as DataPointSeries."""

    BASE_URL = "https://health.googleapis.com"
    ROLLUP_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:rollUp"
    LIST_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints"
    # rollUp enforces windowSize * pageSize <= the data type's max range; list default page.
    MAX_PAGE_SIZE = 10_000
    LIST_PAGE_SIZE = 1_000

    def __init__(self, oauth: BaseOAuthTemplate, connection_repo: UserConnectionRepository):
        super().__init__(provider_name="google", api_base_url=self.BASE_URL, oauth=oauth)
        self.connection_repo = connection_repo
        self.settings_repo = ProviderSettingsRepository()

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
        granularity = self.settings_repo.get_data_granularity(db, self.provider_name) or _DEFAULT_GRANULARITY
        results: dict[str, WriteCounts] = {}

        for metric in METRICS:
            try:
                if metric.use_list(granularity):
                    samples = self._list_samples(db, user_id, metric, start_time, end_time)
                else:
                    samples = self._rollup_samples(db, user_id, metric, start_time, end_time, granularity)
            except Exception as e:
                self._log_metric_failure(metric.data_type, user_id, e)
                continue
            if samples:
                results[metric.data_type] = timeseries_service.bulk_create_samples(db, samples)

        if results:
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
        )
        return results

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
        window_seconds = _WINDOW_SECONDS.get(granularity, _WINDOW_SECONDS[DataGranularity.HOURLY])
        windows_per_day = _DAY_SECONDS // window_seconds
        page_size = min(spec.max_range_days * windows_per_day, self.MAX_PAGE_SIZE)
        is_daily_total = window_seconds == _DAY_SECONDS

        endpoint = self.ROLLUP_ENDPOINT.format(data_type=metric.data_type)
        samples: list[TimeSeriesSampleCreate] = []
        for chunk_start, chunk_end in self._chunk_range(start_time, end_time, spec.max_range_days):
            for point in self._fetch_rollup_window(
                db, user_id, endpoint, chunk_start, chunk_end, window_seconds, page_size
            ):
                value_obj = point.get(spec.value_key)
                recorded_at = parse_rfc3339(point.get("startTime"))
                if not isinstance(value_obj, dict) or recorded_at is None:
                    continue
                value = read_number(value_obj, spec.field, spec.subfield, spec.scale)
                if value is not None:
                    samples.append(self._sample(user_id, recorded_at, value, metric.series_type, is_daily_total))
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

    # -- list operation --------------------------------------------------------

    def _list_samples(
        self,
        db: DbSession,
        user_id: UUID,
        metric: DataTypeMetric,
        start_time: datetime,
        end_time: datetime,
    ) -> list[TimeSeriesSampleCreate]:
        """List raw data points and map those within the sync window to samples.

        list has no range parameter, so we filter client-side on each point's startTime.
        """
        spec = metric.list_spec
        if spec is None:
            return []
        samples: list[TimeSeriesSampleCreate] = []
        for point in self._fetch_list(db, user_id, metric.data_type):
            recorded_at = self._point_time(point, spec.time)
            if recorded_at is None or not (start_time <= recorded_at < end_time):
                continue
            value = read_number(point, spec.field, spec.subfield, spec.scale)
            if value is not None:
                samples.append(self._sample(user_id, recorded_at, value, metric.series_type, spec.is_daily_total))
        return samples

    @staticmethod
    def _point_time(point: dict[str, Any], shape: TimeShape) -> datetime | None:
        """Resolve a list data point's timestamp from its declared record shape."""
        match shape:
            case TimeShape.INTERVAL:
                interval = point.get("interval") or {}
                return parse_rfc3339(interval.get("startTime") or interval.get("endTime"))
            case TimeShape.SAMPLE:
                return parse_rfc3339((point.get("sampleTime") or {}).get("physicalTime"))
            case TimeShape.DATE:
                return parse_date(point.get("date"))

    def _fetch_list(self, db: DbSession, user_id: UUID, data_type: str) -> list[dict[str, Any]]:
        """GET dataPoints for one list data type, following pageToken."""
        endpoint = self.LIST_ENDPOINT.format(data_type=data_type)
        points: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": self.LIST_PAGE_SIZE}
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
    ) -> TimeSeriesSampleCreate:
        return TimeSeriesSampleCreate(
            id=uuid4(),
            user_id=user_id,
            source=self.provider_name,
            provider=self.provider_name,
            recorded_at=recorded_at,
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
