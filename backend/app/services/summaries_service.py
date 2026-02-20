"""Service for daily summaries (sleep, activity, recovery, body)."""

from datetime import date, datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import DataPointSeries, EventRecord, ProviderPriority, User
from app.repositories import EventRecordRepository, ProviderPriorityRepository
from app.repositories.data_point_series_repository import (
    ActiveMinutesResult,
    DataPointSeriesRepository,
    IntensityMinutesResult,
)
from app.repositories.device_type_priority_repository import DeviceTypePriorityRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common_types import PaginatedResponse, Pagination, SourceMetadata, TimeseriesMetadata
from app.schemas.device_type import infer_device_type_from_model
from app.schemas.oauth import ProviderName
from app.schemas.series_types import SeriesType
from app.schemas.summaries import (
    ActivitySummary,
    BloodPressure,
    BodyAveraged,
    BodyLatest,
    BodySlowChanging,
    BodySummary,
    HeartRateStats,
    IntensityMinutes,
    SleepStagesSummary,
    SleepSummary,
)
from app.utils.exceptions import handle_exceptions
from app.utils.pagination import (
    decode_activity_cursor,
    encode_activity_cursor,
    encode_cursor,
)
from app.utils.structured_logging import log_structured

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

# Body summary constants
BP_TIMESTAMP_TOLERANCE_SECONDS = 5  # Max time difference for valid systolic/diastolic pair

BODY_SLOW_CHANGING_SERIES = [
    SeriesType.weight,
    SeriesType.height,
    SeriesType.body_fat_percentage,
    SeriesType.body_mass_index,
    SeriesType.lean_body_mass,
]

BODY_AVERAGED_SERIES = [
    SeriesType.resting_heart_rate,
    SeriesType.heart_rate_variability_sdnn,
]

# Default settings for body summary
DEFAULT_AVERAGE_PERIOD_DAYS = 7
DEFAULT_LATEST_WINDOW_HOURS = 4


class SummariesService:
    """Service for aggregating daily health summaries."""

    def __init__(self, log: Logger):
        self.logger = log
        self.event_record_repo = EventRecordRepository(EventRecord)
        self.data_point_repo = DataPointSeriesRepository(DataPointSeries)
        self.user_repo = UserRepository(User)

    def _filter_by_priority(
        self,
        db_session: DbSession,
        user_id: UUID,
        results: list[dict] | list,
        date_key: str = "activity_date",
    ) -> list[dict] | list:
        """Filter results to highest priority source per date.

        Args:
            results: List of dicts with date, source (provider), device_model
            date_key: Key name for date field (activity_date or sleep_date)

        Returns:
            Filtered list with only highest priority entry per date
        """
        if not results:
            return results

        provider_order = ProviderPriorityRepository(ProviderPriority).get_priority_order(db_session)
        device_type_order = DeviceTypePriorityRepository().get_priority_order(db_session)

        # Group results by date
        by_date: dict[date, list[dict]] = {}
        for result in results:
            dt = result[date_key]
            if dt not in by_date:
                by_date[dt] = []
            by_date[dt].append(result)

        # For each date, pick highest priority
        filtered = []
        for dt, entries in by_date.items():
            if len(entries) == 1:
                filtered.append(entries[0])
                continue

            # Sort by priority
            def sort_key(entry: dict) -> tuple[int, int, str]:
                # Parse provider
                source = entry.get("source", "unknown")
                try:
                    provider = ProviderName(source)
                except ValueError:
                    provider = ProviderName.UNKNOWN

                provider_priority = provider_order.get(provider, 99)

                # Parse device type
                device_model = entry.get("device_model")
                device_type_priority = 99
                if device_model:
                    device_type = infer_device_type_from_model(device_model)
                    device_type_priority = device_type_order.get(device_type, 99)

                return (provider_priority, device_type_priority, device_model or "")

            entries_sorted = sorted(entries, key=sort_key)
            filtered.append(entries_sorted[0])

        return filtered

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

        # Filter by priority to get best source per date
        results = self._filter_by_priority(db_session, user_id, results, date_key="sleep_date")

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

        # Pre-fetch physiological averages for all sleep records in a single batch query
        # This eliminates the N+1 query problem where we used to query per sleep record
        time_ranges: list[tuple[datetime, datetime]] = []
        result_indices: list[int] = []
        for idx, result in enumerate(results):
            sleep_start = result.get("min_start_time")
            sleep_end = result.get("max_end_time")
            if sleep_start and sleep_end:
                time_ranges.append((sleep_start, sleep_end))
                result_indices.append(idx)

        # Batch fetch all averages in one query (fixes N+1 issue #493)
        physio_averages_list: list[dict] = []
        if time_ranges:
            try:
                physio_averages_list = self.data_point_repo.get_averages_for_time_ranges(
                    db_session,
                    user_id,
                    time_ranges,
                    SLEEP_PHYSIO_SERIES_TYPES,
                )
            except Exception as e:
                log_structured(
                    self.logger,
                    "warning",
                    f"Failed to fetch heart rate metrics batch for sleep summaries: {e}",
                )
                # Fallback: all None values
                physio_averages_list = [{SeriesType.heart_rate: None} for _ in time_ranges]

        # Create a map from result index to averages
        averages_by_result: dict[int, dict] = {}
        for list_idx, result_idx in enumerate(result_indices):
            averages_by_result[result_idx] = physio_averages_list[list_idx]

        # Transform to schema
        data = []
        for idx, result in enumerate(results):
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

            # Get pre-fetched average heart rate for this sleep period
            # TODO: Add HRV, respiratory rate, and SpO2 when ready
            avg_hr: int | None = None
            physio_averages = averages_by_result.get(idx, {})
            hr_avg = physio_averages.get(SeriesType.heart_rate)
            if hr_avg is not None:
                avg_hr = int(round(hr_avg))

            summary = SleepSummary(
                date=result["sleep_date"],
                source=SourceMetadata(provider=result["source"] or "unknown", device=result.get("device_model")),
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
                avg_hrv_sdnn_ms=None,
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
        sort_order: str = "asc",
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

        # Filter by priority to get best source per date
        results = self._filter_by_priority(db_session, user_id, results, date_key="activity_date")

        # Get workout aggregates (elevation, distance, energy from workouts)
        workout_aggregates = self.event_record_repo.get_daily_workout_aggregates(
            db_session, user_id, start_date, end_date
        )

        # Build lookup dict for workout data by (date, provider, device)
        workout_lookup: dict[tuple, dict] = {}
        for wa in workout_aggregates:
            key = (wa["workout_date"], wa["source"], wa.get("device_model"))
            workout_lookup[key] = wa

        # Get active/sedentary minutes from step data
        activity_minutes = self.data_point_repo.get_daily_active_minutes(
            db_session, user_id, start_date, end_date, active_threshold=ACTIVE_STEPS_THRESHOLD
        )

        # Build lookup for activity minutes
        activity_lookup: dict[tuple, ActiveMinutesResult] = {}
        for am in activity_minutes:
            key = (am["activity_date"], am["source"], am.get("device_model"))
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
            key = (im["activity_date"], im["source"], im.get("device_model"))
            intensity_lookup[key] = im

        # Sort results based on sort_order (default ascending from DB)
        if sort_order == "desc":
            results = list(reversed(results))

        # Apply cursor-based pagination using compound key (date, provider, device)
        # This ensures we don't skip records when multiple providers exist for the same date
        if cursor:
            cursor_date, cursor_provider, cursor_device, direction = decode_activity_cursor(cursor)
            cursor_key = (cursor_date, cursor_provider, cursor_device or "")

            if direction == "prev":
                # Backward pagination: get items BEFORE cursor key (in current sort order)
                if sort_order == "desc":
                    # In desc order, "before" means items with GREATER keys
                    results = [
                        r
                        for r in results
                        if (r["activity_date"], r["source"] or "", r.get("device_model") or "") > cursor_key
                    ]
                else:
                    results = [
                        r
                        for r in results
                        if (r["activity_date"], r["source"] or "", r.get("device_model") or "") < cursor_key
                    ]
                # Reverse to get correct order for backward pagination
                results = list(reversed(results))
            else:
                # Forward pagination: get items AFTER cursor key (in current sort order)
                if sort_order == "desc":
                    # In desc order, "after" means items with SMALLER keys
                    results = [
                        r
                        for r in results
                        if (r["activity_date"], r["source"] or "", r.get("device_model") or "") < cursor_key
                    ]
                else:
                    results = [
                        r
                        for r in results
                        if (r["activity_date"], r["source"] or "", r.get("device_model") or "") > cursor_key
                    ]

        # Check for more data
        has_more = len(results) > limit
        if has_more:
            results = results[:limit]

        # Generate cursors
        next_cursor: str | None = None
        previous_cursor: str | None = None

        if results:
            # Next cursor points to last item's compound key
            if has_more:
                last = results[-1]
                next_cursor = encode_activity_cursor(
                    last["activity_date"], last["source"] or "unknown", last.get("device_model"), "next"
                )

            # Previous cursor if we had a cursor (not first page)
            if cursor:
                first = results[0]
                previous_cursor = encode_activity_cursor(
                    first["activity_date"], first["source"] or "unknown", first.get("device_model"), "prev"
                )

        # Transform to schema
        data = []
        for result in results:
            # Look up workout data for this day/provider/device
            result_key = (result["activity_date"], result["source"], result.get("device_model"))
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
                source=SourceMetadata(provider=result["source"] or "unknown", device=result.get("device_model")),
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

    def _calculate_age(self, birth_date: date, reference_date: date) -> int:
        """Calculate age in years from birth date to reference date."""
        age = reference_date.year - birth_date.year
        # Adjust if birthday hasn't occurred yet this year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        return age

    def _calculate_bmi(self, weight_kg: float | None, height_cm: float | None) -> float | None:
        """Calculate BMI from weight (kg) and height (cm).

        BMI = weight(kg) / height(m)^2
        """
        if weight_kg is None or height_cm is None or height_cm <= 0:
            return None
        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m * height_m)
        return round(bmi, 1)

    @handle_exceptions
    async def get_body_summary(
        self,
        db_session: DbSession,
        user_id: UUID,
        average_period_days: int = DEFAULT_AVERAGE_PERIOD_DAYS,
        latest_window_hours: int = DEFAULT_LATEST_WINDOW_HOURS,
    ) -> BodySummary | None:
        """Get comprehensive body metrics with semantic grouping.

        Returns body data organized into three categories:
        - slow_changing: Slow-changing values (weight, height, body fat, muscle mass, BMI, age)
        - averaged: Vitals averaged over a period (resting HR, HRV)
        - latest: Point-in-time readings only if recent (body temperature, blood pressure)

        Args:
            average_period_days: Days to average vitals over (1-7)
            latest_window_hours: Hours for "latest" readings to be considered valid (1-24)

        Returns:
            BodySummary with structured data, or None if no data exists

        Raises:
            ValueError: If parameters are out of valid range
        """
        if not 1 <= average_period_days <= 7:
            raise ValueError("average_period_days must be between 1 and 7")
        if not 1 <= latest_window_hours <= 24:
            raise ValueError("latest_window_hours must be between 1 and 24")

        self.logger.debug(
            f"Fetching body summary for user {user_id} "
            f"(avg_period={average_period_days}d, latest_window={latest_window_hours}h)"
        )

        now = datetime.now(timezone.utc)

        # Get user for age calculation
        user = self.user_repo.get(db_session, user_id)
        birth_date = None
        if user and user.personal_record:
            birth_date = user.personal_record.birth_date

        # --- SLOW-CHANGING: Get latest values for slow-changing metrics ---
        slow_changing_values = self.data_point_repo.get_latest_values_for_types(
            db_session, user_id, now, BODY_SLOW_CHANGING_SERIES
        )

        weight_data = slow_changing_values.get(SeriesType.weight)
        height_data = slow_changing_values.get(SeriesType.height)
        body_fat_data = slow_changing_values.get(SeriesType.body_fat_percentage)
        muscle_mass_data = slow_changing_values.get(SeriesType.lean_body_mass)
        bmi_data = slow_changing_values.get(SeriesType.body_mass_index)

        weight_kg = weight_data[0] if weight_data else None
        height_cm = height_data[0] if height_data else None
        body_fat_pct = body_fat_data[0] if body_fat_data else None
        muscle_mass_kg = muscle_mass_data[0] if muscle_mass_data else None

        # Use stored BMI if available, otherwise calculate from weight and height
        bmi = bmi_data[0] if bmi_data else self._calculate_bmi(weight_kg, height_cm)

        # Calculate age
        age = self._calculate_age(birth_date, now.date()) if birth_date else None

        # Determine source from most recent slow-changing measurement
        provider = "unknown"
        device_id = None
        for data in [weight_data, height_data, body_fat_data, muscle_mass_data]:
            if data:
                provider = data[2] or "unknown"
                device_id = data[3]
                break

        body_slow_changing = BodySlowChanging(
            weight_kg=weight_kg,
            height_cm=height_cm,
            body_fat_percent=body_fat_pct,
            muscle_mass_kg=muscle_mass_kg,
            bmi=bmi,
            age=age,
        )

        # --- AVERAGED: Get aggregates for vitals over the period ---
        period_end = now
        period_start = now - timedelta(days=average_period_days)

        vitals_aggregates = self.data_point_repo.get_aggregates_for_period(
            db_session, user_id, period_start, period_end, BODY_AVERAGED_SERIES
        )

        resting_hr_data = vitals_aggregates.get(SeriesType.resting_heart_rate)
        hrv_data = vitals_aggregates.get(SeriesType.heart_rate_variability_sdnn)

        resting_hr_avg = resting_hr_data.get("avg") if resting_hr_data else None
        resting_hr = int(round(resting_hr_avg)) if resting_hr_avg else None
        hrv_avg = hrv_data.get("avg") if hrv_data else None
        avg_hrv = round(hrv_avg, 1) if hrv_avg else None

        body_averaged = BodyAveraged(
            period_days=average_period_days,
            resting_heart_rate_bpm=resting_hr,
            avg_hrv_sdnn_ms=avg_hrv,
            period_start=period_start,
            period_end=period_end,
        )

        # --- LATEST: Get recent point-in-time readings ---
        latest_window_start = now - timedelta(hours=latest_window_hours)

        body_temp_reading = self.data_point_repo.get_latest_reading_within_window(
            db_session, user_id, SeriesType.body_temperature, latest_window_start, now
        )
        skin_temp_reading = self.data_point_repo.get_latest_reading_within_window(
            db_session, user_id, SeriesType.skin_temperature, latest_window_start, now
        )
        # Get blood pressure readings within the window
        bp_systolic_reading = self.data_point_repo.get_latest_reading_within_window(
            db_session, user_id, SeriesType.blood_pressure_systolic, latest_window_start, now
        )
        bp_diastolic_reading = self.data_point_repo.get_latest_reading_within_window(
            db_session, user_id, SeriesType.blood_pressure_diastolic, latest_window_start, now
        )

        # ignore provider and device id
        body_temp_celsius, body_temp_measured_at, _, _ = body_temp_reading or (None, None, None, None)
        skin_temp_celsius, skin_temp_measured_at, _, _ = skin_temp_reading or (None, None, None, None)

        # Blood pressure readings are only meaningful as a pair recorded at the same time.
        # Validate that both readings exist and their timestamps match within tolerance.
        # This guards against inconsistent or corrupted data where systolic and diastolic
        # might come from different measurement sessions.
        blood_pressure = None
        bp_measured_at = None

        if bp_systolic_reading and bp_diastolic_reading:
            time_diff = abs((bp_systolic_reading[1] - bp_diastolic_reading[1]).total_seconds())
            if time_diff <= BP_TIMESTAMP_TOLERANCE_SECONDS:
                blood_pressure = BloodPressure(
                    avg_systolic_mmhg=int(round(bp_systolic_reading[0])),
                    avg_diastolic_mmhg=int(round(bp_diastolic_reading[0])),
                    # For single point-in-time reading, no min/max/count needed
                    max_systolic_mmhg=None,
                    max_diastolic_mmhg=None,
                    min_systolic_mmhg=None,
                    min_diastolic_mmhg=None,
                    reading_count=1,
                )
                bp_measured_at = max(bp_systolic_reading[1], bp_diastolic_reading[1])

        # Check if we have any data at all
        has_slow_changing = any([weight_kg, height_cm, body_fat_pct, muscle_mass_kg])
        has_averaged = any([resting_hr, avg_hrv])
        has_latest = any([body_temp_celsius, skin_temp_celsius, blood_pressure])

        if not has_slow_changing and not has_averaged and not has_latest:
            return None

        body_latest = BodyLatest(
            body_temperature_celsius=body_temp_celsius,
            body_temperature_measured_at=body_temp_measured_at,
            skin_temperature_celsius=skin_temp_celsius,
            skin_temperature_measured_at=skin_temp_measured_at,
            blood_pressure=blood_pressure,
            blood_pressure_measured_at=bp_measured_at,
        )

        return BodySummary(
            source=SourceMetadata(provider=provider, device=device_id),
            slow_changing=body_slow_changing,
            averaged=body_averaged,
            latest=body_latest,
        )


summaries_service = SummariesService(log=getLogger(__name__))
