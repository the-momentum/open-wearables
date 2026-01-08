"""Service for daily summaries (sleep, activity, recovery, body)."""

from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import DataPointSeries, EventRecord
from app.repositories import EventRecordRepository
from app.repositories.data_point_series_repository import DataPointSeriesRepository
from app.schemas.common_types import DataSource, PaginatedResponse, Pagination, TimeseriesMetadata
from app.schemas.series_types import SeriesType
from app.schemas.summaries import SleepStagesSummary, SleepSummary
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_cursor

# Series types needed for sleep physiological metrics
# TODO: Add HRV, respiratory rate, and SpO2 when ready
SLEEP_PHYSIO_SERIES_TYPES = [
    SeriesType.heart_rate,
]


class SummariesService:
    """Service for aggregating daily health summaries."""

    def __init__(self, log: Logger):
        self.logger = log
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.data_point_repo = DataPointSeriesRepository(DataPointSeries)

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

        # Get aggregated data from repository (now returns list of dicts)
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
            last_result = results[-1]
            last_date = last_result["sleep_date"]
            last_id = last_result["record_id"]
            last_date_midnight = datetime.combine(last_date, datetime.min.time()).replace(tzinfo=timezone.utc)
            if has_more:
                next_cursor = encode_cursor(last_date_midnight, last_id, "next")

            # Previous cursor if we had a cursor (not first page)
            if cursor:
                first_result = results[0]
                first_date = first_result["sleep_date"]
                first_id = first_result["record_id"]
                first_date_midnight = datetime.combine(first_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                previous_cursor = encode_cursor(first_date_midnight, first_id, "prev")

        # Transform to schema
        data = []
        for result in results:
            # Build sleep stages if any stage data is available
            stages = None
            has_stage_data = any(
                result.get(key) is not None for key in ["deep_minutes", "light_minutes", "rem_minutes", "awake_minutes"]
            )
            if has_stage_data:
                stages = SleepStagesSummary(
                    deep_minutes=result.get("deep_minutes"),
                    light_minutes=result.get("light_minutes"),
                    rem_minutes=result.get("rem_minutes"),
                    awake_minutes=result.get("awake_minutes"),
                )

            # Fetch average heart rate during the sleep period
            # TODO: Add HRV, respiratory rate, and SpO2 when ready
            avg_hr: int | None = None

            sleep_start = result.get("min_start_time")
            sleep_end = result.get("max_end_time")
            if sleep_start and sleep_end:
                try:
                    physio_averages = self.data_point_repo.get_averages_for_time_range(
                        db_session,
                        user_id,
                        sleep_start,
                        sleep_end,
                        SLEEP_PHYSIO_SERIES_TYPES,
                    )
                    hr_avg = physio_averages.get(SeriesType.heart_rate)
                    avg_hr = int(round(hr_avg)) if hr_avg is not None else None
                except Exception as e:
                    self.logger.warning(f"Failed to fetch heart rate metrics for sleep: {e}")

            summary = SleepSummary(
                date=result["sleep_date"],
                source=DataSource(provider=result["provider_name"], device=result.get("device_id")),
                start_time=result["min_start_time"],
                end_time=result["max_end_time"],
                duration_minutes=result["total_duration_minutes"],
                time_in_bed_minutes=result.get("time_in_bed_minutes"),
                efficiency_percent=result.get("efficiency_percent"),
                stages=stages,
                nap_count=result.get("nap_count"),
                nap_duration_minutes=result.get("nap_duration_minutes"),
                avg_heart_rate_bpm=avg_hr,
                # TODO: Implement these when ready
                avg_hrv_rmssd_ms=None,
                avg_respiratory_rate=None,
                avg_spo2_percent=None,
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
