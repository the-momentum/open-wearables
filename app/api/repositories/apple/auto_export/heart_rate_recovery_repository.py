from sqlalchemy import func

from app.database import DbSession
from app.models import HeartRateData, HeartRateRecovery
from app.repositories.apple.auto_export.base_heart_rate_repository import BaseHeartRateRepository
from app.repositories.apple.auto_export.heart_rate_data_repository import HeartRateDataRepository
from app.repositories.repositories import CrudRepository
from app.schemas import AEHeartRateQueryParams
from app.schemas import (
    AEHeartRateRecoveryCreate,
    AEHeartRateRecoveryUpdate
)


class HeartRateRecoveryRepository(CrudRepository[HeartRateRecovery, AEHeartRateRecoveryCreate, AEHeartRateRecoveryUpdate], BaseHeartRateRepository[HeartRateRecovery]):
    """Repository for heart rate recovery database operations."""

    def __init__(self, model: type[HeartRateRecovery]):
        CrudRepository.__init__(self, model)
        BaseHeartRateRepository.__init__(self, model)

    def get_heart_rate_recovery_with_filters(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> tuple[list[HeartRateRecovery], int]:
        """
        Get heart rate recovery data with filtering, sorting, and pagination.

        Returns:
            Tuple of (heart_rate_recovery_data, total_count)
        """
        return self.get_heart_rate_with_filters(db_session, query_params, user_id)

    def get_heart_rate_summary(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> dict:
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

        return {
            "total_records": hr_stats.total_records or 0,
            "avg_heart_rate": float(hr_stats.avg_hr or 0),
            "max_heart_rate": float(hr_stats.max_hr or 0),
            "min_heart_rate": float(hr_stats.min_hr or 0),
            "avg_recovery_rate": float(hr_recovery_stats.avg_recovery or 0),
            "max_recovery_rate": float(hr_recovery_stats.max_recovery or 0),
            "min_recovery_rate": float(hr_recovery_stats.min_recovery or 0),
        }
