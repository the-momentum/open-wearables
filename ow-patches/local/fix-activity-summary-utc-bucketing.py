# patch_id:        fix-activity-summary-utc-bucketing
# upstream_file:   backend/app/repositories/data_point_series_repository.py
# upstream_symbol: DataPointSeriesRepository.get_daily_activity_aggregates + .get_daily_active_minutes + .get_daily_intensity_minutes
# retire_when:     DataPointSeriesRepository buckets daily aggregates by the user's IANA
#                  timezone (not by per-row zone_offset with a UTC fallback).
#                  Marker (same as PATCHES.md): `_local_date_bucket_expr` or any
#                  `AT TIME ZONE user.timezone` bucketing in data_point_series_repository.py.
#                  NOT a bare `func.timezone` grep — upstream c8409b55 added
#                  `func.timezone("UTC", ...)` (utc_bucket_start) to repositories.py, which is
#                  unrelated. Upstream currently buckets by
#                  `cast(recorded_at + coalesce(zone_offset, "+00:00"), Date)`.

"""Bucket the three daily activity aggregates by the user's local date.

Background
----------
Upstream buckets each daily aggregate query by the per-row ``zone_offset``
column, falling back to UTC when that column is NULL:

    local_date = cast(
        recorded_at + coalesce(zone_offset, "+00:00")::interval,
        Date,
    )

This correctly handles providers that populate ``zone_offset`` (e.g. Apple
Health) but silently falls back to UTC for Garmin Connect / Ultrahuman, which
leave ``zone_offset`` NULL on their historical sync data. For a Brisbane user
(UTC+10) a Sunday-morning trail run (UTC timestamps: Saturday evening) lands on
the Saturday card with the wrong HR/step stats.

Our delta
---------
This is the ONLY thing this patch changes versus upstream: instead of bucketing
purely by ``recorded_at + zone_offset`` (UTC when NULL), we add a user-timezone
fallback so providers that leave ``zone_offset`` NULL still bucket locally:

    local_date = cast(
        coalesce(
            recorded_at + zone_offset::interval,          # 1. honor a real recorded offset
            timezone(user.timezone, recorded_at),         # 2. else recorded_at AT TIME ZONE user_tz
        ),
        Date,
    )

Priority chain:
  1. ``zone_offset`` present on the row  -> honor it (identical to upstream; a
     real recorded offset wins even when the user travels).
  2. ``zone_offset`` NULL                -> ``recorded_at AT TIME ZONE user.timezone``.
  3. ``user.timezone`` also NULL         -> ``_resolve_user_timezone`` returns
     ``"UTC"``, so it degrades to upstream's UTC behavior (safe default).

``recorded_at`` is stored as ``timestamptz``, so ``AT TIME ZONE user.timezone``
yields the local wall-clock timestamp and ``::date`` the local calendar date.
The timezone string is resolved once per call in Python from the ``User`` row.

Everything else in these three methods is upstream's current behaviour, kept
verbatim:
  * ``prefer_daily_sum()`` / ``is_daily_total`` de-duplication that avoids
    double-counting a provider daily-total against its own intraday epochs,
    including the ``is_daily_total.isnot(True)`` filter in active-minutes (#1232).
  * ``active_time`` aggregation returned as ``active_time_minutes`` and
    ``DataSource.provider`` added to the SELECT / GROUP BY / result dict (#1242).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import ColumnElement, Date, Interval, and_, asc, case, cast, func, literal_column

from app.database import DbSession
from app.models import DataSource
from app.schemas.enums import SeriesType, get_series_type_id
from app.schemas.responses.activity import (
    ActiveMinutesResult,
    ActivityAggregateResult,
    IntensityMinutesResult,
)


def _resolve_user_timezone(db_session: DbSession, user_id: UUID) -> str:
    """Return the user's IANA timezone string, or 'UTC' as the safe default."""
    from app.models import User  # noqa: PLC0415

    tz = db_session.query(User.timezone).filter(User.id == user_id).scalar()
    return tz or "UTC"


# ---------------------------------------------------------------------------
# get_daily_activity_aggregates
# ---------------------------------------------------------------------------


def get_daily_activity_aggregates(
    self,
    db_session: DbSession,
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
) -> list[ActivityAggregateResult]:
    """Get daily activity aggregates from time-series data.

    Aggregates steps, energy, heart rate stats by date for a user.

    Returns list of dicts with keys:
    - activity_date, provider, source, device_model, device_type
    - steps_sum, active_energy_sum, basal_energy_sum
    - hr_avg, hr_max, hr_min
    - distance_sum, flights_climbed_sum, active_time_minutes
    """
    # Series type IDs we need
    steps_id = get_series_type_id(SeriesType.steps)
    energy_id = get_series_type_id(SeriesType.energy)
    basal_energy_id = get_series_type_id(SeriesType.basal_energy)
    hr_id = get_series_type_id(SeriesType.heart_rate)
    distance_id = get_series_type_id(SeriesType.distance_walking_running)
    flights_id = get_series_type_id(SeriesType.flights_climbed)
    active_time_id = get_series_type_id(SeriesType.active_time)

    # OUR DELTA: bucket by the user's local date. Priority chain:
    #   1. zone_offset present on the row  -> honor it (identical to upstream)
    #   2. zone_offset NULL                -> recorded_at AT TIME ZONE user.timezone
    #   3. user.timezone also NULL         -> user_tz == "UTC", degrades to upstream UTC behavior
    user_tz = _resolve_user_timezone(db_session, user_id)
    local_date = cast(
        func.coalesce(
            self.model.recorded_at + cast(self.model.zone_offset, Interval),
            func.timezone(user_tz, self.model.recorded_at),
        ),
        Date,
    )

    def prefer_daily_sum(series_id: int) -> ColumnElement:
        """Per (day, source): use the daily-total rows if any exist, else sum samples.

        Removes the Garmin/Suunto double-count (a daily total + its own intraday
        epochs). NULL is_daily_total counts as "not daily" (legacy rows are summed).
        COALESCE falls through to the sample sum only when no daily total exists.
        """
        daily = func.sum(
            case(
                (
                    and_(self.model.series_type_definition_id == series_id, self.model.is_daily_total.is_(True)),
                    self.model.value,
                )
            )
        )
        samples = func.sum(
            case(
                (
                    and_(self.model.series_type_definition_id == series_id, self.model.is_daily_total.isnot(True)),
                    self.model.value,
                )
            )
        )
        return func.coalesce(daily, samples)

    # Build aggregation query
    results = (
        db_session.query(
            local_date.label("activity_date"),
            DataSource.provider.label("provider"),
            DataSource.source.label("source"),
            DataSource.device_model.label("device_model"),
            # device_type is functionally dependent on the three columns above
            # (uq_data_source_identity is unique per user on
            # provider/device_model/source), so adding it to the GROUP BY cannot
            # change the number of groups. Added upstream in #1414.
            DataSource.device_type.label("device_type"),
            # Steps - prefer daily total, else sum samples
            prefer_daily_sum(steps_id).label("steps_sum"),
            # Active energy - prefer daily total, else sum samples
            prefer_daily_sum(energy_id).label("active_energy_sum"),
            # Basal energy - prefer daily total, else sum samples
            prefer_daily_sum(basal_energy_id).label("basal_energy_sum"),
            # Heart rate stats
            func.avg(case((self.model.series_type_definition_id == hr_id, self.model.value), else_=None)).label(
                "hr_avg"
            ),
            func.max(case((self.model.series_type_definition_id == hr_id, self.model.value), else_=None)).label(
                "hr_max"
            ),
            func.min(case((self.model.series_type_definition_id == hr_id, self.model.value), else_=None)).label(
                "hr_min"
            ),
            # Distance - prefer daily total, else sum samples (NULL when no data)
            prefer_daily_sum(distance_id).label("distance_sum"),
            # Flights climbed - prefer daily total, else sum samples (NULL when no data)
            prefer_daily_sum(flights_id).label("flights_climbed_sum"),
            # Provider-reported active time (minutes) - daily total (NULL when no data)
            prefer_daily_sum(active_time_id).label("active_time_sum"),
        )
        .join(DataSource, self.model.data_source_id == DataSource.id)
        .filter(
            DataSource.user_id == user_id,
            self.model.recorded_at >= start_date - timedelta(days=1),
            local_date >= cast(start_date, Date),
            local_date < cast(end_date, Date),
            self.model.series_type_definition_id.in_(
                [steps_id, energy_id, basal_energy_id, hr_id, distance_id, flights_id, active_time_id]
            ),
        )
        .group_by(
            local_date,
            DataSource.provider,
            DataSource.source,
            DataSource.device_model,
            DataSource.device_type,
        )
        .order_by(asc(local_date))
        .all()
    )

    # Transform to list of dicts
    aggregates: list[ActivityAggregateResult] = []
    for row in results:
        aggregates.append(
            {
                "activity_date": row.activity_date,
                "provider": row.provider,
                "source": row.source,
                "device_model": row.device_model,
                "device_type": row.device_type,
                "steps_sum": int(row.steps_sum) if row.steps_sum else 0,
                "active_energy_sum": float(row.active_energy_sum) if row.active_energy_sum else 0.0,
                "basal_energy_sum": float(row.basal_energy_sum) if row.basal_energy_sum else 0.0,
                "hr_avg": int(round(float(row.hr_avg))) if row.hr_avg is not None else None,
                "hr_max": int(row.hr_max) if row.hr_max is not None else None,
                "hr_min": int(row.hr_min) if row.hr_min is not None else None,
                "distance_sum": float(row.distance_sum) if row.distance_sum is not None else None,
                "flights_climbed_sum": int(row.flights_climbed_sum)
                if row.flights_climbed_sum is not None
                else None,
                "active_time_minutes": int(row.active_time_sum) if row.active_time_sum is not None else None,
            }
        )
    return aggregates


# ---------------------------------------------------------------------------
# get_daily_active_minutes
# ---------------------------------------------------------------------------


def get_daily_active_minutes(
    self,
    db_session: DbSession,
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
    active_threshold: int = 30,
) -> list[ActiveMinutesResult]:
    """Get daily active/sedentary minutes from step data.

    Buckets step data by minute and counts:
    - active_minutes: minutes with steps >= threshold
    - tracked_minutes: total minutes with any step data
    - sedentary_minutes: tracked_minutes - active_minutes

    Args:
        active_threshold: Steps per minute to be considered "active" (default: 30)

    Returns list of dicts with keys:
    - activity_date, source, device_model
    - active_minutes, tracked_minutes, sedentary_minutes
    """
    steps_id = get_series_type_id(SeriesType.steps)

    # OUR DELTA: bucket by the user's local date. Priority chain:
    #   1. zone_offset present on the row  -> honor it (identical to upstream)
    #   2. zone_offset NULL                -> recorded_at AT TIME ZONE user.timezone
    #   3. user.timezone also NULL         -> user_tz == "UTC", degrades to upstream UTC behavior
    user_tz = _resolve_user_timezone(db_session, user_id)
    local_date = cast(
        func.coalesce(
            self.model.recorded_at + cast(self.model.zone_offset, Interval),
            func.timezone(user_tz, self.model.recorded_at),
        ),
        Date,
    )

    # Create minute bucket expression using literal 'minute' text
    minute_trunc = func.date_trunc(literal_column("'minute'"), self.model.recorded_at)

    # Subquery: bucket step data by minute and sum steps per minute
    minute_bucket = (
        db_session.query(
            local_date.label("activity_date"),
            DataSource.source,
            DataSource.device_model,
            minute_trunc.label("minute_bucket"),
            func.sum(self.model.value).label("steps_in_minute"),
        )
        .join(DataSource, self.model.data_source_id == DataSource.id)
        .filter(
            DataSource.user_id == user_id,
            self.model.recorded_at >= start_date - timedelta(days=1),
            local_date >= cast(start_date, Date),
            local_date < cast(end_date, Date),
            self.model.series_type_definition_id == steps_id,
            self.model.is_daily_total.isnot(True),
        )
        .group_by(
            local_date,
            DataSource.source,
            DataSource.device_model,
            minute_trunc,
        )
        .subquery()
    )

    # Main query: aggregate minute buckets to get daily active/tracked counts
    results = (
        db_session.query(
            minute_bucket.c.activity_date,
            minute_bucket.c.source,
            minute_bucket.c.device_model,
            # Count minutes where steps >= threshold (active)
            func.sum(case((minute_bucket.c.steps_in_minute >= active_threshold, 1), else_=0)).label(
                "active_minutes"
            ),
            # Count all tracked minutes
            func.count(minute_bucket.c.minute_bucket).label("tracked_minutes"),
        )
        .group_by(
            minute_bucket.c.activity_date,
            minute_bucket.c.source,
            minute_bucket.c.device_model,
        )
        .order_by(asc(minute_bucket.c.activity_date))
        .all()
    )

    aggregates: list[ActiveMinutesResult] = []
    for row in results:
        active = int(row.active_minutes) if row.active_minutes else 0
        tracked = int(row.tracked_minutes) if row.tracked_minutes else 0
        sedentary = tracked - active

        aggregates.append(
            {
                "activity_date": row.activity_date,
                "source": row.source,
                "device_model": row.device_model,
                "active_minutes": active,
                "tracked_minutes": tracked,
                "sedentary_minutes": sedentary,
            }
        )
    return aggregates


# ---------------------------------------------------------------------------
# get_daily_intensity_minutes
# ---------------------------------------------------------------------------


def get_daily_intensity_minutes(
    self,
    db_session: DbSession,
    user_id: UUID,
    start_date: datetime,
    end_date: datetime,
    light_min: int,
    light_max: int,
    moderate_max: int,
    vigorous_max: int,
) -> list[IntensityMinutesResult]:
    """Get daily intensity minutes from heart rate data.

    Buckets HR data by minute and categorizes by intensity zone based on
    provided HR thresholds. Zone boundaries are calculated by the service layer.

    Args:
        light_min: Lower bound for light zone (inclusive)
        light_max: Upper bound for light zone (inclusive)
        moderate_max: Upper bound for moderate zone (inclusive, lower bound is light_max + 1)
        vigorous_max: Upper bound for vigorous zone (inclusive, lower bound is moderate_max + 1)

    Returns list of dicts with keys:
    - activity_date, source, device_model
    - light_minutes, moderate_minutes, vigorous_minutes
    """
    hr_id = get_series_type_id(SeriesType.heart_rate)

    # OUR DELTA: bucket by the user's local date. Priority chain:
    #   1. zone_offset present on the row  -> honor it (identical to upstream)
    #   2. zone_offset NULL                -> recorded_at AT TIME ZONE user.timezone
    #   3. user.timezone also NULL         -> user_tz == "UTC", degrades to upstream UTC behavior
    user_tz = _resolve_user_timezone(db_session, user_id)
    local_date = cast(
        func.coalesce(
            self.model.recorded_at + cast(self.model.zone_offset, Interval),
            func.timezone(user_tz, self.model.recorded_at),
        ),
        Date,
    )

    # Create minute bucket expression
    minute_trunc = func.date_trunc(literal_column("'minute'"), self.model.recorded_at)

    # Subquery: bucket HR data by minute and get avg HR per minute
    minute_bucket = (
        db_session.query(
            local_date.label("activity_date"),
            DataSource.source,
            DataSource.device_model,
            minute_trunc.label("minute_bucket"),
            func.avg(self.model.value).label("avg_hr_in_minute"),
        )
        .join(DataSource, self.model.data_source_id == DataSource.id)
        .filter(
            DataSource.user_id == user_id,
            self.model.recorded_at >= start_date - timedelta(days=1),
            local_date >= cast(start_date, Date),
            local_date < cast(end_date, Date),
            self.model.series_type_definition_id == hr_id,
        )
        .group_by(
            local_date,
            DataSource.source,
            DataSource.device_model,
            minute_trunc,
        )
        .subquery()
    )

    # Main query: categorize minute buckets into intensity zones
    results = (
        db_session.query(
            minute_bucket.c.activity_date,
            minute_bucket.c.source,
            minute_bucket.c.device_model,
            # Light: 50-63% of max HR
            func.sum(
                case(
                    (
                        (minute_bucket.c.avg_hr_in_minute >= light_min)
                        & (minute_bucket.c.avg_hr_in_minute <= light_max),
                        1,
                    ),
                    else_=0,
                )
            ).label("light_minutes"),
            # Moderate: 64-76% of max HR
            func.sum(
                case(
                    (
                        (minute_bucket.c.avg_hr_in_minute > light_max)
                        & (minute_bucket.c.avg_hr_in_minute <= moderate_max),
                        1,
                    ),
                    else_=0,
                )
            ).label("moderate_minutes"),
            # Vigorous: 77-93% of max HR
            func.sum(
                case(
                    (
                        (minute_bucket.c.avg_hr_in_minute > moderate_max)
                        & (minute_bucket.c.avg_hr_in_minute <= vigorous_max),
                        1,
                    ),
                    else_=0,
                )
            ).label("vigorous_minutes"),
        )
        .group_by(
            minute_bucket.c.activity_date,
            minute_bucket.c.source,
            minute_bucket.c.device_model,
        )
        .order_by(asc(minute_bucket.c.activity_date))
        .all()
    )

    aggregates: list[IntensityMinutesResult] = []
    for row in results:
        aggregates.append(
            {
                "activity_date": row.activity_date,
                "source": row.source,
                "device_model": row.device_model,
                "light_minutes": int(row.light_minutes) if row.light_minutes else 0,
                "moderate_minutes": int(row.moderate_minutes) if row.moderate_minutes else 0,
                "vigorous_minutes": int(row.vigorous_minutes) if row.vigorous_minutes else 0,
            }
        )
    return aggregates


def install() -> None:
    """Replace the three daily-aggregation methods on DataPointSeriesRepository."""
    import sys  # noqa: PLC0415

    import app.repositories.data_point_series_repository  # noqa: F401, PLC0415

    repo_module = sys.modules["app.repositories.data_point_series_repository"]
    repo_module.DataPointSeriesRepository.get_daily_activity_aggregates = get_daily_activity_aggregates
    repo_module.DataPointSeriesRepository.get_daily_active_minutes = get_daily_active_minutes
    repo_module.DataPointSeriesRepository.get_daily_intensity_minutes = get_daily_intensity_minutes
