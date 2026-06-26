"""Google Health API 24/7 daily-rollup handler.

A single endpoint — ``dataPoints:dailyRollUp`` — serves every daily-summary metric,
parameterised by data type. Each metric is declared once in ``rollup/`` and this
class just drives the generic fetch → map → persist loop. Sleep and workouts come
from the sessions endpoint and are handled separately.
"""

from datetime import datetime
from typing import Any, NoReturn
from uuid import UUID, uuid4

from app.database import DbSession
from app.repositories.data_point_series_repository import WriteCounts
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.model_crud.activities import TimeSeriesSampleCreate
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.google.health_api.rollup import (
    ROLLUP_METRICS,
    RollupMetric,
    civil_time_interval,
    parse_civil_datetime,
)
from app.services.providers.templates.base_247_data import Base247DataTemplate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.timeseries_service import timeseries_service
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

GOOGLE_HEALTH_API_BASE_URL = "https://health.googleapis.com"
_ROLLUP_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"
_PAGE_SIZE = 1000


class GoogleHealth247Data(Base247DataTemplate):
    """Fetches Google daily-rollup metrics and persists them as DataPointSeries."""

    def __init__(self, oauth: BaseOAuthTemplate, connection_repo: UserConnectionRepository):
        super().__init__(provider_name="google", api_base_url=GOOGLE_HEALTH_API_BASE_URL, oauth=oauth)
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
        """Fetch + persist every registered rollup metric; one metric's failure is isolated."""
        results: dict[str, WriteCounts] = {}
        for metric in ROLLUP_METRICS:
            try:
                points = self._fetch_rollup(db, user_id, metric.data_type, start_time, end_time)
                samples = self._build_samples(metric, points, user_id)
                if samples:
                    results[metric.data_type] = timeseries_service.bulk_create_samples(db, samples)
            except Exception as e:
                log_and_capture_error(
                    e,
                    self.logger,
                    f"Google rollup sync failed for data type {metric.data_type}: {e}",
                    extra={"user_id": str(user_id), "provider": self.provider_name, "data_type": metric.data_type},
                )
        if results:
            db.commit()
        log_structured(
            self.logger,
            "info",
            "Google rollup sync complete",
            provider=self.provider_name,
            task="load_and_save_all",
            user_id=str(user_id),
            metrics_synced=len(results),
        )
        return results

    def _fetch_rollup(
        self,
        db: DbSession,
        user_id: UUID,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """POST to dataPoints:dailyRollUp for one data type, following pageToken."""
        endpoint = _ROLLUP_ENDPOINT.format(data_type=data_type)
        points: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            body: dict[str, Any] = {
                "range": civil_time_interval(start_time, end_time),
                "windowSizeDays": 1,
                "pageSize": _PAGE_SIZE,
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

    def _build_samples(
        self,
        metric: RollupMetric,
        points: list[dict[str, Any]],
        user_id: UUID,
    ) -> list[TimeSeriesSampleCreate]:
        """Turn DailyRollupDataPoints into one daily-total sample each."""
        samples: list[TimeSeriesSampleCreate] = []
        for point in points:
            value_obj = point.get(metric.value_key)
            recorded_at = parse_civil_datetime(point.get("civilStartTime"))
            if not isinstance(value_obj, dict) or recorded_at is None:
                continue
            value = metric.extract(value_obj)
            if value is None:
                continue
            samples.append(
                TimeSeriesSampleCreate(
                    id=uuid4(),
                    user_id=user_id,
                    source=self.provider_name,
                    provider=self.provider_name,
                    recorded_at=recorded_at,
                    value=value,
                    series_type=metric.series_type,
                    is_daily_total=True,
                )
            )
        return samples

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
