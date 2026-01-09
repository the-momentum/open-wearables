"""Service for daily summaries (sleep, activity, recovery, body)."""

from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import DataPointSeries, EventRecord, User
from app.repositories import EventRecordRepository
from app.repositories.data_point_series_repository import (
    ActiveMinutesResult,
    DataPointSeriesRepository,
    IntensityMinutesResult,
)
from app.repositories.user_repository import UserRepository
from app.schemas.common_types import DataSource, PaginatedResponse, Pagination, TimeseriesMetadata
from app.schemas.series_types import SeriesType
from app.schemas.summaries import ActivitySummary, HeartRateStats, IntensityMinutes, SleepStagesSummary, SleepSummary
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import encode_cursor

# Series types needed for sleep physiological metrics
# TODO: Add HRV, respiratory rate, and SpO2 when ready
SLEEP_PHYSIO_SERIES_TYPES = [
    SeriesType.heart_rate,
]

# Activity summary constants
DEFAULT_MAX_HR = 190  # Assumes ~30 years old when birth_date unavailable
ACTIVE_STEPS_THRESHOLD = 30  # Steps per minute to be considered "active"
METERS_PER_FLOOR = 3.0  # Standard floor height for floors_climbed calculation

# HR zone percentages (as fraction of max HR)
HR_ZONE_LIGHT = (0.50, 0.63)  # 50-63% of max HR
HR_ZONE_MODERATE = (0.64, 0.76)  # 64-76% of max HR
HR_ZONE_VIGOROUS = (0.77, 0.93)  # 77-93% of max HR


class SummariesService:
    """Service for aggregating daily health summaries."""

    def __init__(self, log: Logger):
        self.logger = log
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.data_point_repo = DataPointSeriesRepository(DataPointSeries)
        self.user_repo = UserRepository(User)

    def _get_user_max_hr(self, db_session: DbSession, user_id: UUID, reference_date: datetime) -> int:
        """Calculate user's max HR based on age.

        Uses formula: max_hr = 220 - age
        Falls back to DEFAULT_MAX_HR if birth_date is not available.
        """
        user = self.user_repo.get(db_session, user_id)
        if not user or not user.personal_record or not user.personal_record.birth_date:
            return DEFAULT_MAX_HR

        # Calculate age as of the reference date
        birth_date = user.personal_record.birth_date
        age = reference_date.year - birth_date.year
        # Adjust if birthday hasn't occurred yet this year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1

        max_hr = 220 - age
        return max(max_hr, 100)  # Ensure reasonable minimum

    def _get_hr_zone_thresholds(self, max_hr: int) -> dict[str, int]:
        """Calculate HR zone thresholds as percentages of max HR.

        Returns dict with keys: light_min, light_max, moderate_max, vigorous_max
        """
        return {
            "light_min": int(max_hr * HR_ZONE_LIGHT[0]),
            "light_max": int(max_hr * HR_ZONE_LIGHT[1]),
            "moderate_max": int(max_hr * HR_ZONE_MODERATE[1]),
            "vigorous_max": int(max_hr * HR_ZONE_VIGOROUS[1]),
        }

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

    @handle_exceptions
    async def get_activity_summaries(
        self,
        db_session: DbSession,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime,
        cursor: str | None,
        limit: int,
    ) -> PaginatedResponse[ActivitySummary]:
        """Get daily activity summaries aggregated by date, provider, and device.

        Aggregates include:
        - Steps (sum from time-series)
        - Distance (sum from time-series)
        - Calories (active + basal from time-series)
        - Elevation (from workouts total_elevation_gain)
        - Floors (from flights_climbed time-series OR elevation)
        - Heart rate stats (avg, max, min)
        - Active/sedentary minutes (based on step threshold)
        - Intensity minutes (HR zones using max HR = 220 - age):
          light 50-63%, moderate 64-76%, vigorous 77-93%
        """
        self.logger.debug(f"Fetching activity summaries for user {user_id} from {start_date} to {end_date}")

        # Get aggregated data from time-series repository
        results = self.data_point_repo.get_daily_activity_aggregates(db_session, user_id, start_date, end_date)

        # Get workout aggregates (elevation, distance, energy from workouts)
        workout_aggregates = self.event_record_repo.get_daily_workout_aggregates(
            db_session, user_id, start_date, end_date
        )

        # Build lookup dict for workout data by (date, provider, device)
        workout_lookup: dict[tuple, dict] = {}
        for wa in workout_aggregates:
            key = (wa["workout_date"], wa["provider_name"], wa.get("device_id"))
            workout_lookup[key] = wa

        # Get active/sedentary minutes from step data
        activity_minutes = self.data_point_repo.get_daily_active_minutes(
            db_session, user_id, start_date, end_date, active_threshold=ACTIVE_STEPS_THRESHOLD
        )

        # Build lookup for activity minutes
        activity_lookup: dict[tuple, ActiveMinutesResult] = {}
        for am in activity_minutes:
            key = (am["activity_date"], am["provider_name"], am.get("device_id"))
            activity_lookup[key] = am

        # Get intensity minutes from HR data
        # Calculate HR zone thresholds based on user's max HR (220 - age)
        max_hr = self._get_user_max_hr(db_session, user_id, start_date)
        hr_zones = self._get_hr_zone_thresholds(max_hr)
        intensity_minutes_data = self.data_point_repo.get_daily_intensity_minutes(
            db_session,
            user_id,
            start_date,
            end_date,
            light_min=hr_zones["light_min"],
            light_max=hr_zones["light_max"],
            moderate_max=hr_zones["moderate_max"],
            vigorous_max=hr_zones["vigorous_max"],
        )

        # Build lookup for intensity minutes
        intensity_lookup: dict[tuple, IntensityMinutesResult] = {}
        for im in intensity_minutes_data:
            key = (im["activity_date"], im["provider_name"], im.get("device_id"))
            intensity_lookup[key] = im

        # Apply pagination (simple offset-based for now, cursor-based can be added later)
        # TODO: Implement proper cursor pagination like sleep summaries
        has_more = len(results) > limit
        if has_more:
            results = results[:limit]

        # Generate cursors (simplified for now)
        next_cursor: str | None = None
        previous_cursor: str | None = None

        # Transform to schema
        data = []
        for result in results:
            # Look up workout data for this day/provider/device
            result_key = (result["activity_date"], result["provider_name"], result.get("device_id"))
            workout_data = workout_lookup.get(result_key, {})
            activity_data = activity_lookup.get(result_key, {})
            intensity_data = intensity_lookup.get(result_key, {})

            # Get elevation from workouts
            elevation_meters = workout_data.get("elevation_meters")

            # Calculate floors: prefer flights_climbed from time-series, fallback to elevation
            flights_climbed = result.get("flights_climbed_sum")
            if flights_climbed is not None:
                floors_climbed = flights_climbed
            elif elevation_meters is not None and elevation_meters > 0:
                floors_climbed = int(elevation_meters / METERS_PER_FLOOR)
            else:
                floors_climbed = None

            # Distance from time-series only
            # Note: workout distance (from WorkoutDetails) is typically a subset of daily distance,
            # not additive - providers report daily totals that include workout distance
            ts_distance = result.get("distance_sum")
            total_distance = float(ts_distance) if ts_distance is not None else None

            # Build heart rate stats if available
            hr_stats = None
            if result.get("hr_avg") is not None:
                hr_stats = HeartRateStats(
                    avg_bpm=result.get("hr_avg"),
                    max_bpm=result.get("hr_max"),
                    min_bpm=result.get("hr_min"),
                )

            # Calculate total calories from time-series data
            # Note: workout energy (from WorkoutDetails) is typically a subset of active_energy,
            # not additive - providers report daily totals that include workout calories
            active_cal = result.get("active_energy_sum")
            basal_cal = result.get("basal_energy_sum")
            total_cal = None
            if active_cal is not None or basal_cal is not None:
                total_cal = (active_cal or 0.0) + (basal_cal or 0.0)

            # Get active/sedentary minutes
            active_mins = activity_data.get("active_minutes")
            sedentary_mins = activity_data.get("sedentary_minutes")

            # Get intensity minutes from HR data
            intensity_mins = None
            if intensity_data:
                light = intensity_data.get("light_minutes", 0)
                moderate = intensity_data.get("moderate_minutes", 0)
                vigorous = intensity_data.get("vigorous_minutes", 0)
                intensity_mins = IntensityMinutes(
                    light=light,
                    moderate=moderate,
                    vigorous=vigorous,
                )

            steps = result.get("steps_sum")
            summary = ActivitySummary(
                date=result["activity_date"],
                source=DataSource(provider=result["provider_name"], device=result.get("device_id")),
                steps=steps if steps is not None else None,
                distance_meters=total_distance,
                floors_climbed=floors_climbed,
                elevation_meters=elevation_meters,
                active_calories_kcal=active_cal,
                total_calories_kcal=total_cal,
                active_minutes=active_mins,
                sedentary_minutes=sedentary_mins,
                intensity_minutes=intensity_mins,
                heart_rate=hr_stats,
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
