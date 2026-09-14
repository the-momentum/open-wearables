"""Daily totals computed from two dailyRollUp operands.

total-calories is Fitbit's own per-minute model (a basal floor plus an activity term) and has
no list form, so basal is only reachable as the remainder once active is taken out. Both
operands are fetched on the same civil days, so energy + basal_energy reconciles to Google's
total exactly.
"""

from app.schemas.enums import SeriesType
from app.schemas.providers.google import DailyRollupSpec, DerivedDailyMetric

DERIVED_DAILY_METRICS: tuple[DerivedDailyMetric, ...] = (
    DerivedDailyMetric(
        "basal-energy-derived",
        SeriesType.basal_energy,
        DailyRollupSpec("total-calories", "totalCalories", "kcalSum", max_range_days=14),
        DailyRollupSpec("active-energy-burned", "activeEnergyBurned", "kcalSum"),
        lambda total, active: total - active,
    ),
)
