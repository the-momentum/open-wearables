"""Tests for RunKeeper CSV parser."""

from datetime import datetime, timezone

from app.schemas.enums.workout_types import WorkoutType
from app.services.csv_import.runkeeper import parse_runkeeper_csv

SAMPLE_CSV = (
    "Activity Id,Date,Type,Route Name,Distance (km),Duration,"
    "Average Pace,Average Speed (km/h),Calories Burned,Climb (m),"
    "Average Heart Rate (bpm),Friend's Tagged,Notes,GPX File\n"
    'b2a1df07-c209-44bb-a44c-9250251634e3,2026-03-28 08:33:29,Running,,3.24,26:11,8:06,7.41,245.0,59,106,"","",\n'
    '4ae694e5-53aa-4c1b-9189-50a401286540,2026-03-25 17:53:26,Running,,3.42,24:50,7:16,8.26,260.0,54,135,"","",\n'
    "e50767a5-d555-4799-92de-91c05c031ee9,2026-03-23 08:25:40,Cycling,,"
    '15.5,45:30,2:56,20.44,320.0,120,142,"","Morning ride",\n'
    '7300dc38-e94b-47a7-95b9-af961dcf3b20,2026-03-21 09:35:15,Walking,,4.24,40:45,9:36,6.25,278.0,51,,"","",\n'
    'abc123,2026-01-15 14:00:00,Swimming,,1.0,1:02:30,62:30,0.96,400.0,,,"","Pool session",\n'
)


def test_parse_runkeeper_csv_count() -> None:
    workouts = parse_runkeeper_csv(SAMPLE_CSV)
    assert len(workouts) == 5


def test_parse_running_workout() -> None:
    workouts = parse_runkeeper_csv(SAMPLE_CSV)
    w = workouts[0]
    assert w["external_id"] == "b2a1df07-c209-44bb-a44c-9250251634e3"
    assert w["workout_type"] == WorkoutType.RUNNING
    assert w["start_datetime"] == datetime(2026, 3, 28, 8, 33, 29, tzinfo=timezone.utc)
    assert w["duration_seconds"] == 26 * 60 + 11
    assert w["distance_meters"] == 3240.0
    assert w["calories"] == 245.0
    assert w["climb_meters"] == 59.0
    assert w["avg_heart_rate"] == 106
    assert w["avg_speed_kmh"] == 7.41


def test_parse_cycling_workout() -> None:
    workouts = parse_runkeeper_csv(SAMPLE_CSV)
    w = workouts[2]
    assert w["workout_type"] == WorkoutType.CYCLING
    assert w["distance_meters"] == 15500.0
    assert w["notes"] == "Morning ride"


def test_parse_missing_heart_rate() -> None:
    workouts = parse_runkeeper_csv(SAMPLE_CSV)
    w = workouts[3]  # Walking, no HR
    assert w["avg_heart_rate"] is None


def test_parse_long_duration() -> None:
    workouts = parse_runkeeper_csv(SAMPLE_CSV)
    w = workouts[4]  # Swimming, 1:02:30
    assert w["duration_seconds"] == 3750
    assert w["workout_type"] == WorkoutType.SWIMMING


def test_end_datetime_calculated() -> None:
    from datetime import timedelta

    workouts = parse_runkeeper_csv(SAMPLE_CSV)
    w = workouts[0]
    expected_end = datetime(2026, 3, 28, 8, 33, 29, tzinfo=timezone.utc) + timedelta(seconds=26 * 60 + 11)
    assert w["end_datetime"] == expected_end


def test_parse_bytes_input() -> None:
    workouts = parse_runkeeper_csv(SAMPLE_CSV.encode("utf-8"))
    assert len(workouts) == 5


def test_parse_empty_csv() -> None:
    header = (
        "Activity Id,Date,Type,Route Name,Distance (km),Duration,"
        "Average Pace,Average Speed (km/h),Calories Burned,Climb (m),"
        "Average Heart Rate (bpm),Friend's Tagged,Notes,GPX File\n"
    )
    workouts = parse_runkeeper_csv(header)
    assert len(workouts) == 0
