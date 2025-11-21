from sqlalchemy import func  # noqa: I001

from app.database import DbSession
from app.models import HeartRateData, HeartRateRecovery
from app.repositories.apple.auto_export.base_heart_rate_repository import BaseHeartRateRepository
from app.repositories.apple.auto_export.heart_rate_data_repository import HeartRateDataRepository
from app.repositories.repositories import CrudRepository
from app.schemas import AEHeartRateQueryParams
from app.schemas import AEHeartRateRecoveryCreate, AEHeartRateRecoveryUpdate


class HeartRateRecoveryRepository(
    CrudRepository[HeartRateRecovery, AEHeartRateRecoveryCreate, AEHeartRateRecoveryUpdate],
    BaseHeartRateRepository[HeartRateRecovery],
):
    """Repository for heart rate recovery database operations."""

    def __init__(self, model: type[HeartRateRecovery]):
        CrudRepository.__init__(self, model)
        BaseHeartRateRepository.__init__(self, model)

    def get_heart_rate_recovery_with_filters(
        self,
        db_session: DbSession,
        query_params: AEHeartRateQueryParams,
        user_id: str,
    ) -> tuple[list[HeartRateRecovery], int]:
        """
        Get heart rate recovery data with filtering, sorting, and pagination.

        Returns:
            Tuple of (heart_rate_recovery_data, total_count)
        """
        return self.get_heart_rate_with_filters(db_session, query_params, user_id)

    def get_heart_rate_summary(self, db_session: DbSession, query_params: AEHeartRateQueryParams, user_id: str) -> dict:
        """
        Get summary statistics for heart rate data.
        """
        # Create temporary repositories for filtering
        hr_data_repo = HeartRateDataRepository(HeartRateData)

        # Apply common filters to both queries
        hr_query = db_session.query(HeartRateData)
        hr_recovery_query = db_session.query(HeartRateRecovery)

        # Use base class filtering logic
        hr_query = hr_data_repo._apply_common_filters(hr_query, query_params, user_id)
        hr_recovery_query = self._apply_common_filters(hr_recovery_query, query_params, user_id)

        # Get heart rate statistics
        hr_stats = hr_query.with_entities(
            func.count(HeartRateData.id).label("total_records"),
            func.avg(HeartRateData.avg).label("avg_hr"),
            func.max(HeartRateData.max).label("max_hr"),
            func.min(HeartRateData.min).label("min_hr"),
        ).first()

        # Get heart rate recovery statistics
        hr_recovery_stats = hr_recovery_query.with_entities(
            func.avg(HeartRateRecovery.avg).label("avg_recovery"),
            func.max(HeartRateRecovery.max).label("max_recovery"),
            func.min(HeartRateRecovery.min).label("min_recovery"),
        ).first()

        # Extract recovery stats with safe defaults
        if hr_recovery_stats:
            avg_recovery = float(hr_recovery_stats.avg_recovery)
            max_recovery = float(hr_recovery_stats.max_recovery)
            min_recovery = float(hr_recovery_stats.min_recovery)
        else:
            avg_recovery = 0
            max_recovery = 0
            min_recovery = 0

        if hr_stats:
            total_records = int(hr_stats.total_records)
            avg_hr = float(hr_stats.avg_hr)
            max_hr = float(hr_stats.max_hr)
            min_hr = float(hr_stats.min_hr)
        else:
            total_records = 0
            avg_hr = 0
            max_hr = 0
            min_hr = 0

        return {
            "total_records": total_records,
            "avg_heart_rate": avg_hr,
            "max_heart_rate": max_hr,
            "min_heart_rate": min_hr,
            "avg_recovery_rate": avg_recovery,
            "max_recovery_rate": max_recovery,
            "min_recovery_rate": min_recovery,
        }
