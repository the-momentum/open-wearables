"""Service for daily summaries (sleep, activity, recovery, body)."""

from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import EventRecord
from app.repositories import EventRecordRepository
from app.schemas.common_types import DataSource, PaginatedResponse, Pagination, TimeseriesMetadata
from app.schemas.summaries import SleepSummary
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_cursor


class SummariesService:
    """Service for aggregating daily health summaries."""

    def __init__(self, log: Logger):
        self.logger = log
        self.event_record_repo = EventRecordRepository(EventRecord)

    @handle_exceptions
    async def get_sleep_summaries(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        cursor: str | None,
        limit: int,
    ) -> PaginatedResponse[SleepSummary]:
        """Get daily sleep summaries aggregated by date, provider, and device."""
        self.logger.debug(f"Fetching sleep summaries for user {user_id} from {start_date} to {end_date}")

        # Get aggregated data from repository
        results = self.event_record_repo.get_sleep_summaries(db_session, user_id, start_date, end_date, cursor, limit)

        # Check if there's more data
        has_more = len(results) > limit
        if has_more:
            results = results[:limit]

        # Generate cursors
        next_cursor: str | None = None
        previous_cursor: str | None = None

        if results:
            # Use the last result for next cursor
            last_date, _, _, _, _, _, last_id = results[-1]
            last_date_midnight = datetime.combine(last_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            if has_more:
                next_cursor = encode_cursor(last_date_midnight, last_id, "next")

            # Previous cursor if we had a cursor (not first page)
            if cursor:
                first_date, _, _, _, _, _, first_id = results[0]
                first_date_midnight = datetime.combine(first_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                previous_cursor = encode_cursor(first_date_midnight, first_id, "prev")

        # Transform to schema
        data = []
        for sleep_date, min_start_time, max_end_time, total_duration, provider_name, device_id, _ in results:
            summary = SleepSummary(
                date=sleep_date,
                source=DataSource(provider=provider_name, device=device_id),
                start_time=min_start_time,
                end_time=max_end_time,
                duration_seconds=total_duration,
            )
            data.append(summary)

        return PaginatedResponse(
            data=data,
            pagination=Pagination(
                has_more=has_more,
                next_cursor=next_cursor,
                previous_cursor=previous_cursor,
            ),
            metadata=TimeseriesMetadata(
                sample_count=len(data),
                start_time=start_date,
                end_time=end_date,
            ),
        )


summaries_service = SummariesService(log=getLogger(__name__))
