from logging import Logger

from app.database import DbSession
from app.models import HeartRateRecovery
from app.repositories import HeartRateRecoveryRepository
from app.schemas import (
    AEHeartRateQueryParams,
    AEHeartRateRecoveryCreate,
    AEHeartRateRecoveryUpdate
)
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class HeartRateRecoveryService(AppService[HeartRateRecoveryRepository, HeartRateRecovery, AEHeartRateRecoveryCreate, AEHeartRateRecoveryUpdate]):
    """Service for heart rate recovery business logic."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=HeartRateRecoveryRepository,
            model=HeartRateRecovery,
            log=log,
            **kwargs
        )

    @handle_exceptions
    async def get_heart_rate_recovery_with_filters(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> tuple[list[HeartRateRecovery], int]:
        """
        Get heart rate recovery data with filtering, sorting, and pagination.
        """
        self.logger.debug(f"Fetching heart rate recovery data with filters: {query_params.model_dump()}")
        
        data, total_count = self.crud.get_heart_rate_recovery_with_filters(
            db_session, query_params, user_id
        )
        
        self.logger.debug(f"Retrieved {len(data)} heart rate recovery records out of {total_count} total")
        
        return data, total_count

    @handle_exceptions
    async def get_heart_rate_summary(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> dict:
        """
        Get summary statistics for heart rate data.
        """
        self.logger.debug(f"Generating heart rate summary with filters: {query_params.model_dump()}")
        
        summary = self.crud.get_heart_rate_summary(db_session, query_params, user_id)
        
        self.logger.debug(f"Generated heart rate summary with {summary['total_records']} total records")
        
        return summary
