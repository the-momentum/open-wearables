from datetime import datetime
from logging import Logger, getLogger

from app.database import DbSession
from app.models import Record
from app.repositories import HKRecordRepository
from app.schemas import (
    HKRecordQueryParams,
    HKRecordCreate,
    HKRecordUpdate,
    HKRecordListResponse,
    HKRecordResponse,
    HKRecordMeta,
    HKMetadataEntryResponse,
    HKDateRange,
)
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class RecordService(AppService[HKRecordRepository, Record, HKRecordCreate, HKRecordUpdate]):
    """Service for HealthKit record-related business logic."""

    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=HKRecordRepository,
            model=Record,
            log=log,
            **kwargs
        )

    @handle_exceptions
    async def _get_records_with_filters(
        self, 
        db_session: DbSession, 
        query_params: HKRecordQueryParams,
        user_id: str
    ) -> tuple[list[Record], int]:
        """
        Get records with filtering, sorting, and pagination.
        Includes business logic and logging.
        """
        self.logger.debug(f"Fetching HealthKit records with filters: {query_params.model_dump()}")
        
        records, total_count = self.crud.get_records_with_filters(
            db_session, query_params, user_id
        )
        
        self.logger.debug(f"Retrieved {len(records)} HealthKit records out of {total_count} total")
        
        return records, total_count

    @handle_exceptions
    async def get_records_response(
        self,
        db_session: DbSession,
        query_params: HKRecordQueryParams,
        user_id: str
    ) -> HKRecordListResponse:
        """
        Get HealthKit records formatted as API response.
        
        Returns:
            HKRecordListResponse ready for API
        """
        records, total_count = await self._get_records_with_filters(db_session, query_params, user_id)
        
        record_responses = []
        for record in records:
            # Convert metadata entries to response format
            metadata_responses = []
            if record.metadataEntries:
                for metadata_entry in record.metadataEntries:
                    metadata_response = HKMetadataEntryResponse(
                        id=str(metadata_entry.id),
                        key=metadata_entry.key,
                        value=metadata_entry.value,
                    )
                    metadata_responses.append(metadata_response)
            
            record_response = HKRecordResponse(
                id=record.id,
                type=record.type,
                sourceName=record.sourceName,
                startDate=record.startDate,
                endDate=record.endDate,
                unit=record.unit,
                value=record.value,
                user_id=str(record.user_id),
                recordMetadata=metadata_responses,
            )
            record_responses.append(record_response)

        start_date_str = query_params.start_date or "1900-01-01T00:00:00Z"
        end_date_str = query_params.end_date or datetime.now().isoformat() + "Z"
        
        start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        duration_days = (end_date - start_date).days
        
        meta = HKRecordMeta(
            requested_at=datetime.now().isoformat() + "Z",
            filters=query_params.model_dump(exclude_none=True),
            result_count=len(record_responses),
            total_count=total_count,
            date_range=HKDateRange(
                start=start_date_str,
                end=end_date_str,
                duration_days=duration_days,
            ),
        )

        return HKRecordListResponse(
            data=record_responses,
            meta=meta,
        )


record_service = RecordService(log=getLogger(__name__))
