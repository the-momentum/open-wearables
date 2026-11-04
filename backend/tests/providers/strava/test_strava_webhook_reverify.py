"""Strava webhook events are unauthenticated, so destructive ones are confirmed in the Strava API first.

Strava signs events with a key it does not expose, so anyone can send a well-formed event.
Each scenario runs a real Strava payload through the real ``process_webhook_push`` task
(handler -> api_client -> token refresh -> revoke) against the test DB. Only the HTTP
calls to Strava and the outgoing connection.revoked webhook are replaced.

- activity delete: deleted only when GET /activities/{id} answers 404. Activities we
  do not store are ignored without an API call.
- deauthorization (athlete update, authorized "false"): the connection is revoked, with
  reason "deregistration", only when Strava rejects both the access token and the
  refresh token.
- Any other API failure leaves the data alone and reaches the task, which retries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlalchemy.orm import Session

import app.integrations.celery.tasks.webhook_push_task as task
from app.models import EventRecord
from app.schemas.auth import ConnectionStatus
from app.services.providers.factory import ProviderFactory
from app.utils.exceptions import ProviderError
from tests.factories import DataSourceFactory, EventRecordFactory, UserConnectionFactory, UserFactory

ATHLETE_ID = 315693644
ACTIVITY_ID = 20853903452
CREATE_TIME = 1793785587

# Captured from Strava on 2026-11-04 (test app 293960).
CREATE_EVENT = {
    "aspect_type": "create",
    "event_time": CREATE_TIME,
    "object_id": ACTIVITY_ID,
    "object_type": "activity",
    "owner_id": ATHLETE_ID,
    "subscription_id": 382914,
    "updates": {},
}
CREATE_SIGNATURE = "t=1793785587,v1=4bace6d8848993ba7485901de535bfa71d1b4b7708cacba069ed48241dd99765"
DELETE_EVENT = {
    "aspect_type": "delete",
    "event_time": 1793786072,
    "object_id": ACTIVITY_ID,
    "object_type": "activity",
    "owner_id": ATHLETE_ID,
    "subscription_id": 382914,
    "updates": {},
}
DEAUTH_EVENT = {
    "aspect_type": "update",
    "event_time": 1793786378,
    "object_id": ATHLETE_ID,
    "object_type": "athlete",
    "owner_id": ATHLETE_ID,
    "subscription_id": 382914,
    "updates": {"authorized": "false"},
}

API_URL = "https://www.strava.com/api/v3/x"
TOKEN_URL = "https://www.strava.com/oauth/token"
RECORD_NOT_FOUND = {"message": "Record Not Found", "errors": [{"resource": "Activity", "code": "not found"}]}
AUTHORIZATION_ERROR = {
    "message": "Authorization Error",
    "errors": [{"resource": "Athlete", "field": "access_token", "code": "invalid"}],
}
REFRESH_TOKEN_INVALID = {
    "message": "Bad Request",
    "errors": [{"resource": "RefreshToken", "field": "refresh_token", "code": "invalid"}],
}
REFRESHED_TOKEN = {
    "token_type": "Bearer",
    "access_token": "refreshed-access",
    "refresh_token": "refreshed-refresh",
    "expires_in": 21600,
}


@pytest.fixture
def handler() -> Any:
    return ProviderFactory().get_provider("strava").webhooks


@pytest.fixture
def user() -> Any:
    return UserFactory()


@pytest.fixture
def connection(user: Any) -> Any:
    return UserConnectionFactory(user=user, provider="strava", provider_user_id=str(ATHLETE_ID))


@pytest.fixture
def activity(user: Any, connection: Any) -> Any:
    source = DataSourceFactory(user=user, provider="strava", source="strava")
    return EventRecordFactory(data_source=source, external_id=str(ACTIVITY_ID), source_name="Strava")


def _response(status_code: int, body: dict[str, Any], url: str = API_URL) -> httpx.Response:
    method = "POST" if url == TOKEN_URL else "GET"
    return httpx.Response(status_code, json=body, request=httpx.Request(method, url))


@dataclass
class Delivery:
    result: dict[str, Any]
    requested: MagicMock  # Strava API calls
    revoked: MagicMock  # connection.revoked sent by the Strava handler


def _run_webhook(
    db: Session,
    payload: dict[str, Any],
    api: list[httpx.Response | Exception],
    refresh: httpx.Response | None = None,
    *,
    refresh_may_revoke: bool = False,
) -> Delivery:
    """Run one delivery through process_webhook_push; ``api`` answers the Strava API calls in order."""
    client = MagicMock()
    client.__enter__.return_value.request.side_effect = api
    with (
        patch.object(task, "SessionLocal") as session_local,
        patch("app.services.providers.api_client.httpx.Client", return_value=client),
        patch("app.services.providers.templates.base_oauth.httpx.post", return_value=refresh) as token_post,
        patch("app.services.providers.templates.base_oauth.on_connection_revoked") as revoked,
        patch.object(task.sync_status_service, "emit_webhook_delivered"),
    ):
        session_local.return_value.__enter__.return_value = db
        result = task.process_webhook_push.run("strava", payload, "trace-1868")
    assert token_post.called == (refresh is not None)
    # A rejected refresh token must not revoke with another reason before the handler does.
    if not refresh_may_revoke:
        assert all(call.kwargs["reason"] == "deregistration" for call in revoked.call_args_list)
    return Delivery(result, client.__enter__.return_value.request, revoked)


def _activity_exists(db: Session, record: EventRecord) -> bool:
    return db.query(EventRecord).filter(EventRecord.id == record.id).one_or_none() is not None


class TestActivityDelete:
    def test_confirmed_delete_removes_activity(self, db: Session, activity: EventRecord) -> None:
        delivery = _run_webhook(db, DELETE_EVENT, [_response(404, RECORD_NOT_FOUND)])

        assert delivery.requested.call_args.kwargs["url"].endswith(f"/api/v3/activities/{ACTIVITY_ID}")
        assert delivery.result["status"] == "deleted"
        assert delivery.result["records_deleted"] == 1
        assert not _activity_exists(db, activity)

    def test_forged_delete_keeps_activity(self, db: Session, activity: EventRecord) -> None:
        delivery = _run_webhook(db, DELETE_EVENT, [_response(200, {"id": ACTIVITY_ID})])

        assert delivery.result == {"status": "ignored", "reason": "activity_still_exists", "activity_id": ACTIVITY_ID}
        assert _activity_exists(db, activity)

    def test_delete_of_unstored_activity_skips_api(self, db: Session, connection: Any) -> None:
        delivery = _run_webhook(db, DELETE_EVENT, [])

        delivery.requested.assert_not_called()
        assert delivery.result == {"status": "ignored", "reason": "activity_not_stored", "activity_id": ACTIVITY_ID}

    @pytest.mark.parametrize(
        "failure",
        [_response(503, {"message": "Service Unavailable"}), httpx.ReadTimeout("timed out")],
        ids=["5xx", "timeout"],
    )
    def test_api_failure_keeps_activity_and_retries(
        self, db: Session, activity: EventRecord, failure: httpx.Response | Exception
    ) -> None:
        # Called directly, Task.retry re-raises the error instead of scheduling a retry.
        with pytest.raises(ProviderError) as exc_info:
            _run_webhook(db, DELETE_EVENT, [failure])

        assert exc_info.value.status_code >= 500
        assert _activity_exists(db, activity)

    @pytest.mark.parametrize("token_status", [503, 429])
    def test_token_endpoint_failure_keeps_activity_and_retries(self, db: Session, user: Any, token_status: int) -> None:
        """Strava tokens live 6 h, so a delete usually refreshes first; a transient failure must be retried."""
        UserConnectionFactory(
            user=user,
            provider="strava",
            provider_user_id=str(ATHLETE_ID),
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        source = DataSourceFactory(user=user, provider="strava", source="strava")
        activity: Any = EventRecordFactory(data_source=source, external_id=str(ACTIVITY_ID), source_name="Strava")

        with pytest.raises(ProviderError) as exc_info:
            _run_webhook(db, DELETE_EVENT, [], refresh=_response(token_status, {"message": "x"}, url=TOKEN_URL))

        assert exc_info.value.upstream_status == token_status
        assert _activity_exists(db, activity)

    def test_dead_grant_keeps_activity(self, db: Session, connection: Any, activity: EventRecord) -> None:
        """Strava answers 401 for a deauthorized athlete, not 404: that is no proof of deletion."""
        delivery = _run_webhook(
            db,
            DELETE_EVENT,
            [_response(401, AUTHORIZATION_ERROR)],
            refresh=_response(400, REFRESH_TOKEN_INVALID, url=TOKEN_URL),
            refresh_may_revoke=True,
        )
        db.refresh(connection)

        assert delivery.result["status"] == "error"
        assert delivery.result["error"] == "reauth_required"
        assert _activity_exists(db, activity)
        assert connection.status == ConnectionStatus.REVOKED


def _assert_revoked(db: Session, connection: Any, delivery: Delivery) -> None:
    db.refresh(connection)
    assert delivery.result == {"status": "deauthorized", "strava_athlete_id": ATHLETE_ID}
    assert connection.status == ConnectionStatus.REVOKED
    delivery.revoked.assert_called_once()
    assert delivery.revoked.call_args.kwargs["provider"] == "strava"
    assert delivery.revoked.call_args.kwargs["reason"] == "deregistration"


def _assert_kept(db: Session, connection: Any, delivery: Delivery) -> None:
    db.refresh(connection)
    assert delivery.result == {
        "status": "ignored",
        "reason": "athlete_still_authorized",
        "strava_athlete_id": ATHLETE_ID,
    }
    assert connection.status == ConnectionStatus.ACTIVE
    delivery.revoked.assert_not_called()


class TestDeauthorization:
    def test_confirmed_deauthorization_revokes_connection(self, db: Session, connection: Any) -> None:
        delivery = _run_webhook(
            db,
            DEAUTH_EVENT,
            [_response(401, AUTHORIZATION_ERROR)],
            refresh=_response(400, REFRESH_TOKEN_INVALID, url=TOKEN_URL),
        )

        assert delivery.requested.call_args.kwargs["url"].endswith("/api/v3/athlete")
        _assert_revoked(db, connection, delivery)

    def test_forged_deauthorization_keeps_connection(self, db: Session, connection: Any) -> None:
        delivery = _run_webhook(db, DEAUTH_EVENT, [_response(200, {"id": ATHLETE_ID})])

        _assert_kept(db, connection, delivery)

    def test_rejected_token_with_working_refresh_keeps_connection(self, db: Session, connection: Any) -> None:
        """A 401 alone is no proof: the refreshed token still works, so the grant is alive."""
        delivery = _run_webhook(
            db,
            DEAUTH_EVENT,
            [_response(401, AUTHORIZATION_ERROR), _response(200, {"id": ATHLETE_ID})],
            refresh=_response(200, REFRESHED_TOKEN, url=TOKEN_URL),
        )

        assert delivery.requested.call_count == 2
        assert delivery.requested.call_args.kwargs["headers"]["Authorization"] == "Bearer refreshed-access"
        _assert_kept(db, connection, delivery)

    def test_expired_token_with_rejected_refresh_revokes_connection(self, db: Session, user: Any) -> None:
        connection = UserConnectionFactory(
            user=user,
            provider="strava",
            provider_user_id=str(ATHLETE_ID),
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        delivery = _run_webhook(db, DEAUTH_EVENT, [], refresh=_response(400, REFRESH_TOKEN_INVALID, url=TOKEN_URL))

        delivery.requested.assert_not_called()
        _assert_revoked(db, connection, delivery)

    def test_expired_token_with_working_refresh_keeps_connection(self, db: Session, user: Any) -> None:
        connection = UserConnectionFactory(
            user=user,
            provider="strava",
            provider_user_id=str(ATHLETE_ID),
            token_expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        delivery = _run_webhook(
            db,
            DEAUTH_EVENT,
            [_response(200, {"id": ATHLETE_ID})],
            refresh=_response(200, REFRESHED_TOKEN, url=TOKEN_URL),
        )

        assert delivery.requested.call_args.kwargs["headers"]["Authorization"] == "Bearer refreshed-access"
        _assert_kept(db, connection, delivery)

    def test_deauthorization_without_connection_skips_api(self, db: Session) -> None:
        delivery = _run_webhook(db, DEAUTH_EVENT, [])

        delivery.requested.assert_not_called()
        assert delivery.result == {"status": "user_not_found", "strava_athlete_id": ATHLETE_ID}

    @pytest.mark.parametrize(
        "failure",
        [_response(503, {"message": "Service Unavailable"}), httpx.ReadTimeout("timed out")],
        ids=["5xx", "timeout"],
    )
    def test_api_failure_keeps_connection_and_retries(
        self, db: Session, connection: Any, failure: httpx.Response | Exception
    ) -> None:
        with pytest.raises(ProviderError) as exc_info:
            _run_webhook(db, DEAUTH_EVENT, [failure])
        db.refresh(connection)

        assert exc_info.value.status_code >= 500
        assert connection.status == ConnectionStatus.ACTIVE

    @pytest.mark.parametrize("token_status", [503, 429])
    def test_token_endpoint_failure_keeps_connection_and_retries(
        self, db: Session, connection: Any, token_status: int
    ) -> None:
        """A 401 followed by a failing token endpoint proves nothing yet: retry instead of dropping the event."""
        with pytest.raises(ProviderError) as exc_info:
            _run_webhook(
                db,
                DEAUTH_EVENT,
                [_response(401, AUTHORIZATION_ERROR)],
                refresh=_response(token_status, {"message": "x"}, url=TOKEN_URL),
            )
        db.refresh(connection)

        assert exc_info.value.upstream_status == token_status
        assert connection.status == ConnectionStatus.ACTIVE

    @pytest.mark.parametrize(
        "event",
        [
            {**DEAUTH_EVENT, "aspect_type": "delete", "updates": {}},
            {**DEAUTH_EVENT, "updates": {"authorized": "true"}},
            {**DEAUTH_EVENT, "updates": {}},
        ],
        ids=["athlete-delete", "authorized-true", "no-updates"],
    )
    def test_other_athlete_events_are_ignored(self, db: Session, connection: Any, event: dict[str, Any]) -> None:
        delivery = _run_webhook(db, event, [])
        db.refresh(connection)

        delivery.requested.assert_not_called()
        assert delivery.result["status"] == "ignored"
        assert connection.status == ConnectionStatus.ACTIVE


class TestVerifySignature:
    """The header is required and its timestamp bounds replays; ``v1`` is not checked."""

    @staticmethod
    def _request(signature: str | None) -> MagicMock:
        request = MagicMock()
        request.headers = {"X-Strava-Signature": signature} if signature is not None else {}
        return request

    def _verify(self, handler: Any, signature: str | None, now: float) -> bool:
        with patch("app.services.providers.strava.webhook_handler.time.time", return_value=now):
            return handler.verify_signature(self._request(signature), json.dumps(CREATE_EVENT).encode())

    def test_real_event_within_tolerance_passes(self, handler: Any) -> None:
        assert self._verify(handler, CREATE_SIGNATURE, now=CREATE_TIME + 10) is True

    def test_stale_event_is_rejected(self, handler: Any) -> None:
        assert self._verify(handler, CREATE_SIGNATURE, now=CREATE_TIME + 301) is False

    @pytest.mark.parametrize("signature", [None, "", "v1=abc", "t=soon,v1=abc"])
    def test_missing_or_malformed_header_is_rejected(self, handler: Any, signature: str | None) -> None:
        assert self._verify(handler, signature, now=CREATE_TIME) is False
