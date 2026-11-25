"""
Provider-specific test fixtures.

These fixtures provide mock data and utilities for testing provider integrations.
"""

import time
from collections.abc import Generator

import pytest

from tests.providers.factories import OuraReadinessFactory, OuraSleepFactory, PolarExerciseFactory


@pytest.fixture
def non_utc_process_timezone(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Run the test with the process timezone on Europe/Warsaw rules (POSIX string, no tzdata needed)."""
    with monkeypatch.context() as mp:
        mp.setenv("TZ", "CET-1CEST,M3.5.0,M10.5.0/3")
        try:
            time.tzset()
            assert time.timezone == -3600, "process timezone did not switch away from UTC"
            yield
        finally:
            mp.undo()
            time.tzset()


@pytest.fixture
def sample_polar_exercise() -> dict:
    """Sample Polar exercise JSON data."""
    return PolarExerciseFactory.build_payload(
        id="ABC123",
        upload_time="2024-01-15T09:00:00.000Z",
        polar_user="https://www.polaraccesslink.com/v3/users/12345",
        device_id="12345678",
        calories=650,
        distance=10000,
        heart_rate={
            "average": 145,
            "maximum": 175,
        },
        training_load=150.0,
        has_route=True,
        detailed_sport_info="RUNNING",
    )


@pytest.fixture
def sample_oura_sleep() -> dict:
    """Sample Oura sleep JSON data."""
    return OuraSleepFactory.build_payload(
        id="sleep-abc123",
        average_breath=15.5,
        average_heart_rate=55.0,
        average_hrv=45,
        awake_time=1800,
        bedtime_start="2024-01-15T23:00:00+00:00",
        deep_sleep_duration=5400,
        efficiency=88,
        latency=300,
        light_sleep_duration=14400,
        low_battery_alert=False,
        lowest_heart_rate=48,
        period=0,
        rem_sleep_duration=7200,
        restless_periods=5,
        time_in_bed=28800,
        total_sleep_duration=27000,
        type="long_sleep",
    )


@pytest.fixture
def sample_oura_readiness() -> dict:
    """Sample Oura daily readiness JSON data."""
    return OuraReadinessFactory.build_payload(
        id="readiness-abc123",
        score=82,
        temperature_deviation=0.15,
        temperature_trend_deviation=0.05,
    )


@pytest.fixture
def sample_ultrahuman_api_response() -> dict:
    """Sample complete Ultrahuman /user_data/metrics API response.

    Based on the real API shape from the partner v1 /user_data/metrics endpoint.
    """
    return {
        "data": {
            "metric_data": [
                {
                    "type": "hr",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Heart Rate",
                        "values": [
                            {"value": 58, "timestamp": 1705276815},
                            {"value": 62, "timestamp": 1705277115},
                            {"value": 55, "timestamp": 1705277415},
                            {"value": 71, "timestamp": 1705277715},
                            {"value": 68, "timestamp": 1705278015},
                        ],
                        "last_reading": {"value": 68, "timestamp": 1705278015},
                        "unit": "bpm",
                    },
                },
                {
                    "type": "temp",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Skin Temperature",
                        "values": [
                            {"value": 36.2, "timestamp": 1705276815},
                            {"value": 36.4, "timestamp": 1705277115},
                            {"value": 36.3, "timestamp": 1705277415},
                            {"value": 36.5, "timestamp": 1705277715},
                        ],
                        "last_reading": {"value": 36.5, "timestamp": 1705277715},
                        "unit": "°C",
                    },
                },
                {
                    "type": "hrv",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "HRV",
                        "values": [
                            {"value": 42, "timestamp": 1705276815},
                            {"value": 51, "timestamp": 1705277115},
                            {"value": 47, "timestamp": 1705277415},
                        ],
                        "subtitle": "Average",
                        "avg": 47,
                        "trend_title": "Stable",
                        "trend_direction": "neutral",
                    },
                },
                {
                    "type": "steps",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "values": [
                            {"value": 0, "timestamp": 1705276815},
                            {"value": 120, "timestamp": 1705277115},
                            {"value": 85, "timestamp": 1705277415},
                            {"value": 200, "timestamp": 1705277715},
                        ],
                        "subtitle": "Average",
                        "total": 8452,
                        "avg": 6200,
                        "trend_title": "Increasing",
                        "trend_direction": "up",
                    },
                },
                {
                    "type": "night_rhr",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Resting HR",
                        "values": [
                            {"value": 52, "timestamp": 1705290000},
                            {"value": 50, "timestamp": 1705293600},
                            {"value": 51, "timestamp": 1705297200},
                        ],
                        "subtitle": "Sleep Time Average",
                        "avg": 51,
                        "trend_title": "Stable",
                        "trend_direction": "neutral",
                    },
                },
                {
                    "type": "temperature_deviation",
                    "object": {
                        "day_start_timestamp": 1705276800,
                        "title": "Temperature Deviation",
                        "value": -0.2,
                        "unit": "°C",
                    },
                },
                {
                    "type": "sleep_rhr",
                    "object": {
                        "value": 51,
                        "day_start_timestamp": 1705276800,
                    },
                },
                {
                    "type": "avg_sleep_hrv",
                    "object": {
                        "value": 48,
                        "day_start_timestamp": 1705276800,
                    },
                },
                {
                    "type": "Sleep",
                    "object": {
                        "bedtime_start": 1705287600,
                        "bedtime_end": 1705314000,
                        "quick_metrics": [
                            {
                                "title": "TIME IN BED",
                                "display_text": "7h 20m",
                                "unit": None,
                                "value": 26400,
                                "type": "time_in_bed",
                            },
                            {
                                "title": "TOTAL SLEEP",
                                "display_text": "6h 48m",
                                "value": 24480,
                                "type": "total_sleep",
                            },
                            {
                                "title": "EFFICIENCY",
                                "display_text": "91%",
                                "value": 91,
                                "type": "sleep_efic",
                            },
                            {
                                "title": "AVG HEART RATE",
                                "display_text": "52",
                                "unit": "bpm",
                                "value": 52,
                                "type": "avg_hr",
                            },
                            {
                                "title": "AVG HRV",
                                "display_text": "48",
                                "value": 48,
                                "type": "avg_hrv",
                            },
                        ],
                        "quick_metrics_tiled": [
                            {
                                "title": "TOTAL SLEEP",
                                "value": "6<b><small>h</small></b> 48<b><small>m</small></b>",
                                "tag": "Optimal",
                                "tag_color": "00B984",
                                "type": "total_sleep",
                            },
                        ],
                        "sleep_stages": [
                            {
                                "title": "Deep Sleep",
                                "type": "deep_sleep",
                                "percentage": 18,
                                "stage_time_text": "1h 18m \u2022 18%",
                                "stage_time": 4680,
                            },
                            {
                                "title": "Light Sleep",
                                "type": "light_sleep",
                                "percentage": 44,
                                "stage_time_text": "3h 12m \u2022 44%",
                                "stage_time": 11520,
                            },
                            {
                                "title": "REM Sleep",
                                "type": "rem_sleep",
                                "percentage": 30,
                                "stage_time_text": "2h 10m \u2022 30%",
                                "stage_time": 7800,
                            },
                            {
                                "title": "Awake",
                                "type": "awake",
                                "percentage": 8,
                                "stage_time_text": "35m \u2022 8%",
                                "stage_time": 2100,
                            },
                        ],
                        "sleep_graph": {
                            "title": "Time In Bed",
                            "data": [
                                {"start": 1705287600, "end": 1705288200, "type": "awake"},
                                {"start": 1705288200, "end": 1705291800, "type": "light_sleep"},
                                {"start": 1705291800, "end": 1705295400, "type": "deep_sleep"},
                                {"start": 1705295400, "end": 1705299000, "type": "rem_sleep"},
                                {"start": 1705299000, "end": 1705314000, "type": "light_sleep"},
                            ],
                        },
                        "movement_graph": [],
                        "hr_graph": [],
                        "hrv_graph": [],
                        "temp_graph": [],
                        "respiratory_graph": [],
                        "summary": [
                            {"title": "Sleep Efficiency", "state": "optimal", "state_title": "Optimal", "score": 88},
                            {"title": "Temperature", "state": "optimal", "state_title": "Optimal", "score": 92},
                        ],
                        "spo2": {"title": "Average Oxygen Saturation", "value": 97, "is_beta": True},
                        "toss_turn": {"title": "Toss & Turn", "value": 12},
                        "sleep_cycles": {
                            "title": "Sleep Cycles \u2022 5",
                            "legend": [
                                {"title": "3 Full", "color": "#008A46"},
                                {"title": "2 Partial", "color": "#004223"},
                            ],
                            "cycles": [
                                {"startTime": 1705287600, "endTime": 1705291200, "cycleType": "full"},
                                {"startTime": 1705291200, "endTime": 1705294800, "cycleType": "full"},
                                {"startTime": 1705294800, "endTime": 1705298400, "cycleType": "partial"},
                            ],
                        },
                        "tags_section": {},
                    },
                },
                {
                    "type": "recovery_index",
                    "object": {"value": 78, "title": "Recovery Index", "day_start_timestamp": 1705276800},
                },
                {
                    "type": "movement_index",
                    "object": {"value": 65, "title": "Movement Index", "day_start_timestamp": 1705276800},
                },
                {
                    "type": "active_minutes",
                    "object": {"title": "Active Minutes", "day_start_timestamp": 1705276800, "value": 35},
                },
                {
                    "type": "inactive_time",
                    "object": {"title": "Inactive Time", "day_start_timestamp": 1705276800, "value": 210.0},
                },
                {
                    "type": "weekly_active_minutes",
                    "object": {"title": "Weekly Active Minutes", "day_start_timestamp": 1705276800, "value": 150},
                },
                {
                    "type": "vo2_max",
                    "object": {"value": 42.5, "title": "VO2 Max", "day_start_timestamp": 1705276800},
                },
                {
                    "type": "sleep_rhr",
                    "object": {"value": 51, "day_start_timestamp": 1705276800},
                },
                {
                    "type": "movements",
                    "object": {"title": "Movements", "day_start_timestamp": 1705276800, "value": 3200},
                },
                {
                    "type": "morning_alertness",
                    "object": {
                        "title": "Morning Alertness",
                        "day_start_timestamp": 1705276800,
                        "value": 7,
                        "unit": "/10",
                        "status": "Good",
                    },
                },
                {
                    "type": "metabolic_score",
                    "object": {"day_start_timestamp": 1705276800, "title": "Metabolic Score", "value": None},
                },
            ]
        },
    }
