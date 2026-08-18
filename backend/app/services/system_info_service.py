from collections import defaultdict
from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.schemas.responses.dashboard import ProviderDataCount, UserDataSummaryResponse
from app.schemas.responses.upload import (
    DataPointsInfo,
    EventRecordsInfo,
    MetricCount,
    SystemInfoResponse,
)
from app.services.dashboard_stats_cache import get_total_data_points
from app.services.event_record_service import EventRecordService, event_record_service
from app.services.timeseries_service import TimeSeriesService, timeseries_service
from app.services.user_connection_service import UserConnectionService, user_connection_service
from app.services.user_service import UserService, user_service


class SystemInfoService:
    """Service for system dashboard information."""

    def __init__(
        self,
        log: Logger,
        user_service: UserService,
        user_connection_service: UserConnectionService,
        timeseries_service: TimeSeriesService,
        event_record_service: EventRecordService,
    ):
        self.logger = log
        self.user_service = user_service
        self.user_connection_service = user_connection_service
        self.timeseries_service = timeseries_service
        self.event_record_service = event_record_service

    def get_system_info(self, db_session: DbSession) -> SystemInfoResponse:
        """Get system dashboard information.

        The total data-point count is served from cache (approximate on a cold cache) to avoid a
        multi-second full scan on every dashboard load; the remaining figures are cheap counts on
        small tables.
        """
        category_counts = dict(self.event_record_service.get_category_counts(db_session))
        event_records = EventRecordsInfo(
            count=sum(category_counts.values()),
            workouts=category_counts.get("workout", 0),
            sleep=category_counts.get("sleep", 0),
            menstrual_cycles=category_counts.get("menstrual_cycle", 0),
        )

        return SystemInfoResponse(
            total_users=MetricCount(count=self.user_service.crud.get_total_count(db_session)),
            active_conn=MetricCount(count=self.user_connection_service.crud.get_active_count(db_session)),
            data_points=DataPointsInfo(
                count=get_total_data_points(db_session),
                archived=self.timeseries_service.get_approximate_archived_count(db_session),
            ),
            event_records=event_records,
            connections_coverage=self.user_connection_service.get_connections_coverage(db_session),
        )

    def get_user_data_summary(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> UserDataSummaryResponse:
        """Get per-user data summary with counts by type and provider.

        When ``start_datetime`` and/or ``end_datetime`` are provided, counts are scoped to that
        window (data points by ``recorded_at``, events by ``start_datetime``). Omitting both
        returns all-time counts. The per-provider breakdown is derived from the scoped rows.
        """
        # Query time-series counts grouped by provider + series type
        series_rows = self.timeseries_service.crud.get_user_counts_by_provider_and_type(
            db_session, user_id, start_datetime, end_datetime
        )

        # Query event counts grouped by provider + category + type
        event_rows = self.event_record_service.crud.get_user_event_counts_by_provider(
            db_session, user_id, start_datetime, end_datetime
        )

        # Aggregate into per-provider and overall totals
        provider_series: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        provider_workouts: dict[str, int] = defaultdict(int)
        provider_sleep: dict[str, int] = defaultdict(int)
        provider_data_points: dict[str, int] = defaultdict(int)
        series_type_totals: dict[str, int] = defaultdict(int)
        workout_type_totals: dict[str, int] = defaultdict(int)

        for provider, code, count in series_rows:
            provider_series[provider][code] += count
            provider_data_points[provider] += count
            series_type_totals[code] += count

        has_womens_health_data = False
        for provider, category, event_type, count in event_rows:
            if category == "workout":
                provider_workouts[provider] += count
                workout_type_totals[event_type or "unknown"] += count
            elif category == "sleep":
                provider_sleep[provider] += count
            elif category == "menstrual_cycle" and count > 0:
                has_womens_health_data = True

        # Build per-provider breakdown
        all_providers = set(provider_series) | set(provider_workouts) | set(provider_sleep)
        by_provider = sorted(
            [
                ProviderDataCount(
                    provider=p,
                    data_points=provider_data_points.get(p, 0),
                    series_counts=dict(provider_series.get(p, {})),
                    workout_count=provider_workouts.get(p, 0),
                    sleep_count=provider_sleep.get(p, 0),
                )
                for p in all_providers
            ],
            key=lambda x: x.data_points + x.workout_count + x.sleep_count,
            reverse=True,
        )

        return UserDataSummaryResponse(
            user_id=str(user_id),
            total_data_points=sum(provider_data_points.values()),
            total_workouts=sum(provider_workouts.values()),
            total_sleep_events=sum(provider_sleep.values()),
            series_type_counts=dict(sorted(series_type_totals.items(), key=lambda x: x[1], reverse=True)),
            workout_type_counts=dict(sorted(workout_type_totals.items(), key=lambda x: x[1], reverse=True)),
            by_provider=by_provider,
            has_womens_health_data=has_womens_health_data,
        )


system_info_service = SystemInfoService(
    log=getLogger(__name__),
    user_service=user_service,
    user_connection_service=user_connection_service,
    timeseries_service=timeseries_service,
    event_record_service=event_record_service,
)
