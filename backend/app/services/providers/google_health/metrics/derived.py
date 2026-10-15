"""Daily totals computed from two dailyRollUp operands.

total-calories is Fitbit's own per-minute model (a basal floor plus an activity term) and has
no list form, so basal is only reachable as the remainder once active is taken out. Both
operands are read from the same civil days and the same data-source family, so the remainder
is Google's own basal for that day. The stored energy series comes from reconcile/list over
every source, so energy + basal_energy approximates, not reproduces, Google's total.
"""

import operator

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DailyRollupSpec, DerivedDailyMetric

DERIVED_DAILY_METRICS: tuple[DerivedDailyMetric, ...] = (
    DerivedDailyMetric(
        "basal-energy-derived",
        SeriesType.basal_energy,
        DailyRollupSpec("total-calories", "totalCalories", "kcalSum", max_range_days=14),
        DailyRollupSpec("active-energy-burned", "activeEnergyBurned", "kcalSum"),
        operator.sub,
    ),
)
