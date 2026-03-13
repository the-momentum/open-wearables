"""
Tests for Apple HealthKit sleep service processing.

Tests the sleep pipeline (handle_sleep_data, _apply_transition, _calculate_final_metrics,
finish_sleep) using synthetic payloads modeled after real Apple HealthKit SDK data.

Apple Watch sleep data patterns:
- Older Apple Watch (pre-watchOS 9): only "in_bed" and "sleeping" stages
- Newer Apple Watch (watchOS 9+): "in_bed", "awake", "light", "deep", "rem" stages
"""

from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.constants.sleep import SleepStageType
from app.schemas.apple.healthkit.sleep_state import SleepState, SleepStateStage
from app.schemas.apple.healthkit.sync_request import SyncRequest
from app.services.apple.healthkit.sleep_service import (
    _calculate_final_metrics,
    finish_sleep,
    handle_sleep_data,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Synthetic payload: older Apple Watch (pre-watchOS 9) with sleeping + in_bed
# Mimics pattern: Watch sends "sleeping" segments, iPhone sends "in_bed"
# ---------------------------------------------------------------------------
OLD_WATCH_PAYLOAD = {
    "provider": "apple",
    "sdkVersion": "0.5.0",
    "syncTimestamp": "2026-03-11T13:28:04Z",
    "data": {
        "records": [],
        "workouts": [],
        "sleep": [
            {
                "id": "aaaa1111-0000-0000-0000-000000000001",
                "parentId": None,
                "stage": "sleeping",
                "startDate": "2026-03-10T23:00:00Z",
                "endDate": "2026-03-10T23:50:00Z",
                "source": {
                    "device_type": "watch",
                    "device_model": "Watch3,3",
                },
            },
            {
                "id": "aaaa1111-0000-0000-0000-000000000002",
                "parentId": None,
                "stage": "sleeping",
                "startDate": "2026-03-10T23:52:00Z",
                "endDate": "2026-03-11T00:45:00Z",
                "source": {
                    "device_type": "watch",
                    "device_model": "Watch3,3",
                },
            },
            {
                "id": "aaaa1111-0000-0000-0000-000000000003",
                "parentId": None,
                "stage": "sleeping",
                "startDate": "2026-03-11T00:47:00Z",
                "endDate": "2026-03-11T01:30:00Z",
                "source": {
                    "device_type": "watch",
                    "device_model": "Watch3,3",
                },
            },
            {
                "id": "aaaa1111-0000-0000-0000-000000000004",
                "parentId": None,
                "stage": "in_bed",
                "startDate": "2026-03-10T22:55:00Z",
                "endDate": "2026-03-11T01:35:00Z",
                "source": {
                    "device_type": "phone",
                    "device_model": "iPhone15,2",
                },
            },
        ],
    },
}

# ---------------------------------------------------------------------------
# Synthetic payload: detailed stages (watchOS 9+ style)
# ---------------------------------------------------------------------------
DETAILED_STAGES_PAYLOAD = {
    "provider": "apple",
    "sdkVersion": "1.0.0",
    "syncTimestamp": "2026-03-11T13:28:04Z",
    "data": {
        "records": [],
        "workouts": [],
        "sleep": [
            {
                "id": "A001",
                "stage": "in_bed",
                "startDate": "2026-03-10T22:00:00Z",
                "endDate": "2026-03-11T06:00:00Z",
                "source": {"device_type": "phone", "device_model": "iPhone15,2"},
            },
            {
                "id": "A002",
                "stage": "light",
                "startDate": "2026-03-10T22:15:00Z",
                "endDate": "2026-03-10T23:00:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A003",
                "stage": "deep",
                "startDate": "2026-03-10T23:00:00Z",
                "endDate": "2026-03-11T00:30:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A004",
                "stage": "rem",
                "startDate": "2026-03-11T00:30:00Z",
                "endDate": "2026-03-11T01:15:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A005",
                "stage": "awake",
                "startDate": "2026-03-11T01:15:00Z",
                "endDate": "2026-03-11T01:25:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A006",
                "stage": "deep",
                "startDate": "2026-03-11T01:25:00Z",
                "endDate": "2026-03-11T02:30:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A007",
                "stage": "light",
                "startDate": "2026-03-11T02:30:00Z",
                "endDate": "2026-03-11T04:00:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A008",
                "stage": "rem",
                "startDate": "2026-03-11T04:00:00Z",
                "endDate": "2026-03-11T05:00:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
            {
                "id": "A009",
                "stage": "light",
                "startDate": "2026-03-11T05:00:00Z",
                "endDate": "2026-03-11T05:45:00Z",
                "source": {"device_type": "watch", "device_model": "Watch7,1"},
            },
        ],
    },
}


class TestCalculateFinalMetrics:
    """Tests for _calculate_final_metrics with different stage combinations."""

    def test_sleeping_stages_only(self) -> None:
        """Older Apple Watch data: only 'sleeping' stages should NOT map to deep."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-03-10T23:00:00Z"),
                end_time=_dt("2026-03-10T23:50:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-03-10T23:52:00Z"),
                end_time=_dt("2026-03-11T00:45:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-03-11T00:47:00Z"),
                end_time=_dt("2026-03-11T01:30:00Z"),
            ),
        ]

        metrics, cleaned = _calculate_final_metrics(stages)

        # "sleeping" should go to sleeping_seconds, NOT deep_seconds
        assert metrics["deep_seconds"] == 0
        assert metrics["light_seconds"] == 0
        assert metrics["rem_seconds"] == 0
        assert metrics["sleeping_seconds"] > 0

        # All cleaned stages should be SLEEPING type
        for s in cleaned:
            assert s.stage == SleepStageType.SLEEPING

        # Total sleeping time: 50min + 53min + 43min = 146min = 8760s
        total_sleeping = metrics["sleeping_seconds"]
        assert total_sleeping == pytest.approx(8760, abs=60)

    def test_sleeping_plus_in_bed(self) -> None:
        """Mixed old-style data: sleeping (watch) + in_bed (phone)."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-03-10T23:00:00Z"),
                end_time=_dt("2026-03-11T01:30:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.IN_BED,
                start_time=_dt("2026-03-10T22:55:00Z"),
                end_time=_dt("2026-03-11T01:35:00Z"),
            ),
        ]

        metrics, cleaned = _calculate_final_metrics(stages)

        # deep should be 0 — sleeping is not deep
        assert metrics["deep_seconds"] == 0
        assert metrics["sleeping_seconds"] > 0
        # in_bed calculated from in_bed intervals
        assert metrics["in_bed_seconds"] > 0
        # Cleaned stages should only include sleeping (not in_bed)
        assert all(s.stage == SleepStageType.SLEEPING for s in cleaned)

    def test_detailed_stages(self) -> None:
        """Modern Apple Watch data with deep/light/rem/awake breakdown."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.LIGHT, start_time=_dt("2026-03-10T22:15:00Z"), end_time=_dt("2026-03-10T23:00:00Z")
            ),
            SleepStateStage(
                stage=SleepStageType.DEEP, start_time=_dt("2026-03-10T23:00:00Z"), end_time=_dt("2026-03-11T00:30:00Z")
            ),
            SleepStateStage(
                stage=SleepStageType.REM, start_time=_dt("2026-03-11T00:30:00Z"), end_time=_dt("2026-03-11T01:15:00Z")
            ),
            SleepStateStage(
                stage=SleepStageType.AWAKE, start_time=_dt("2026-03-11T01:15:00Z"), end_time=_dt("2026-03-11T01:25:00Z")
            ),
            SleepStateStage(
                stage=SleepStageType.DEEP, start_time=_dt("2026-03-11T01:25:00Z"), end_time=_dt("2026-03-11T02:30:00Z")
            ),
        ]

        metrics, cleaned = _calculate_final_metrics(stages)

        assert metrics["sleeping_seconds"] == 0
        assert metrics["light_seconds"] == 45 * 60  # 45 min
        assert metrics["deep_seconds"] == (90 + 65) * 60  # 155 min
        assert metrics["rem_seconds"] == 45 * 60  # 45 min
        assert metrics["awake_seconds"] == 10 * 60  # 10 min

    def test_in_bed_fallback_includes_sleeping(self) -> None:
        """When no in_bed stages exist, in_bed_seconds should sum all sleep types."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-03-11T00:00:00Z"),
                end_time=_dt("2026-03-11T06:00:00Z"),
            ),
        ]

        metrics, _ = _calculate_final_metrics(stages)

        # No in_bed stages → fallback includes sleeping_seconds
        assert metrics["in_bed_seconds"] == metrics["sleeping_seconds"] + metrics["awake_seconds"]

    def test_empty_stages(self) -> None:
        """Empty stages list should return zero metrics."""
        metrics, cleaned = _calculate_final_metrics([])

        assert metrics["sleeping_seconds"] == 0
        assert metrics["deep_seconds"] == 0
        assert metrics["in_bed_seconds"] == 0
        assert cleaned == []

    def test_only_in_bed_treated_as_sleeping(self) -> None:
        """When only in_bed stages exist (no sleep phases), treat in_bed as sleeping."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.IN_BED,
                start_time=_dt("2026-04-10T22:30:00Z"),
                end_time=_dt("2026-04-11T06:00:00Z"),
            ),
        ]

        metrics, cleaned = _calculate_final_metrics(stages)

        # in_bed should be converted to sleeping
        assert metrics["sleeping_seconds"] == 7.5 * 3600
        assert metrics["deep_seconds"] == 0
        assert metrics["light_seconds"] == 0
        assert metrics["rem_seconds"] == 0
        # in_bed_seconds still calculated from original in_bed intervals
        assert metrics["in_bed_seconds"] == 7.5 * 3600
        # Hypnogram should show sleeping, not in_bed
        assert len(cleaned) == 1
        assert cleaned[0].stage == SleepStageType.SLEEPING

    def test_detailed_plus_sleeping_wrapper_excludes_sleeping(self) -> None:
        """When detailed phases + sleeping wrapper coexist, sleeping is dropped."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-04-10T22:00:00Z"),
                end_time=_dt("2026-04-11T06:00:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.LIGHT,
                start_time=_dt("2026-04-10T22:10:00Z"),
                end_time=_dt("2026-04-10T23:00:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.DEEP,
                start_time=_dt("2026-04-10T23:00:00Z"),
                end_time=_dt("2026-04-11T01:00:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.REM,
                start_time=_dt("2026-04-11T01:00:00Z"),
                end_time=_dt("2026-04-11T02:00:00Z"),
            ),
        ]

        metrics, cleaned = _calculate_final_metrics(stages)

        # sleeping wrapper must NOT be counted
        assert metrics["sleeping_seconds"] == 0
        assert metrics["light_seconds"] == 50 * 60
        assert metrics["deep_seconds"] == 2 * 3600
        assert metrics["rem_seconds"] == 1 * 3600
        # Hypnogram should not contain sleeping
        stage_types = {s.stage for s in cleaned}
        assert SleepStageType.SLEEPING not in stage_types
        assert SleepStageType.IN_BED not in stage_types

    def test_detailed_plus_sleeping_plus_in_bed(self) -> None:
        """Full modern scenario: in_bed + sleeping wrapper + detailed phases."""
        stages = [
            SleepStateStage(
                stage=SleepStageType.IN_BED,
                start_time=_dt("2026-04-10T22:00:00Z"),
                end_time=_dt("2026-04-11T06:00:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.SLEEPING,
                start_time=_dt("2026-04-10T22:00:00Z"),
                end_time=_dt("2026-04-11T06:00:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.DEEP,
                start_time=_dt("2026-04-10T22:30:00Z"),
                end_time=_dt("2026-04-11T00:00:00Z"),
            ),
            SleepStateStage(
                stage=SleepStageType.LIGHT,
                start_time=_dt("2026-04-11T00:00:00Z"),
                end_time=_dt("2026-04-11T02:00:00Z"),
            ),
        ]

        metrics, cleaned = _calculate_final_metrics(stages)

        # Only detailed phases should be counted
        assert metrics["sleeping_seconds"] == 0
        assert metrics["deep_seconds"] == 1.5 * 3600
        assert metrics["light_seconds"] == 2 * 3600
        # in_bed still calculated from original intervals
        assert metrics["in_bed_seconds"] == 8 * 3600
        # Hypnogram: only deep + light
        stage_types = {s.stage for s in cleaned}
        assert stage_types == {SleepStageType.DEEP, SleepStageType.LIGHT}


class TestFinishSleep:
    """Tests for finish_sleep with different stage compositions."""

    @patch("app.services.apple.healthkit.sleep_service.event_record_service")
    @patch("app.services.apple.healthkit.sleep_service.delete_sleep_state")
    def test_finish_sleep_with_sleeping_stages(
        self,
        mock_delete_state: MagicMock,
        mock_event_service: MagicMock,
        db: Session,
    ) -> None:
        """Finish sleep with old-style 'sleeping' data should set correct totals."""
        user_id = str(uuid4())
        mock_record = MagicMock()
        mock_record.id = uuid4()
        mock_event_service.create.return_value = mock_record

        state = SleepState(
            uuid=str(uuid4()),
            source_name="Apple Watch",
            device_model="Watch3,3",
            provider="apple",
            start_time=_dt("2026-03-15T23:00:00Z"),
            end_time=_dt("2026-03-16T01:30:00Z"),
            last_start_timestamp=_dt("2026-03-16T00:47:00Z"),
            last_end_timestamp=_dt("2026-03-16T01:30:00Z"),
            sleeping_seconds=8760.0,
            stages=[
                SleepStateStage(
                    stage=SleepStageType.SLEEPING,
                    start_time=_dt("2026-03-15T23:00:00Z"),
                    end_time=_dt("2026-03-15T23:50:00Z"),
                ),
                SleepStateStage(
                    stage=SleepStageType.SLEEPING,
                    start_time=_dt("2026-03-15T23:52:00Z"),
                    end_time=_dt("2026-03-16T00:45:00Z"),
                ),
                SleepStateStage(
                    stage=SleepStageType.SLEEPING,
                    start_time=_dt("2026-03-16T00:47:00Z"),
                    end_time=_dt("2026-03-16T01:30:00Z"),
                ),
            ],
        )

        finish_sleep(db, user_id, state)

        # Verify create was called
        mock_event_service.create.assert_called_once()
        mock_event_service.create_detail.assert_called_once()

        # Check the detail payload
        detail_call = mock_event_service.create_detail.call_args
        detail = detail_call[0][1]  # second positional arg

        # Total duration should include sleeping time
        assert detail.sleep_total_duration_minutes > 0
        # Deep/rem/light should all be 0 (no breakdown available)
        assert detail.sleep_deep_minutes == 0
        assert detail.sleep_rem_minutes == 0
        assert detail.sleep_light_minutes == 0
        # Stages should be present
        assert detail.sleep_stages is not None
        assert len(detail.sleep_stages) == 3
        assert all(s.stage == SleepStageType.SLEEPING for s in detail.sleep_stages)

    @patch("app.services.apple.healthkit.sleep_service.event_record_service")
    @patch("app.services.apple.healthkit.sleep_service.delete_sleep_state")
    def test_finish_sleep_with_detailed_stages(
        self,
        mock_delete_state: MagicMock,
        mock_event_service: MagicMock,
        db: Session,
    ) -> None:
        """Finish sleep with detailed stages should set deep/rem/light correctly."""
        user_id = str(uuid4())
        mock_record = MagicMock()
        mock_record.id = uuid4()
        mock_event_service.create.return_value = mock_record

        state = SleepState(
            uuid=str(uuid4()),
            source_name="Apple Watch",
            device_model="Watch7,1",
            provider="apple",
            start_time=_dt("2026-03-10T22:15:00Z"),
            end_time=_dt("2026-03-11T02:30:00Z"),
            last_start_timestamp=_dt("2026-03-11T01:25:00Z"),
            last_end_timestamp=_dt("2026-03-11T02:30:00Z"),
            light_seconds=2700.0,  # 45 min
            deep_seconds=9300.0,  # 155 min
            rem_seconds=2700.0,  # 45 min
            awake_seconds=600.0,  # 10 min
            stages=[
                SleepStateStage(
                    stage=SleepStageType.LIGHT,
                    start_time=_dt("2026-03-10T22:15:00Z"),
                    end_time=_dt("2026-03-10T23:00:00Z"),
                ),
                SleepStateStage(
                    stage=SleepStageType.DEEP,
                    start_time=_dt("2026-03-10T23:00:00Z"),
                    end_time=_dt("2026-03-11T00:30:00Z"),
                ),
                SleepStateStage(
                    stage=SleepStageType.REM,
                    start_time=_dt("2026-03-11T00:30:00Z"),
                    end_time=_dt("2026-03-11T01:15:00Z"),
                ),
                SleepStateStage(
                    stage=SleepStageType.AWAKE,
                    start_time=_dt("2026-03-11T01:15:00Z"),
                    end_time=_dt("2026-03-11T01:25:00Z"),
                ),
                SleepStateStage(
                    stage=SleepStageType.DEEP,
                    start_time=_dt("2026-03-11T01:25:00Z"),
                    end_time=_dt("2026-03-11T02:30:00Z"),
                ),
            ],
        )

        finish_sleep(db, user_id, state)

        detail = mock_event_service.create_detail.call_args[0][1]

        assert detail.sleep_deep_minutes == 155
        assert detail.sleep_light_minutes == 45
        assert detail.sleep_rem_minutes == 45
        assert detail.sleep_awake_minutes == 10
        assert detail.sleep_total_duration_minutes == 245  # light+deep+rem (no sleeping)


class TestHandleSleepDataIntegration:
    """Integration tests for handle_sleep_data with real payload structures."""

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps")
    @patch("app.services.apple.healthkit.sleep_service.event_record_service")
    @patch("app.services.apple.healthkit.sleep_service.get_redis_client")
    def test_handle_real_payload_sleeping_stages(
        self,
        mock_redis_func: MagicMock,
        mock_event_service: MagicMock,
        mock_finalize: MagicMock,
        db: Session,
    ) -> None:
        """Process a synthetic payload with in_bed + sleeping stages.

        Modeled after older Apple Watch pattern:
        - 3 sleeping segments (Watch3,3)
        - 1 in_bed segment (iPhone15,2)
        All within gap threshold → single session.
        """
        user_id = str(uuid4())

        mock_redis = MagicMock()
        mock_redis.get.return_value = None  # No existing state
        mock_redis_func.return_value = mock_redis

        mock_record = MagicMock()
        mock_record.id = uuid4()
        mock_event_service.create.return_value = mock_record

        request = SyncRequest.model_validate(OLD_WATCH_PAYLOAD)

        handle_sleep_data(db, request, user_id)

        # Sleep state should be saved to Redis (session not yet finalized —
        # that happens via finalize_stale_sleeps.delay())
        assert mock_redis.set.called

        # The finalize task should be dispatched
        mock_finalize.delay.assert_called_once()

        # Verify saved state: grab the last set() call's value
        last_set_call = mock_redis.set.call_args_list[-1]
        state_json = last_set_call[0][1]  # second positional arg
        state = SleepState.model_validate_json(state_json)

        # sleeping_seconds should be populated, NOT deep_seconds
        assert state.sleeping_seconds > 0
        assert state.deep_seconds == 0
        assert state.light_seconds == 0
        assert state.rem_seconds == 0

        # Stages should have SLEEPING and IN_BED types
        # Note: with 120-min gap threshold, entries 1-2 form one session (finalized),
        # entry 3 (sleeping) + entry 4 (in_bed) form the active session in Redis.
        sleeping_stages = [s for s in state.stages if s.stage == SleepStageType.SLEEPING]
        in_bed_stages = [s for s in state.stages if s.stage == SleepStageType.IN_BED]
        assert len(sleeping_stages) >= 1
        assert len(in_bed_stages) == 1

    @patch("app.integrations.celery.tasks.finalize_stale_sleep_task.finalize_stale_sleeps")
    @patch("app.services.apple.healthkit.sleep_service.event_record_service")
    @patch("app.services.apple.healthkit.sleep_service.get_redis_client")
    def test_handle_detailed_stages_payload(
        self,
        mock_redis_func: MagicMock,
        mock_event_service: MagicMock,
        mock_finalize: MagicMock,
        db: Session,
    ) -> None:
        """Process a modern payload with detailed sleep stages."""
        user_id = str(uuid4())

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis_func.return_value = mock_redis

        request = SyncRequest.model_validate(DETAILED_STAGES_PAYLOAD)

        handle_sleep_data(db, request, user_id)

        # Verify saved state
        last_set_call = mock_redis.set.call_args_list[-1]
        state = SleepState.model_validate_json(last_set_call[0][1])

        assert state.sleeping_seconds == 0
        assert state.deep_seconds > 0
        assert state.light_seconds > 0
        assert state.rem_seconds > 0
        assert state.awake_seconds > 0

        # Verify stage types
        stage_types = {s.stage for s in state.stages}
        assert SleepStageType.DEEP in stage_types
        assert SleepStageType.LIGHT in stage_types
        assert SleepStageType.REM in stage_types
        assert SleepStageType.AWAKE in stage_types


class TestSDKSyncEndpointSleep:
    """Test the /sdk/users/{user_id}/sync endpoint with sleep payloads."""

    def test_sync_endpoint_accepts_sleeping_stage(
        self,
        client: MagicMock,
        db: Session,
    ) -> None:
        """Endpoint should validate payload with 'sleeping' stage (older Apple Watch)."""
        from app.services.sdk_token_service import create_sdk_user_token

        user_id = str(uuid4())
        token = create_sdk_user_token("test_app", user_id)

        with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as mock_task:
            mock_task.delay.return_value = None

            response = client.post(
                "/api/v1/sdk/users/" + user_id + "/sync/",
                headers={"Authorization": f"Bearer {token}"},
                json=OLD_WATCH_PAYLOAD,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status_code"] == 202
        mock_task.delay.assert_called_once()

    def test_sync_endpoint_accepts_detailed_stages(
        self,
        client: MagicMock,
        db: Session,
    ) -> None:
        """Endpoint should validate payload with detailed sleep stages."""
        from app.services.sdk_token_service import create_sdk_user_token

        user_id = str(uuid4())
        token = create_sdk_user_token("test_app", user_id)

        with patch("app.api.routes.v1.sdk_sync.process_sdk_upload") as mock_task:
            mock_task.delay.return_value = None

            response = client.post(
                "/api/v1/sdk/users/" + user_id + "/sync/",
                headers={"Authorization": f"Bearer {token}"},
                json=DETAILED_STAGES_PAYLOAD,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status_code"] == 202
