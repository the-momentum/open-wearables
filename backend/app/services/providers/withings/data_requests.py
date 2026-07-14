"""Withings data API request definitions shared by ingestion services."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WithingsDataRequest:
    """Static contract for one Withings data API request."""

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
    data_fields=(
        "steps",
        "distance",
        "elevation",
        "calories",
        "totalcalories",
        "soft",
        "moderate",
        "intense",
        "hr_average",
        "hr_min",
        "hr_max",
    ),
)

SLEEP_SUMMARY = WithingsDataRequest(
    service_path="/v2/sleep",
    action="getsummary",
    list_key="series",
    data_fields=(
        "deepsleepduration",
        "lightsleepduration",
        "remsleepduration",
        "wakeupduration",
        "sleep_efficiency",
        "sleep_score",
        "hr_average",
        "rr_average",
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
        "elevation",
    ),
)
