from logging import Logger, getLogger

from datetime import datetime

from app.database import DbSession
from app.models import HeartRateData, HeartRateRecovery
from app.schemas import (
    AEHeartRateDataResponse,
    AEHeartRateListResponse,
    AEMeta,
    AEHeartRateQueryParams,
    AEHeartRateRecoveryResponse,
    AESummary,
    AEHeartRateValue,
)
from .mixins.heart_rate_data_service import HeartRateDataService
from .mixins.heart_rate_recovery_service import HeartRateRecoveryService
from app.utils.exceptions import handle_exceptions


class HeartRateService:
    """
    Combined service for heart rate operations.
    Provides access to both heart rate data and recovery operations.
    """

    def __init__(
        self, 
        log: Logger,
        **kwargs
    ):
        self.logger = log
        self.heart_rate_data_service = HeartRateDataService(log=log, **kwargs)
        self.heart_rate_recovery_service = HeartRateRecoveryService(log=log, **kwargs)

    @handle_exceptions
    async def _get_complete_heart_rate_data(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> tuple[list[HeartRateData], list[HeartRateRecovery], dict, int, int]:
        """
        Get complete heart rate data including both data and recovery records with summary.
        
        Returns:
            Tuple of (heart_rate_data, heart_rate_recovery, summary, hr_total_count, recovery_total_count)
        """
        self.logger.debug(f"Fetching complete heart rate data with filters: {query_params.model_dump()}")
        
        # Use methods from composed services
        hr_data, hr_total_count = await self.heart_rate_data_service.get_heart_rate_data_with_filters(db_session, query_params, user_id)
        recovery_data, recovery_total_count = await self.heart_rate_recovery_service.get_heart_rate_recovery_with_filters(db_session, query_params, user_id)
        summary = await self.heart_rate_recovery_service.get_heart_rate_summary(db_session, query_params, user_id)
        
        self.logger.debug(f"Retrieved complete heart rate data: {hr_total_count} HR records, {recovery_total_count} recovery records")
        
        return hr_data, recovery_data, summary, hr_total_count, recovery_total_count

    @handle_exceptions
    async def build_heart_rate_full_data_response(
        self, 
        db_session: DbSession, 
        query_params: AEHeartRateQueryParams,
        user_id: str
    ) -> AEHeartRateListResponse:
        """
        Get complete heart rate data formatted as API response.
        
        Returns:
            HeartRateListResponse ready for API
        """
        # Get raw data
        hr_data, recovery_data, summary_data, hr_total_count, recovery_total_count = await self._get_complete_heart_rate_data(db_session, query_params, user_id)
        
        # Convert heart rate data to response format
        heart_rate_responses = []
        for hr_data_item in hr_data:
            heart_rate_response = AEHeartRateDataResponse(
                id=hr_data_item.id,
                workout_id=hr_data_item.workout_id,
                date=hr_data_item.date.isoformat(),
                source=hr_data_item.source,
                units=hr_data_item.units,
                avg=(
                    AEHeartRateValue(
                        value=float(hr_data_item.avg or 0),
                        unit=hr_data_item.units or "bpm",
                    )
                    if hr_data_item.avg
                    else None
                ),
                min=(
                    AEHeartRateValue(
                        value=float(hr_data_item.min or 0),
                        unit=hr_data_item.units or "bpm",
                    )
                    if hr_data_item.min
                    else None
                ),
                max=(
                    AEHeartRateValue(
                        value=float(hr_data_item.max or 0),
                        unit=hr_data_item.units or "bpm",
                    )
                    if hr_data_item.max
                    else None
                ),
            )
            heart_rate_responses.append(heart_rate_response)

        # Convert heart rate recovery data to response format
        heart_rate_recovery_responses = []
        for hr_recovery_item in recovery_data:
            heart_rate_recovery_response = AEHeartRateRecoveryResponse(
                id=hr_recovery_item.id,
                workout_id=hr_recovery_item.workout_id,
                date=hr_recovery_item.date.isoformat(),
                source=hr_recovery_item.source,
                units=hr_recovery_item.units,
                avg=(
                    AEHeartRateValue(
                        value=float(hr_recovery_item.avg or 0),
                        unit=hr_recovery_item.units or "bpm",
                    )
                    if hr_recovery_item.avg
                    else None
                ),
                min=(
                    AEHeartRateValue(
                        value=float(hr_recovery_item.min or 0),
                        unit=hr_recovery_item.units or "bpm",
                    )
                    if hr_recovery_item.min
                    else None
                ),
                max=(
                    AEHeartRateValue(
                        value=float(hr_recovery_item.max or 0),
                        unit=hr_recovery_item.units or "bpm",
                    )
                    if hr_recovery_item.max
                    else None
                ),
            )
            heart_rate_recovery_responses.append(heart_rate_recovery_response)

        # Build summary
        summary = AESummary(**summary_data)

        # Build metadata
        meta = AEMeta(
            requested_at=datetime.now().isoformat() + "Z",
            filters=query_params.model_dump(exclude_none=True),
            result_count=hr_total_count + recovery_total_count,
            date_range={
                "start": query_params.start_date or "1900-01-01T00:00:00Z",
                "end": query_params.end_date or datetime.now().isoformat() + "Z",
            },
        )

        return AEHeartRateListResponse(
            data=heart_rate_responses,
            recovery_data=heart_rate_recovery_responses,
            summary=summary,
            meta=meta,
        )


heart_rate_service = HeartRateService(log=getLogger(__name__))