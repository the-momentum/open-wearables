"""Unit tests for HevyWorkouts: normalization, events pagination, deletes, 401 handling."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.schemas.auth import ConnectionStatus
from app.schemas.enums import WorkoutType
from app.services.providers.base_strategy import IncompleteSyncError
from app.services.providers.hevy.workouts import HevyWorkouts

API_BASE = "https://api.hevyapp.com"


def _workout_payload(**overrides) -> dict:
    payload = {
        "id": "b459cba5-cd6d-463c-abd6-54f8eafcadcb",
        "title": "Push Day",
        "description": None,
        "start_time": "2026-08-01T12:00:00Z",
        "end_time": "2026-08-01T13:10:00Z",
        "updated_at": "2026-08-01T13:11:00Z",
        "exercises": [
            {
                "index": 0,
                "title": "Bench Press (Barbell)",
                "exercise_template_id": "79D0BB3A",
                "sets": [
                    {"index": 0, "type": "warmup", "weight_kg": 60, "reps": 10},
                    {"index": 1, "type": "normal", "weight_kg": 100, "reps": 5, "rpe": 8.5},
                ],
            },
            {
                "index": 1,
                "title": "Treadmill",
                "sets": [{"index": 0, "type": "normal", "distance_meters": 1000, "duration_seconds": 360}],
            },
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def workouts() -> HevyWorkouts:
    return HevyWorkouts(
        workout_repo=MagicMock(),
        connection_repo=MagicMock(),
        provider_name="hevy",
        api_base_url=API_BASE,
        oauth=None,  # type: ignore[arg-type]
    )


@pytest.fixture
def active_connection() -> MagicMock:
    conn = MagicMock()
    conn.status = ConnectionStatus.ACTIVE
    conn.access_token = "11111111-2222-3333-4444-555555555555"
    return conn


class TestNormalizeWorkout:
    def test_full_workout(self, workouts: HevyWorkouts) -> None:
        user_id = uuid4()
        record, detail = workouts._normalize_workout(_workout_payload(), user_id)

        assert record.category == "workout"
        assert record.type == WorkoutType.STRENGTH_TRAINING.value
        assert record.source == "hevy"
        assert record.source_name == "Hevy"
        assert record.external_id == "b459cba5-cd6d-463c-abd6-54f8eafcadcb"
        assert record.user_id == user_id
        assert record.duration_seconds == 70 * 60
        assert record.start_datetime == datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)

        assert detail.record_id == record.id
        # distance aggregated from the treadmill set
        assert detail.distance == Decimal("1000")
        # exercises preserved losslessly in segments
        assert detail.segments is not None
        assert len(detail.segments) == 2
        assert detail.segments[0]["title"] == "Bench Press (Barbell)"
        assert detail.segments[0]["sets"][1]["weight_kg"] == 100.0

    def test_no_cardio_sets_means_no_distance(self, workouts: HevyWorkouts) -> None:
        payload = _workout_payload()
        payload["exercises"] = payload["exercises"][:1]  # bench press only
        _, detail = workouts._normalize_workout(payload, uuid4())
        assert detail.distance is None

    def test_title_keyword_changes_type(self, workouts: HevyWorkouts) -> None:
        record, _ = workouts._normalize_workout(_workout_payload(title="Morning Run"), uuid4())
        assert record.type == WorkoutType.RUNNING.value


class TestGetWorkoutEvents:
    def _response(self, page: int, page_count: int, events: list) -> dict:
        return {"page": page, "page_count": page_count, "events": events}

    def test_splits_updated_and_deleted_across_pages(self, workouts: HevyWorkouts) -> None:
        pages = [
            self._response(1, 2, [{"type": "updated", "workout": _workout_payload()}]),
            self._response(2, 2, [{"type": "deleted", "id": "gone-1", "deleted_at": "2026-08-02T00:00:00Z"}]),
        ]
        with patch.object(workouts, "_make_api_request", side_effect=pages) as mock_request:
            updated, deleted = workouts.get_workout_events(
                MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc)
            )
        assert len(updated) == 1
        assert deleted == ["gone-1"]
        assert mock_request.call_count == 2
        # since is passed as ISO with Z suffix
        params = mock_request.call_args_list[0].kwargs["params"]
        assert params["since"] == "2026-08-01T00:00:00Z"

    def test_a_later_page_failure_fails_the_whole_fetch(self, workouts: HevyWorkouts) -> None:
        """Returning page 1 alone would let the caller advance its cursor past page 2."""
        pages = [
            self._response(1, 3, [{"type": "updated", "workout": _workout_payload()}]),
            RuntimeError("boom"),
        ]
        with (
            patch.object(workouts, "_make_api_request", side_effect=pages),
            pytest.raises(IncompleteSyncError, match="page 2"),
        ):
            workouts.get_workout_events(MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc))

    def test_error_on_first_page_raises(self, workouts: HevyWorkouts) -> None:
        with (
            patch.object(workouts, "_make_api_request", side_effect=RuntimeError("boom")),
            pytest.raises(IncompleteSyncError),
        ):
            workouts.get_workout_events(MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc))

    @pytest.mark.parametrize(
        "garbled",
        [
            {"page": 2, "page_count": "two", "events": []},
            {"page": 2, "page_count": 2.5, "events": []},
            {"page": 2, "page_count": 3, "events": "nope"},
            {"page": 2, "page_count": 3, "events": ["not-an-object"]},
            ["not", "an", "object"],
        ],
    )
    def test_a_garbled_page_fails_the_whole_fetch(self, workouts: HevyWorkouts, garbled: object) -> None:
        """A page that cannot be read must hold the cursor like a failed request, not read as empty."""
        pages = [self._response(1, 3, [{"type": "updated", "workout": _workout_payload()}]), garbled]
        with (
            patch.object(workouts, "_make_api_request", side_effect=pages),
            pytest.raises(IncompleteSyncError, match="page 2"),
        ):
            workouts.get_workout_events(MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc))

    def test_a_garbled_page_fails_load_data(self, workouts: HevyWorkouts) -> None:
        with (
            patch.object(workouts, "_make_api_request", return_value={"page_count": "x", "events": []}),
            pytest.raises(IncompleteSyncError),
        ):
            workouts.load_data(MagicMock(), uuid4(), start="2026-08-01T00:00:00Z")

    def test_lenient_where_the_feed_is_unambiguous(self, workouts: HevyWorkouts) -> None:
        """A numeric-string page_count is read, and an empty or missing events list just ends paging."""
        pages = [
            {"page": 1, "page_count": "2", "events": [{"type": "updated", "workout": _workout_payload()}]},
            {"page": 2},
        ]
        with patch.object(workouts, "_make_api_request", side_effect=pages) as mock_request:
            updated, deleted = workouts.get_workout_events(
                MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc)
            )
        assert len(updated) == 1
        assert deleted == []
        assert mock_request.call_count == 2


def _updated(workout_id: str, updated_at: str, title: str = "Push Day") -> dict:
    return {"type": "updated", "workout": _workout_payload(id=workout_id, updated_at=updated_at, title=title)}


def _deleted(workout_id: str, deleted_at: str) -> dict:
    return {"type": "deleted", "id": workout_id, "deleted_at": deleted_at}


class TestLatestEventPerWorkout:
    """The feed is newest first; only the newest event per workout may be applied."""

    def _fetch(self, workouts: HevyWorkouts, events: list[dict]) -> tuple[list[dict], list[str]]:
        page = {"page": 1, "page_count": 1, "events": events}
        with patch.object(workouts, "_make_api_request", return_value=page):
            return workouts.get_workout_events(MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc))

    def test_older_delete_does_not_remove_a_newer_update(self, workouts: HevyWorkouts) -> None:
        updated, deleted = self._fetch(
            workouts,
            [_updated("w1", "2026-08-03T10:00:00Z"), _deleted("w1", "2026-08-02T10:00:00Z")],
        )
        assert [w["id"] for w in updated] == ["w1"]
        assert deleted == []

    def test_newer_delete_wins_over_an_older_update(self, workouts: HevyWorkouts) -> None:
        updated, deleted = self._fetch(
            workouts,
            [_deleted("w1", "2026-08-03T10:00:00Z"), _updated("w1", "2026-08-02T10:00:00Z")],
        )
        assert updated == []
        assert deleted == ["w1"]

    def test_only_the_newest_update_is_kept(self, workouts: HevyWorkouts) -> None:
        updated, _ = self._fetch(
            workouts,
            [
                _updated("w1", "2026-08-03T10:00:00Z", title="Newest"),
                _updated("w1", "2026-08-02T10:00:00Z", title="Older"),
                _updated("w2", "2026-08-01T10:00:00Z", title="Other"),
            ],
        )
        assert sorted((w["id"], w["title"]) for w in updated) == [("w1", "Newest"), ("w2", "Other")]

    def test_timestamps_beat_feed_order(self, workouts: HevyWorkouts) -> None:
        # Should the feed ever come oldest first, the timestamps still decide.
        updated, deleted = self._fetch(
            workouts,
            [_deleted("w1", "2026-08-02T10:00:00Z"), _updated("w1", "2026-08-03T10:00:00Z", title="Newest")],
        )
        assert [w["title"] for w in updated] == ["Newest"]
        assert deleted == []

    def test_events_across_pages_are_collapsed(self, workouts: HevyWorkouts) -> None:
        pages = [
            {"page": 1, "page_count": 2, "events": [_updated("w1", "2026-08-03T10:00:00Z")]},
            {"page": 2, "page_count": 2, "events": [_deleted("w1", "2026-08-02T10:00:00Z")]},
        ]
        with patch.object(workouts, "_make_api_request", side_effect=pages):
            updated, deleted = workouts.get_workout_events(
                MagicMock(), uuid4(), since=datetime(2026, 8, 1, tzinfo=timezone.utc)
            )
        assert [w["id"] for w in updated] == ["w1"]
        assert deleted == []


class TestLoadData:
    def test_upserts_and_deletes(self, workouts: HevyWorkouts) -> None:
        user_id = uuid4()
        with (
            patch.object(
                workouts,
                "get_workout_events",
                return_value=([_workout_payload()], ["deleted-ext-id"]),
            ),
            patch.object(workouts, "_stored_workouts", return_value=[]),
            patch("app.services.providers.hevy.workouts.event_record_service") as mock_service,
        ):
            mock_service.create.return_value = MagicMock(id=uuid4())
            count = workouts.load_data(MagicMock(), user_id, start_date="2026-08-01T00:00:00Z")

        assert count == 1
        mock_service.create.assert_called_once()
        mock_service.create_detail.assert_called_once()
        workouts.workout_repo.delete_by_external_id.assert_called_once()
        _, kwargs = workouts.workout_repo.delete_by_external_id.call_args
        args, _ = workouts.workout_repo.delete_by_external_id.call_args
        assert "deleted-ext-id" in args or kwargs.get("external_id") == "deleted-ext-id"

    def test_malformed_workout_is_skipped(self, workouts: HevyWorkouts) -> None:
        bad = {"id": "x"}  # missing required start/end times
        with (
            patch.object(workouts, "get_workout_events", return_value=([bad], [])),
            patch("app.services.providers.hevy.workouts.event_record_service") as mock_service,
        ):
            count = workouts.load_data(MagicMock(), uuid4(), start_date="2026-08-01T00:00:00Z")
        assert count == 0
        mock_service.create.assert_not_called()

    def test_a_write_failure_fails_the_sync(self, workouts: HevyWorkouts) -> None:
        db = MagicMock()
        with (
            patch.object(workouts, "get_workout_events", return_value=([_workout_payload()], [])),
            patch.object(workouts, "_stored_workouts", return_value=[]),
            patch("app.services.providers.hevy.workouts.event_record_service") as mock_service,
        ):
            mock_service.create.side_effect = RuntimeError("db down")
            with pytest.raises(IncompleteSyncError, match="db down"):
                workouts.load_data(db, uuid4(), start_date="2026-08-01T00:00:00Z")
        db.rollback.assert_called_once()


class TestApiKeyAuth:
    def test_request_sends_api_key_header(self, workouts: HevyWorkouts, active_connection: MagicMock) -> None:
        workouts.connection_repo.get_by_user_and_provider.return_value = active_connection
        response = MagicMock(status_code=200)
        response.json.return_value = {"ok": True}
        with patch("app.services.providers.hevy.workouts.httpx.request", return_value=response) as mock_httpx:
            result = workouts._make_api_request(MagicMock(), uuid4(), "/v1/workouts")
        assert result == {"ok": True}
        headers = mock_httpx.call_args.kwargs["headers"]
        assert headers["api-key"] == active_connection.access_token

    def test_401_marks_connection_revoked(self, workouts: HevyWorkouts, active_connection: MagicMock) -> None:
        workouts.connection_repo.get_by_user_and_provider.return_value = active_connection
        response = MagicMock(status_code=401)
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=MagicMock(), response=MagicMock(status_code=401)
        )
        with (
            patch("app.services.providers.hevy.workouts.httpx.request", return_value=response),
            pytest.raises(httpx.HTTPStatusError),
        ):
            workouts._make_api_request(MagicMock(), uuid4(), "/v1/workouts")
        workouts.connection_repo.mark_as_revoked.assert_called_once()

    def test_no_active_connection_raises(self, workouts: HevyWorkouts) -> None:
        workouts.connection_repo.get_by_user_and_provider.return_value = None
        with pytest.raises(ValueError, match="No active Hevy connection"):
            workouts._make_api_request(MagicMock(), uuid4(), "/v1/workouts")
