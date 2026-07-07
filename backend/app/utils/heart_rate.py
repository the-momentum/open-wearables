"""Shared heart-rate helpers.

Single source of truth for the ``220 - age`` max-HR estimate and the Edwards
HR-zone boundaries. Used by both the daily activity summaries
(``summaries_service``) and the ``workout.created`` outgoing webhook's Edwards
zone computation (``event_record_service`` → ``data_point_series_repository``),
so the formula and its fallback can never drift between the two paths.
"""

from datetime import date, datetime

# Assumes ~30 years old (max_hr = 220 - 30) when birth_date is unavailable.
DEFAULT_MAX_HR = 190

# Floor so an implausibly old age never collapses the zones to nothing.
MIN_ESTIMATED_MAX_HR = 100

# Edwards 5-zone lower bounds as fractions of max HR. Bands are HALF-OPEN:
#   zone_1 = [0.50, 0.60)   zone_2 = [0.60, 0.70)   zone_3 = [0.70, 0.80)
#   zone_4 = [0.80, 0.90)   zone_5 = [0.90, +inf)   (zone 5 is unclamped)
# Average HR below 0.50 * max_hr falls in no zone.
EDWARDS_ZONE_LOWER_FRACTIONS = (0.50, 0.60, 0.70, 0.80, 0.90)


def estimate_max_hr(birth_date: date | None, reference_date: datetime) -> int:
    """Estimate max HR as ``220 - age`` at ``reference_date``.

    Falls back to :data:`DEFAULT_MAX_HR` when ``birth_date`` is unavailable, and
    floors the result at :data:`MIN_ESTIMATED_MAX_HR`.
    """
    if birth_date is None:
        return DEFAULT_MAX_HR
    age = reference_date.year - birth_date.year
    # Adjust if the birthday hasn't occurred yet this year.
    if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return max(220 - age, MIN_ESTIMATED_MAX_HR)


def edwards_zone_lower_bounds(max_hr: int) -> tuple[int, int, int, int, int]:
    """Return the five integer BPM lower bounds for the Edwards zones at ``max_hr``."""
    b0, b1, b2, b3, b4 = (int(max_hr * f) for f in EDWARDS_ZONE_LOWER_FRACTIONS)
    return b0, b1, b2, b3, b4
