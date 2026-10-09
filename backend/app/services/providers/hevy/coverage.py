"""Declared data coverage for the Hevy provider.

Hevy is a gym/strength tracker: workouts only (exercises, sets, reps,
weights), no timeseries, sleep, or health scores. The per-set structure is
persisted in the structural ``segments`` JSONB field (excluded from coverage
by convention); ``distance`` is the only aggregated detail metric (summed
from cardio-machine sets that log meters).
"""

from app.schemas.enums import SeriesType
from app.schemas.enums.health_score_category import HealthScoreCategory

TIMESERIES: frozenset[SeriesType] = frozenset()

# Exercises and sets (reps, weights, RPE) are preserved losslessly in ``segments``.
WORKOUT_FIELDS: frozenset[str] = frozenset({"distance", "segments"})

SLEEP_FIELDS: frozenset[str] = frozenset()

HEALTH_SCORES: frozenset[HealthScoreCategory] = frozenset()
