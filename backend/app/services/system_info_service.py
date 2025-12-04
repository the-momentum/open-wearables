from logging import Logger, getLogger

from app.database import DbSession
from app.repositories.system_info_repository import SystemInfoRepository
from app.schemas.system_info import CountWithGrowth, DataPointsInfo, SystemInfoResponse


class SystemInfoService:
    """Service for system dashboard information."""

    def __init__(self, log: Logger):
        self.repository = SystemInfoRepository()
        self.logger = log

    def _calculate_weekly_growth(self, current: int, previous: int) -> float:
        """Calculate weekly growth percentage."""
        if previous == 0:
            return 0.0 if current == 0 else 100.0
        return ((current - previous) / previous) * 100.0

    def get_system_info(self, db_session: DbSession) -> SystemInfoResponse:
        """Get system dashboard information."""
        # Get total users data
        total_users_current = self.repository.get_total_users_count(db_session)
        total_users_week_ago = self.repository.get_total_users_count_week_ago(db_session)
        total_users_growth = self._calculate_weekly_growth(total_users_current, total_users_week_ago)

        # Get active connections data
        active_conn_current = self.repository.get_active_connections_count(db_session)
        active_conn_week_ago = self.repository.get_active_connections_count_week_ago(db_session)
        active_conn_growth = self._calculate_weekly_growth(active_conn_current, active_conn_week_ago)

        # Mock data points for now
        # TODO: Replace with actual data points query when ready
        data_points_histogram = [100, 120, 95, 110, 130, 115, 125]  # Mock: 7 days of data
        data_points_count = sum(data_points_histogram)
        data_points_week_ago_count = 700  # Mock previous week total
        data_points_growth = self._calculate_weekly_growth(data_points_count, data_points_week_ago_count)

        return SystemInfoResponse(
            total_users=CountWithGrowth(count=total_users_current, weekly_growth=total_users_growth),
            active_conn=CountWithGrowth(count=active_conn_current, weekly_growth=active_conn_growth),
            data_points=DataPointsInfo(
                weekly_histogram=data_points_histogram,
                count=data_points_count,
                weekly_growth=data_points_growth,
            ),
        )


system_info_service = SystemInfoService(log=getLogger(__name__))

