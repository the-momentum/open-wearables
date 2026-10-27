"""How code before the aggregate tables stored day and session values as series_sample rows.

Frozen history, on purpose not derived from the providers' current mappings: it describes rows already
written, so it must not move when a provider's mapping does. The aggregate backfill copies what these
rules match into series_aggregate and event_record_aggregate; the later cleanup deletes a copy only where it sits at
the very instant of its aggregate row, so the rest stay samples.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.schemas.enums import ProviderName, SeriesType
from app.schemas.model_crud.activities import StatColumn


class DayAnchor(StrEnum):
    """How a day value's recorded_at maps onto its calendar day."""

    # recorded_at is the local midnight and zone_offset its offset (or NULL for UTC).
    LOCAL = "local"
    # recorded_at is 00:00 UTC of the provider's date.
    UTC_DATE = "utc_date"
    # recorded_at is the local midnight but the offset was not kept: the day is the date 13 hours on, right for
    # every offset from -11:00 (Samoa) to +13:00 (New Zealand in summer).
    LOCAL_MIDNIGHT_NO_OFFSET = "local_midnight_no_offset"
    # recorded_at is when the night's sleep started, at the row's offset: the day is the one the user woke up on,
    # the local date 12 hours on.
    NIGHT_STARTED_AT = "night_started_at"


class SessionMatch(StrEnum):
    """Which event record a session value belongs to."""

    # The sleep of the same data source whose window holds recorded_at.
    SLEEP_CONTAINING = "sleep_containing"
    # The sleep with the sample's external_id, else the one ending at recorded_at.
    SLEEP_BY_ID_OR_END = "sleep_by_id_or_end"
    # The latest main sleep that ended within 24 hours before recorded_at.
    SLEEP_ENDED_BEFORE = "sleep_ended_before"
    # The workout ending at recorded_at.
    WORKOUT_ENDING = "workout_ending"


@dataclass(frozen=True)
class HistoryRule:
    providers: frozenset[ProviderName]
    # Each series with the statistic it holds; None is the series' own (its aggregation method).
    series: tuple[tuple[SeriesType, StatColumn | None], ...]
    # Further SQL condition on series_sample `s`, for series that also have genuine samples.
    where: str = "TRUE"
    day: DayAnchor | None = None
    session: SessionMatch | None = None


def _own(*series: SeriesType) -> tuple[tuple[SeriesType, StatColumn | None], ...]:
    return tuple((series_type, None) for series_type in series)


_DAILY_TOTAL = "s.is_daily_total IS TRUE"
_UTC_MIDNIGHT = "s.recorded_at = date_trunc('day', s.recorded_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'"
_SDK = frozenset({ProviderName.APPLE, ProviderName.SAMSUNG, ProviderName.HEALTH_CONNECT})

HISTORY_RULES: tuple[HistoryRule, ...] = (
    # Garmin dailies at the local midnight; steps and energy share their keys with epochs.
    HistoryRule(
        frozenset({ProviderName.GARMIN}),
        _own(
            SeriesType.steps,
            SeriesType.active_energy,
            SeriesType.basal_energy,
            SeriesType.flights_climbed,
            SeriesType.distance_walking_running,
            SeriesType.active_time,
            SeriesType.exercise_time,
        ),
        where=_DAILY_TOTAL,
        day=DayAnchor.LOCAL,
    ),
    HistoryRule(frozenset({ProviderName.GARMIN}), _own(SeriesType.resting_heart_rate), day=DayAnchor.LOCAL),
    # Garmin lastNightAvg carries the bare summaryId; its per-reading values carry "summaryId:offset".
    HistoryRule(
        frozenset({ProviderName.GARMIN}),
        _own(SeriesType.heart_rate_variability_rmssd),
        where="s.external_id IS NOT NULL AND position(':' in s.external_id) = 0",
        day=DayAnchor.NIGHT_STARTED_AT,
    ),
    HistoryRule(
        frozenset({ProviderName.GARMIN}),
        _own(SeriesType.vo2_max, SeriesType.garmin_fitness_age, SeriesType.skin_temperature_deviation),
        day=DayAnchor.UTC_DATE,
    ),
    HistoryRule(
        frozenset({ProviderName.OURA}),
        _own(
            SeriesType.steps,
            SeriesType.active_energy,
            SeriesType.basal_energy,
            SeriesType.distance_walking_running,
            SeriesType.active_time,
            SeriesType.exercise_time,
        ),
        day=DayAnchor.LOCAL,
    ),
    HistoryRule(
        frozenset({ProviderName.OURA}),
        _own(SeriesType.skin_temperature_deviation, SeriesType.skin_temperature_trend_deviation, SeriesType.vo2_max),
        day=DayAnchor.LOCAL_MIDNIGHT_NO_OFFSET,
    ),
    HistoryRule(
        frozenset({ProviderName.OURA}),
        _own(SeriesType.oxygen_saturation, SeriesType.breathing_disturbance_index, SeriesType.cardiovascular_age),
        day=DayAnchor.UTC_DATE,
    ),
    HistoryRule(
        frozenset({ProviderName.OURA}),
        _own(SeriesType.respiratory_rate, SeriesType.resting_heart_rate),
        session=SessionMatch.SLEEP_CONTAINING,
    ),
    # Polar stored its local midnight wall-clock as if it were UTC.
    HistoryRule(
        frozenset({ProviderName.POLAR}),
        _own(
            SeriesType.steps,
            SeriesType.active_energy,
            SeriesType.basal_energy,
            SeriesType.distance_walking_running,
            SeriesType.active_time,
            SeriesType.exercise_time,
        ),
        where=_DAILY_TOTAL,
        day=DayAnchor.UTC_DATE,
    ),
    HistoryRule(
        frozenset({ProviderName.POLAR}),
        _own(
            SeriesType.heart_rate_variability_rmssd,
            SeriesType.respiratory_rate,
            SeriesType.skin_temperature,
            SeriesType.skin_temperature_deviation,
        ),
        where=_UTC_MIDNIGHT,
        day=DayAnchor.UTC_DATE,
    ),
    # Withings activity rows have "activity:{date}..." ids; its intraday rows "intraday:...".
    HistoryRule(
        frozenset({ProviderName.WITHINGS}),
        _own(
            SeriesType.steps,
            SeriesType.distance_walking_running,
            SeriesType.active_energy,
            SeriesType.exercise_time,
            SeriesType.basal_energy,
        ),
        where="s.external_id LIKE 'activity:%'",
        day=DayAnchor.LOCAL,
    ),
    HistoryRule(
        frozenset({ProviderName.WITHINGS}),
        _own(SeriesType.resting_heart_rate),
        session=SessionMatch.SLEEP_CONTAINING,
    ),
    HistoryRule(
        frozenset({ProviderName.SUUNTO}),
        _own(SeriesType.steps, SeriesType.active_energy),
        where=_DAILY_TOTAL,
        day=DayAnchor.LOCAL_MIDNIGHT_NO_OFFSET,
    ),
    # Suunto wrote its nightly values with is_daily_total even for averages, at the sleep's end.
    HistoryRule(
        frozenset({ProviderName.SUUNTO}),
        (
            (SeriesType.resting_heart_rate, None),
            (SeriesType.heart_rate_variability_rmssd, None),
            (SeriesType.oxygen_saturation, "max"),
        ),
        where=_DAILY_TOTAL,
        session=SessionMatch.SLEEP_BY_ID_OR_END,
    ),
    # Whoop cycles: the local midnight of the cycle's day (its start before 2026-09-30).
    HistoryRule(frozenset({ProviderName.WHOOP}), _own(SeriesType.total_energy, SeriesType.steps), day=DayAnchor.LOCAL),
    # Whoop recovery was stored at its creation, after the sleep it scores, without the sleep's id.
    HistoryRule(
        frozenset({ProviderName.WHOOP}),
        _own(
            SeriesType.resting_heart_rate,
            SeriesType.heart_rate_variability_rmssd,
            SeriesType.oxygen_saturation,
            SeriesType.skin_temperature,
        ),
        session=SessionMatch.SLEEP_ENDED_BEFORE,
    ),
    HistoryRule(
        frozenset({ProviderName.SENSORBIO}),
        _own(SeriesType.resting_heart_rate, SeriesType.heart_rate_variability_rmssd, SeriesType.oxygen_saturation),
        where=_UTC_MIDNIGHT,
        day=DayAnchor.UTC_DATE,
    ),
    HistoryRule(
        frozenset({ProviderName.SENSORBIO}),
        _own(SeriesType.steps, SeriesType.active_energy, SeriesType.distance_walking_running, SeriesType.basal_energy),
        day=DayAnchor.UTC_DATE,
    ),
    HistoryRule(
        frozenset({ProviderName.ULTRAHUMAN}),
        _own(
            SeriesType.vo2_max,
            SeriesType.exercise_time,
            SeriesType.resting_heart_rate,
            SeriesType.skin_temperature_deviation,
        ),
        day=DayAnchor.LOCAL_MIDNIGHT_NO_OFFSET,
    ),
    HistoryRule(
        frozenset({ProviderName.GOOGLE_HEALTH}),
        _own(SeriesType.exercise_time, SeriesType.basal_energy),
        where=f"{_DAILY_TOTAL} AND {_UTC_MIDNIGHT}",
        day=DayAnchor.UTC_DATE,
    ),
    # SDK workout statistics, stored at the workout's end without an external_id (a genuine record ending there,
    # an Apple VO2 max estimate say, carries its own); mean and max cadence shared one row, read as the mean.
    HistoryRule(
        _SDK,
        _own(
            SeriesType.cadence,
            SeriesType.physical_effort,
            SeriesType.running_ground_contact_time,
            SeriesType.running_stride_length,
            SeriesType.running_vertical_oscillation,
            SeriesType.steps,
            SeriesType.swimming_stroke_count,
            SeriesType.vo2_max,
            SeriesType.weather_humidity,
            SeriesType.weather_temperature,
        ),
        # The Apple Health XML export has no ids at all: whatever it has at a workout's end is a genuine record.
        where="""s.external_id IS NULL AND NOT EXISTS (
            SELECT 1 FROM data_source d WHERE d.id = s.data_source_id AND d.source = 'apple_health_xml')""",
        session=SessionMatch.WORKOUT_ENDING,
    ),
)
