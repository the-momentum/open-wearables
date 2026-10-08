"""Withings data API request definitions.

Withings is RPC-over-POST: the service path is one of a handful of endpoints and
the operation is named by an ``action`` field, so a request is the pair plus the
key its rows arrive under. ``data_fields`` is Withings' own opt-in parameter for
which measures a response should carry.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WithingsDataRequest:
    service_path: str
    action: str
    list_key: str
    data_fields: tuple[str, ...] = ()


MEASURES = WithingsDataRequest(
    service_path="/measure",
    action="getmeas",
    list_key="measuregrps",
)

ACTIVITY = WithingsDataRequest(
    service_path="/v2/measure",
    action="getactivity",
    list_key="activities",
    # Request persisted fields only; totalcalories derives passive calories.
    data_fields=(
        "steps",
        "distance",
        "calories",
        "totalcalories",
        "active",
    ),
)

# The high-frequency data the daily summaries above are built from. Its rows arrive
# under ``series`` as an object keyed by the start epoch of each slice, not as a list,
# so this request cannot go through ``paginate``.
INTRADAY_ACTIVITY = WithingsDataRequest(
    service_path="/v2/measure",
    action="getintradayactivity",
    list_key="series",
    # The same measures as the daily rows, so this adds granularity rather than metrics.
    data_fields=(
        "steps",
        "distance",
        "calories",
    ),
)

SLEEP_SUMMARY = WithingsDataRequest(
    service_path="/v2/sleep",
    action="getsummary",
    list_key="series",
    data_fields=(
        "total_timeinbed",
        "total_sleep_time",
        "asleepduration",
        "deepsleepduration",
        "lightsleepduration",
        "remsleepduration",
        "wakeupduration",
        "sleep_efficiency",
        "hr_min",
    ),
)

WORKOUTS = WithingsDataRequest(
    service_path="/v2/measure",
    action="getworkouts",
    list_key="series",
    data_fields=(
        "calories",
        "steps",
        "distance",
        "hr_average",
        "hr_min",
        "hr_max",
    ),
)

SLEEP_SERIES = WithingsDataRequest(
    service_path="/v2/sleep",
    action="get",
    list_key="series",
    data_fields=(
        "rmssd",
        "sdnn_1",
    ),
)
