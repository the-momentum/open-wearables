"""Tests for the SDK sync status endpoint."""

from collections.abc import Iterator
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from app.repositories.data_type_coverage_repository import data_type_coverage_repository
from app.schemas.data_type_coverage import CoverageSpan
from app.schemas.sync_status import (
    DataTypeKind,
    DataTypeOutcome,
    SyncScope,
    SyncSource,
    SyncStage,
    SyncStatus,
    SyncStatusEvent,
)
from app.services.sdk_token_service import create_sdk_user_token
from app.services.sync_status_service import try_persist_run, try_record_data_types
from tests.factories import ApiKeyFactory, UserFactory

ENDPOINT = "/api/v1/sdk/users/{user_id}/sync/status"


def _at(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


@pytest.fixture
def stored_runs(db: Session) -> Iterator[None]:
    """Route the best-effort run writers onto the test session."""
    with patch("app.services.sync_status_service.SessionLocal") as session_local:
        session_local.return_value.__enter__.return_value = db
        with patch("app.services.sync_status_service._dispatch_data_type_webhooks"):
            yield


def _open_export(user_id: UUID, session_id: str, started_at: datetime, provider: str = "apple") -> str:
    run_key = f"sdk_{session_id}"
    try_persist_run(
        SyncStatusEvent(
            run_id=run_key,
            user_id=user_id,
            provider=provider,
            source=SyncSource.SDK,
            scope=SyncScope.HISTORICAL,
            stage=SyncStage.STARTED,
            status=SyncStatus.IN_PROGRESS,
            started_at=started_at,
            timestamp=started_at,
        )
    )
    return run_key


def _report(
    run_key: str,
    data_type: str,
    status: SyncStatus,
    kind: DataTypeKind = DataTypeKind.SERIES,
    covered: tuple[datetime, datetime] | None = None,
) -> None:
    span = {"covered_start": covered[0], "covered_end": covered[1]} if covered else {}
    try_record_data_types(
        run_key,
        [DataTypeOutcome(data_type=data_type, kind=kind, status=status, **span)],
        scope=SyncScope.HISTORICAL,
    )


def _hold(
    db: Session,
    user_id: UUID,
    start: datetime,
    end: datetime,
    data_type: str = "heart_rate",
    kind: DataTypeKind = DataTypeKind.SERIES,
    provider: str = "apple",
) -> None:
    data_type_coverage_repository.record(db, [CoverageSpan(user_id, provider, data_type, kind, start, end)])
    db.commit()


def _get(client: TestClient, user_id: UUID, provider: str = "apple", token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {"X-Open-Wearables-API-Key": ApiKeyFactory().plain_key}
    response = client.get(ENDPOINT.format(user_id=user_id), params={"provider": provider}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _types(body: dict) -> dict[str, dict]:
    return {item["type"]: item for item in body["dataTypes"]}


class TestSDKSyncState:
    def test_new_user_gets_empty_state(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        assert _get(client, user.id) == {
            "provider": "apple",
            "historicalSyncCompleted": None,
            "syncedUntil": None,
            "dataTypes": [],
        }

    @pytest.mark.usefixtures("stored_runs")
    def test_interrupted_export_reports_where_each_type_resumes(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(30))
        _report(run_key, "heart_rate", SyncStatus.IN_PROGRESS, covered=(_at(25), _at(30, 18)))
        _report(run_key, "steps", SyncStatus.SUCCESS)
        _hold(db, user.id, _at(20), _at(30, 18), data_type="heart_rate")
        _hold(db, user.id, _at(1), _at(30, 17), data_type="steps")

        body = _get(client, user.id)

        assert body["historicalSyncCompleted"] is False
        assert body["syncedUntil"] == "2026-10-30T18:00:00Z"
        heart_rate, steps = _types(body)["heart_rate"], _types(body)["steps"]
        assert heart_rate["historicalSyncCompleted"] is False
        assert heart_rate["coveredRange"] == {"startDate": "2026-10-20T00:00:00Z", "endDate": "2026-10-30T18:00:00Z"}
        assert heart_rate["exportedRange"] == {"startDate": "2026-10-25T00:00:00Z", "endDate": "2026-10-30T18:00:00Z"}
        assert steps["historicalSyncCompleted"] is True

    @pytest.mark.usefixtures("stored_runs")
    def test_resume_point_comes_from_the_latest_export_not_the_data_held(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        old = _open_export(user.id, "s1", _at(5))
        _report(old, "heart_rate", SyncStatus.UNFINISHED, covered=(_at(1), _at(5)))
        new = _open_export(user.id, "s2", _at(30))
        _report(new, "heart_rate", SyncStatus.IN_PROGRESS, covered=(_at(20), _at(30)))
        _hold(db, user.id, _at(1), _at(30))

        heart_rate = _types(_get(client, user.id))["heart_rate"]

        assert heart_rate["coveredRange"]["startDate"] == "2026-10-01T00:00:00Z"
        assert heart_rate["exportedRange"] == {"startDate": "2026-10-20T00:00:00Z", "endDate": "2026-10-30T00:00:00Z"}

    @pytest.mark.usefixtures("stored_runs")
    def test_sleep_and_workouts_reported_under_native_names_still_complete(
        self, client: TestClient, db: Session
    ) -> None:
        """A batch writes `sleep`/`workouts`, the end event the device's own identifier."""
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(28))
        _report(run_key, "heart_rate", SyncStatus.SUCCESS)
        _report(run_key, "sleep", SyncStatus.IN_PROGRESS, DataTypeKind.EVENT)
        _report(run_key, "HKCategoryTypeIdentifierSleepAnalysis", SyncStatus.SUCCESS, DataTypeKind.EVENT)
        _report(run_key, "workouts", SyncStatus.IN_PROGRESS, DataTypeKind.EVENT)
        _report(run_key, "WORKOUT", SyncStatus.SUCCESS, DataTypeKind.EVENT)
        _hold(db, user.id, _at(1), _at(27, 7), data_type="sleep", kind=DataTypeKind.EVENT)
        _hold(db, user.id, _at(2), _at(26), data_type="workout", kind=DataTypeKind.EVENT)

        body = _get(client, user.id)

        assert body["historicalSyncCompleted"] is True
        assert _types(body)["sleep"]["historicalSyncCompleted"] is True
        assert _types(body)["workout"]["historicalSyncCompleted"] is True

    @pytest.mark.usefixtures("stored_runs")
    def test_completed_export_marks_every_held_type_done(self, client: TestClient, db: Session) -> None:
        """The device sends no end event for a type it had nothing to send, so the run decides."""
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(28))
        _report(run_key, "heart_rate", SyncStatus.SUCCESS)
        _hold(db, user.id, _at(1), datetime(2026, 11, 1, 22, 15, tzinfo=timezone.utc), data_type="heart_rate")
        _hold(db, user.id, _at(3), _at(4), data_type="weight")

        body = _get(client, user.id)

        assert body["historicalSyncCompleted"] is True
        assert body["syncedUntil"] == "2026-11-01T22:15:00Z"
        assert all(item["historicalSyncCompleted"] for item in body["dataTypes"])

    @pytest.mark.usefixtures("stored_runs")
    def test_failed_type_leaves_the_export_incomplete(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(28))
        _report(run_key, "heart_rate", SyncStatus.SUCCESS)
        _report(run_key, "steps", SyncStatus.IN_PROGRESS)
        _report(run_key, "steps", SyncStatus.FAILED)
        _hold(db, user.id, _at(10), _at(28), data_type="steps")

        body = _get(client, user.id)

        assert body["historicalSyncCompleted"] is False
        assert _types(body)["steps"]["historicalSyncCompleted"] is False

    @pytest.mark.usefixtures("stored_runs")
    def test_completion_survives_a_later_interrupted_export(self, client: TestClient, db: Session) -> None:
        """A device that lost its state may start a new export; the finished one still counts."""
        user = UserFactory()
        done = _open_export(user.id, "s1", _at(10))
        _report(done, "heart_rate", SyncStatus.SUCCESS)
        later = _open_export(user.id, "s2", _at(20))
        _report(later, "heart_rate", SyncStatus.IN_PROGRESS)

        assert _get(client, user.id)["historicalSyncCompleted"] is True

    @pytest.mark.usefixtures("stored_runs")
    def test_other_providers_do_not_leak_in(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(10), provider="samsung")
        _report(run_key, "heart_rate", SyncStatus.SUCCESS)
        _hold(db, user.id, _at(1), _at(31), data_type="steps", provider="samsung")

        assert _get(client, user.id) == {
            "provider": "apple",
            "historicalSyncCompleted": None,
            "syncedUntil": None,
            "dataTypes": [],
        }

    @pytest.mark.usefixtures("stored_runs")
    def test_state_is_returned_after_logging_in_again(self, client: TestClient, db: Session) -> None:
        """The device lost its local state on logout; a fresh token reads it back from the server."""
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(30))
        _report(run_key, "heart_rate", SyncStatus.IN_PROGRESS)
        _hold(db, user.id, _at(20), _at(30, 18))

        first = _get(client, user.id, token=create_sdk_user_token("app_1", str(user.id)))
        relogged = _get(client, user.id, token=create_sdk_user_token("app_1", str(user.id)))

        assert relogged == first
        assert relogged["historicalSyncCompleted"] is False
        assert relogged["syncedUntil"] == "2026-10-30T18:00:00Z"
        assert [{k: v for k, v in item.items() if k != "lastSyncedAt"} for item in relogged["dataTypes"]] == [
            {
                "type": "heart_rate",
                "kind": "series",
                "historicalSyncCompleted": False,
                "coveredRange": {"startDate": "2026-10-20T00:00:00Z", "endDate": "2026-10-30T18:00:00Z"},
                "exportedRange": None,
            }
        ]

    def test_data_without_any_export_on_record_is_unknown_not_unfinished(self, client: TestClient, db: Session) -> None:
        """SDKs that send no syncSessionId upload as live, so no export is ever recorded."""
        user = UserFactory()
        _hold(db, user.id, _at(1), _at(30))

        body = _get(client, user.id)

        assert body["historicalSyncCompleted"] is None
        assert body["syncedUntil"] == "2026-10-30T00:00:00Z"
        assert _types(body)["heart_rate"]["historicalSyncCompleted"] is None

    @pytest.mark.usefixtures("stored_runs")
    def test_started_export_with_nothing_reported_yet_is_unfinished(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        _open_export(user.id, "s1", _at(30))

        assert _get(client, user.id)["historicalSyncCompleted"] is False

    @pytest.mark.usefixtures("stored_runs")
    def test_type_no_export_reported_is_unknown(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        run_key = _open_export(user.id, "s1", _at(30))
        _report(run_key, "heart_rate", SyncStatus.IN_PROGRESS)
        _hold(db, user.id, _at(20), _at(30), data_type="heart_rate")
        _hold(db, user.id, _at(1), _at(2), data_type="weight")

        types = _types(_get(client, user.id))

        assert types["heart_rate"]["historicalSyncCompleted"] is False
        assert types["weight"]["historicalSyncCompleted"] is None

    def test_provider_alias_is_normalized(self, client: TestClient, db: Session) -> None:
        user = UserFactory()

        assert _get(client, user.id, provider="google")["provider"] == "health_connect"


class TestSDKSyncStateAccess:
    def test_unsupported_provider_is_rejected(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        response = client.get(
            ENDPOINT.format(user_id=user.id),
            params={"provider": "garmin"},
            headers={"X-Open-Wearables-API-Key": ApiKeyFactory().plain_key},
        )
        assert response.status_code == 422

    def test_token_for_another_user_is_forbidden(self, client: TestClient, db: Session) -> None:
        user = UserFactory()
        token = create_sdk_user_token("app_1", str(uuid4()))
        response = client.get(
            ENDPOINT.format(user_id=user.id),
            params={"provider": "apple"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    def test_unknown_user_is_not_found(self, client: TestClient, db: Session) -> None:
        response = client.get(
            ENDPOINT.format(user_id=uuid4()),
            params={"provider": "apple"},
            headers={"X-Open-Wearables-API-Key": ApiKeyFactory().plain_key},
        )
        assert response.status_code == 404

    def test_requires_auth(self, client: TestClient, db: Session) -> None:
        response = client.get(ENDPOINT.format(user_id=uuid4()), params={"provider": "apple"})
        assert response.status_code == 401
