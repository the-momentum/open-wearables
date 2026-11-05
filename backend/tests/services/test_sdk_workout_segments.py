"""Tests for normalising mobile-SDK workout laps and segments into `workout_details.segments`."""

from typing import Any

from app.schemas.providers.mobile_sdk.sync_request import Workout
from app.services.sdk.workout_segments import build_workout_segments


def _workout(**fields: Any) -> Workout:
    return Workout.model_validate(
        {"type": "swimming", "startDate": "2026-09-01T06:00:00Z", "endDate": "2026-09-01T07:00:00Z", **fields}
    )


def _at(start: str, end: str, **fields: Any) -> dict[str, Any]:
    return {"startDate": f"2026-09-01T{start}Z", "endDate": f"2026-09-01T{end}Z", **fields}


class TestPoolSwimLengths:
    def test_typed_lap_fields_become_a_length(self) -> None:
        workout = _workout(
            laps=[
                {
                    "type": "lap",
                    "startDate": "2026-09-01T06:01:00Z",
                    "endDate": "2026-09-01T06:01:58.8Z",
                    "distanceM": 50,
                    "strokeStyle": "freestyle",
                    "strokeCount": 23,
                    "swolf": 82,
                }
            ]
        )

        assert build_workout_segments(workout) == [
            {
                "kind": "length",
                "index": 0,
                "start_time": "2026-09-01T06:01:00+00:00",
                "elapsed_seconds": 58.8,
                "swim_stroke": "freestyle",
                "total_strokes": 23,
                "swolf": 82,
                "avg_speed": 0.85,
                "length_type": "active",
            }
        ]

    def test_stringified_healthkit_metadata_is_read_from_older_sdks(self) -> None:
        workout = _workout(
            laps=[
                {
                    "type": "lap",
                    "startDate": "2026-09-01T06:01:00Z",
                    "endDate": "2026-09-01T06:02:00Z",
                    "duration": 60,
                    "distanceM": 50,
                    "metadata": {"HKSwimmingStrokeStyle": "4", "HKSWOLFScore": "88 count", "HKLapLength": "50 m"},
                }
            ]
        )

        [length] = build_workout_segments(workout) or []

        assert length["kind"] == "length"
        assert length["swim_stroke"] == "breaststroke"
        assert length["swolf"] == 88
        assert "total_strokes" not in length

    def test_kickboard_maps_to_drill(self) -> None:
        workout = _workout(
            laps=[
                {"startDate": "2026-09-01T06:01:00Z", "endDate": "2026-09-01T06:02:00Z", "strokeStyle": "kickboard"},
                {
                    "startDate": "2026-09-01T06:03:00Z",
                    "endDate": "2026-09-01T06:04:00Z",
                    "metadata": {"HKSwimmingStrokeStyle": "6"},
                },
            ]
        )

        assert [s["swim_stroke"] for s in build_workout_segments(workout) or []] == ["drill", "drill"]

    def test_unknown_stroke_without_swolf_is_a_plain_lap(self) -> None:
        workout = _workout(
            laps=[
                {
                    "startDate": "2026-09-01T06:01:00Z",
                    "endDate": "2026-09-01T06:02:00Z",
                    "metadata": {"HKSwimmingStrokeStyle": "0"},
                }
            ]
        )

        [lap] = build_workout_segments(workout) or []

        assert lap["kind"] == "lap"
        assert "swim_stroke" not in lap


class TestLapsAndSplits:
    def test_running_laps_and_segment_events(self) -> None:
        workout = _workout(
            type="running",
            laps=[
                _at("06:05:00", "06:10:00", type="lap", distanceM=1000),
                _at("06:07:00", "06:07:00", type="marker"),
                _at("06:00:00", "06:10:00", type="segment"),
                _at("06:00:00", "06:05:00", type="lap", distanceM=1000),
            ],
        )

        segments = build_workout_segments(workout) or []

        assert [(s["kind"], s["index"]) for s in segments] == [("split", 0), ("lap", 0), ("lap", 1)]
        assert segments[1] == {
            "kind": "lap",
            "index": 0,
            "start_time": "2026-09-01T06:00:00+00:00",
            "elapsed_seconds": 300,
            "distance_meters": 1000,
            "avg_speed": 3.33,
        }
        assert segments[0]["split_type"] == "segment"

    def test_health_connect_exercise_segments_become_splits(self) -> None:
        workout = _workout(
            type="STRENGTH_TRAINING",
            segments=[
                _at("06:00:00", "06:01:00", type="squat", repetitions=12),
                _at("06:01:00", "06:03:00", type="rest"),
            ],
        )

        assert build_workout_segments(workout) == [
            {
                "kind": "split",
                "index": 0,
                "start_time": "2026-09-01T06:00:00+00:00",
                "elapsed_seconds": 60,
                "split_type": "squat",
                "repetitions": 12,
            },
            {
                "kind": "split",
                "index": 1,
                "start_time": "2026-09-01T06:01:00+00:00",
                "elapsed_seconds": 120,
                "split_type": "rest",
            },
        ]

    def test_no_laps_or_segments_returns_none(self) -> None:
        assert build_workout_segments(_workout(laps=None, segments=None)) is None
        assert build_workout_segments(_workout(laps=[_at("06:00:00", "06:00:00", type="marker")])) is None


class TestTolerance:
    def test_malformed_lap_is_skipped_and_the_workout_kept(self) -> None:
        workout = _workout(laps=[{"type": "lap", "startDate": "not-a-date"}, _at("06:00:00", "06:01:00", type="lap")])

        assert [s["kind"] for s in build_workout_segments(workout) or []] == ["lap"]

    def test_naive_and_offset_aware_timestamps_sort_together(self) -> None:
        workout = _workout(
            laps=[{"type": "lap", "startDate": "2026-09-01T06:05:00", "endDate": "2026-09-01T06:06:00"}],
            segments=[_at("06:00:00", "06:05:00", type="running")],
        )

        segments = build_workout_segments(workout) or []

        assert [s["kind"] for s in segments] == ["split", "lap"]
        assert segments[1]["start_time"] == "2026-09-01T06:05:00+00:00"

    def test_lap_with_one_naive_date_keeps_its_elapsed_time(self) -> None:
        workout = _workout(
            laps=[{"type": "lap", "startDate": "2026-09-01T06:00:00", "endDate": "2026-09-01T06:01:00Z"}]
        )

        [lap] = build_workout_segments(workout) or []

        assert lap["elapsed_seconds"] == 60
