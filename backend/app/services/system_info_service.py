from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger

from app.database import DbSession
from app.schemas.system_info import CountWithGrowth, DataPointsInfo, SystemInfoResponse
from app.services.time_series_service import TimeSeriesService, time_series_service
from app.services.user_connection_service import UserConnectionService, user_connection_service
from app.services.user_service import UserService, user_service


class SystemInfoService:
    """Service for system dashboard information."""

    def __init__(
        self,
        log: Logger,
        user_service: UserService,
        user_connection_service: UserConnectionService,
        time_series_service: TimeSeriesService,
    ):
        self.logger = log
        self.user_service = user_service
        self.user_connection_service = user_connection_service
        self.time_series_service = time_series_service

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

    def get_system_info(self, db_session: DbSession) -> SystemInfoResponse:
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
            self.time_series_service.crud.get_total_count,
            self.time_series_service.get_count_in_range,
            week_ago,
            two_weeks_ago,
            now,
        )

        return SystemInfoResponse(
            total_users=users_stats,
            active_conn=active_conn_stats,
            data_points=DataPointsInfo(
                count=data_points_stats.count,
                weekly_growth=data_points_stats.weekly_growth,
            ),
        )


system_info_service = SystemInfoService(
    log=getLogger(__name__),
    user_service=user_service,
    user_connection_service=user_connection_service,
    time_series_service=time_series_service,
)
