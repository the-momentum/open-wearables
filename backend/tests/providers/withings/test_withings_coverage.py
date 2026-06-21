from app.schemas.enums import SeriesType
from app.services.providers.withings.coverage import DEFERRED_MEASURE_TYPES, MEASURE_TYPE_MAP, TIMESERIES


def test_getmeas_mapping_is_limited_to_core_semantic_matches() -> None:
    expected = {
        1: SeriesType.weight,
        4: SeriesType.height,
        5: SeriesType.lean_body_mass,
        6: SeriesType.body_fat_percentage,
        8: SeriesType.body_fat_mass,
        9: SeriesType.blood_pressure_diastolic,
        10: SeriesType.blood_pressure_systolic,
        11: SeriesType.heart_rate,
        12: SeriesType.body_temperature,
        54: SeriesType.oxygen_saturation,
        71: SeriesType.body_temperature,
        73: SeriesType.skin_temperature,
        76: SeriesType.skeletal_muscle_mass,
        119: SeriesType.blood_glucose,
        123: SeriesType.vo2_max,
        155: SeriesType.cardiovascular_age,
    }
    assert expected == MEASURE_TYPE_MAP


def test_deferred_getmeas_types_are_recorded_and_never_mapped() -> None:
    # The deferred registry documents the "parsed but not mapped" decision; a
    # type must never live in both it and the active map.
    assert DEFERRED_MEASURE_TYPES.keys().isdisjoint(MEASURE_TYPE_MAP)
    # The near-match traps that motivated the registry must stay deferred.
    assert {77, 88, 91, 130, 226, 227}.issubset(DEFERRED_MEASURE_TYPES)


def test_all_mapped_getmeas_series_are_declared_timeseries_coverage() -> None:
    assert set(MEASURE_TYPE_MAP.values()).issubset(TIMESERIES)
