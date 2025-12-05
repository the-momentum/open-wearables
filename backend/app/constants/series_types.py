from app.schemas.time_series import SeriesType

# Stable integer identifiers for each series type. These IDs are persisted in the database,
# so update with caution.
SERIES_TYPE_DEFINITIONS: list[tuple[int, SeriesType, str]] = [
    (1, SeriesType.steps, "count"),
    (2, SeriesType.heart_rate, "bpm"),
    (3, SeriesType.energy, "kcal"),
    (4, SeriesType.height, "cm"),
    (5, SeriesType.weight, "kg"),
    (6, SeriesType.body_fat_percentage, "percent"),
    (7, SeriesType.resting_heart_rate, "bpm"),
    (8, SeriesType.body_temperature, "celsius"),
    (9, SeriesType.distance_walking_running, "meters"),
    (10, SeriesType.distance_cycling, "meters"),
    (11, SeriesType.respiratory_rate, "breaths_per_minute"),
    (12, SeriesType.walking_heart_rate_average, "bpm"),
    (13, SeriesType.heart_rate_variability_sdnn, "ms"),
    (14, SeriesType.oxygen_saturation, "percent"),
]

SERIES_TYPE_ID_BY_ENUM: dict[SeriesType, int] = {enum: type_id for type_id, enum, _ in SERIES_TYPE_DEFINITIONS}
SERIES_TYPE_ENUM_BY_ID: dict[int, SeriesType] = {type_id: enum for type_id, enum, _ in SERIES_TYPE_DEFINITIONS}
SERIES_TYPE_UNIT_BY_ENUM: dict[SeriesType, str] = {enum: unit for _, enum, unit in SERIES_TYPE_DEFINITIONS}


def get_series_type_id(series_type: SeriesType) -> int:
    return SERIES_TYPE_ID_BY_ENUM[series_type]


def get_series_type_from_id(series_type_id: int) -> SeriesType:
    return SERIES_TYPE_ENUM_BY_ID[series_type_id]

