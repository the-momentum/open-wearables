import math
from datetime import datetime
from typing import NamedTuple


class ScoreBounds(NamedTuple):
    min: int
    max: int


def time_to_hours_past_noon(dt: datetime) -> float:
    """Convert a datetime to continuous hours past noon to handle the midnight boundary."""
    hours = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    if hours < 12.0:
        hours += 24.0
    return hours - 12.0


def score_sigmoid(x: float, k: float, base: float, midpoint: float, anchor: float) -> float:
    """Scaled sigmoid that equals base exactly at anchor.

    Pass a negative k for a rising curve (under-sleeping) and a positive k for
    a falling curve (over-sleeping).
    """
    return base * (1 + math.exp(k * (anchor - midpoint))) / (1 + math.exp(k * (x - midpoint)))
