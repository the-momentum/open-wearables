"""Civil-day totals read straight from one dataPoints:dailyRollUp data type.

active-minutes reports whole minutes per activity level; exercise_time keeps the moderate and
vigorous ones, unweighted, so it means the same as the other providers' intensity minutes.

Most current devices (Charge 4 and later, Inspire 2/3, Sense, Versa, Pixel Watch 1-3) report
active-zone-minutes instead, so days without active-minutes fall back to it. Zone minutes are
weighted (1 per fat-burn minute, 2 per cardio or peak minute); halving cardio and peak turns them
back into minutes, with fat burn as moderate and cardio/peak as vigorous.
"""

from decimal import Decimal

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DailyRollupMetric, DailyRollupSpec, LevelSum

_HALF = Decimal("0.5")

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
        fallback=DailyRollupSpec(
            "active-zone-minutes",
            "activeZoneMinutes",
            "sumInFatBurnHeartZone",
            max_range_days=14,
            weighted_fields=(
                ("sumInFatBurnHeartZone", Decimal(1)),
                ("sumInCardioHeartZone", _HALF),
                ("sumInPeakHeartZone", _HALF),
            ),
        ),
    ),
)
