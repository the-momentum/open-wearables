from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.schemas.enums import get_series_type_from_id
from app.schemas.enums.series_types import SERIES_TYPE_ENUM_BY_ID
from app.schemas.responses.dashboard import ProviderDataCount, UserDataSummaryResponse
from app.schemas.responses.upload import (
    CountWithGrowth,
    DataPointsInfo,
    SeriesTypeMetric,
    SystemInfoResponse,
    WorkoutTypeMetric,
)
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

    def _calculate_weekly_growth(self, current: int, previous: int) -> float:
        """Calculate weekly growth percentage."""
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return ((current - previous) / previous) * 100.0

    def _get_growth_stats(
        self,
        db_session: DbSession,
        total_count_func: Callable[[DbSession], int],
        range_count_func: Callable[[DbSession, datetime, datetime], int],
        week_ago: datetime,
        two_weeks_ago: datetime,
        now: datetime,
    ) -> CountWithGrowth:
        """Calculate stats with growth based on current and previous week."""
        total = total_count_func(db_session)
        this_week = range_count_func(db_session, week_ago, now)
        last_week = range_count_func(db_session, two_weeks_ago, week_ago)
        growth = self._calculate_weekly_growth(this_week, last_week)
        return CountWithGrowth(count=total, weekly_growth=growth)

    def get_system_info(self, db_session: DbSession, top_limit: int = 6) -> SystemInfoResponse:
        """Get system dashboard information."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        # Users
        users_stats = self._get_growth_stats(
            db_session,
            self.user_service.crud.get_total_count,
            self.user_service.get_count_in_range,
            week_ago,
            two_weeks_ago,
            now,
        )

        # Active Connections
        active_conn_stats = self._get_growth_stats(
            db_session,
            self.user_connection_service.crud.get_active_count,
            self.user_connection_service.get_active_count_in_range,
            week_ago,
            two_weeks_ago,
            now,
        )

        # Data Points
        data_points_stats = self._get_growth_stats(
            db_session,
            self.timeseries_service.crud.get_total_count,
            self.timeseries_service.get_count_in_range,
            week_ago,
            two_weeks_ago,
            now,
        )

        # Get metrics by series type
        series_type_counts = self.timeseries_service.get_count_by_series_type(db_session)
        top_series_types = [
            SeriesTypeMetric(
                series_type=get_series_type_from_id(series_type_id).value,
                count=count,
            )
            for series_type_id, count in series_type_counts
            if series_type_id in SERIES_TYPE_ENUM_BY_ID
        ][:top_limit]

        # Get metrics by workout type
        workout_type_counts = self.event_record_service.get_count_by_workout_type(db_session)
        top_workout_types = [
            WorkoutTypeMetric(
                workout_type=workout_type or "Unknown",
                count=count,
            )
            for workout_type, count in workout_type_counts[:top_limit]
        ]

        return SystemInfoResponse(
            total_users=users_stats,
            active_conn=active_conn_stats,
            data_points=DataPointsInfo(
                count=data_points_stats.count,
                weekly_growth=data_points_stats.weekly_growth,
                top_series_types=top_series_types,
                top_workout_types=top_workout_types,
            ),
        )

    def get_user_data_summary(self, db_session: DbSession, user_id: UUID) -> UserDataSummaryResponse:
        """Get per-user data summary with counts by type and provider."""
        # Query time-series counts grouped by provider + series type
        series_rows = self.timeseries_service.crud.get_user_counts_by_provider_and_type(db_session, user_id)

        # Query event counts grouped by provider + category + type
        event_rows = self.event_record_service.crud.get_user_event_counts_by_provider(db_session, user_id)

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

        for provider, category, event_type, count in event_rows:
            if category == "workout":
                provider_workouts[provider] += count
                workout_type_totals[event_type or "unknown"] += count
            elif category == "sleep":
                provider_sleep[provider] += count

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
        )


system_info_service = SystemInfoService(
    log=getLogger(__name__),
    user_service=user_service,
    user_connection_service=user_connection_service,
    timeseries_service=timeseries_service,
    event_record_service=event_record_service,
)
