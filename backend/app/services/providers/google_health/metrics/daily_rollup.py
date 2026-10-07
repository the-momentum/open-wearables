"""Civil-day totals read straight from one dataPoints:dailyRollUp data type.

active-minutes reports whole minutes per activity level; exercise_time keeps the moderate and
vigorous ones, unweighted, so it means the same as the other providers' intensity minutes.
"""

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DailyRollupMetric, DailyRollupSpec, LevelSum

DAILY_ROLLUP_METRICS: tuple[DailyRollupMetric, ...] = (
    DailyRollupMetric(
        "active-minutes",
        SeriesType.exercise_time,
        DailyRollupSpec(
            "active-minutes",
            "activeMinutes",
            "activeMinutesRollupByActivityLevel",
            max_range_days=14,
            level_sum=LevelSum("activityLevel", "activeMinutesSum", frozenset({"MODERATE", "VIGOROUS"})),
        ),
    ),
)
