"""Google Health API 24/7 daily-rollup handler.

A single endpoint — ``dataPoints:dailyRollUp`` — serves every daily-summary metric,
parameterised by data type. Each metric is declared once in ``rollup/`` and this
class just drives the generic fetch → map → persist loop. Sleep and workouts come
from the sessions endpoint and are handled separately.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any, NoReturn
from uuid import UUID, uuid4

from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.google.health_api.extract import parse_rfc3339
from app.services.providers.google.health_api.listed import LIST_METRICS, ListMetric
from app.services.providers.google.health_api.rollup import ROLLUP_METRICS, RollupMetric, physical_interval
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured


class GoogleHealth247Data(Base247DataTemplate):
    """Fetches Google daily-rollup metrics and persists them as DataPointSeries."""

    # Health API data plane (health.googleapis.com). dataPoints:rollUp's parent is
    # users/{user}/dataTypes/{dataType}. We roll up over physical time with daily
    # windows. The API enforces windowSize * pageSize <= the data type's max range,
    # so with 1-day windows pageSize must be <= max_range_days (set per metric).
    BASE_URL = "https://health.googleapis.com"
    ROLLUP_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:rollUp"
    WINDOW_SIZE = "86400s"  # Duration: 1-day aggregation windows
    # list operation for data types that don't support rollUp (Daily summaries etc.).
    LIST_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints"
    LIST_PAGE_SIZE = 1000

    def __init__(self, oauth: BaseOAuthTemplate, connection_repo: UserConnectionRepository):
        super().__init__(provider_name="google", api_base_url=self.BASE_URL, oauth=oauth)
        self.connection_repo = connection_repo

    # -- orchestration ---------------------------------------------------------

    def load_and_save_all(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
        is_first_sync: bool = False,
    ) -> dict[str, WriteCounts]:
        """Fetch + persist every registered metric (rollUp + list); failures are isolated per metric."""
        results: dict[str, WriteCounts] = {}

        for rollup_metric in ROLLUP_METRICS:
            try:
                points = self._fetch_rollup(db, user_id, rollup_metric, start_time, end_time)
                samples = self._build_samples(rollup_metric, points, user_id)
            except Exception as e:
                self._log_metric_failure(rollup_metric.data_type, user_id, e)
                continue
            if samples:
                results[rollup_metric.data_type] = timeseries_service.bulk_create_samples(db, samples)

        for list_metric in LIST_METRICS:
            try:
                points = self._fetch_list(db, user_id, list_metric.data_type)
                samples = self._build_list_samples(list_metric, points, user_id, start_time, end_time)
            except Exception as e:
                self._log_metric_failure(list_metric.data_type, user_id, e)
                continue
            if samples:
                results[list_metric.data_type] = timeseries_service.bulk_create_samples(db, samples)

        if results:
            db.commit()
        log_structured(
            self.logger,
            "info",
            "Google 24/7 sync complete",
            provider=self.provider_name,
            task="load_and_save_all",
            user_id=str(user_id),
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

    def _fetch_rollup(
        self,
        db: DbSession,
        user_id: UUID,
        metric: RollupMetric,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """POST to dataPoints:rollUp for one metric, chunking the range to its max."""
        endpoint = self.ROLLUP_ENDPOINT.format(data_type=metric.data_type)
        points: list[dict[str, Any]] = []
        # With 1-day windows, max_range_days daily windows fit the limit exactly.
        page_size = metric.max_range_days
        for chunk_start, chunk_end in self._chunk_range(start_time, end_time, metric.max_range_days):
            points.extend(self._fetch_window(db, user_id, endpoint, chunk_start, chunk_end, page_size))
        return points

    def _fetch_window(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        start_time: datetime,
        end_time: datetime,
        page_size: int,
    ) -> list[dict[str, Any]]:
        """Fetch one within-limit range, following pageToken to exhaustion."""
        points: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            body: dict[str, Any] = {
                "range": physical_interval(start_time, end_time),
                "windowSize": self.WINDOW_SIZE,
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

    def _build_samples(
        self,
        metric: RollupMetric,
        points: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        """Turn RollupDataPoints into one daily-total sample each."""
        samples: list[TimeSeriesSampleCreate] = []
        for point in points:
            value_obj = point.get(metric.value_key)
            recorded_at = parse_rfc3339(point.get("startTime"))
            if not isinstance(value_obj, dict) or recorded_at is None:
                continue
            value = metric.extract(value_obj)
            if value is None:
                continue
            samples.append(self._sample(user_id, recorded_at, value, metric.series_type, is_daily_total=True))
        return samples

    # -- list operation (data types without rollUp support) --------------------

    def _fetch_list(self, db: DbSession, user_id: UUID, data_type: str) -> list[dict[str, Any]]:
        """GET dataPoints for one list-only data type, following pageToken."""
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

    def _build_list_samples(
        self,
        metric: ListMetric,
        points: list[dict[str, Any]],
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[TimeSeriesSampleCreate]:
        """Turn list data points into samples, filtering to the sync window.

        list has no range parameter, so we filter client-side on the point's startTime.
        """
        samples: list[TimeSeriesSampleCreate] = []
        for point in points:
            recorded_at = parse_rfc3339(point.get("startTime") or point.get("endTime"))
            if recorded_at is None or not (start_time <= recorded_at < end_time):
                continue
            value = metric.extract(point)
            if value is None:
                continue
            samples.append(
                self._sample(user_id, recorded_at, value, metric.series_type, is_daily_total=metric.is_daily_total)
            )
        return samples

    def _sample(
        self,
        user_id: UUID,
        recorded_at: datetime,
        value: Any,
        series_type: Any,
        *,
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
    # Google's rollup model doesn't use the sleep/recovery/activity-sample split;
    # the sync orchestrator calls load_and_save_all() instead.

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
