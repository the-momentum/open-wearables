"""Reproduction: new OAuth connections must trigger the backfill sync task.

Covers the Oura and Google Health callbacks end-to-end: the connection is saved
and ``sync_vendor_data.delay`` must be invoked with ``is_historical=True`` and a
provider filter matching the connected provider. Then ``sync_vendor_data`` itself
must actually run the provider's fetch for a just-created connection.
"""

import importlib
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.auth import ConnectionStatus
from app.services.providers.factory import ProviderFactory
from tests.factories import UserConnectionFactory, UserFactory


def _mock_httpx_response(json_data: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = 200
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.parametrize(
    ("provider_slug", "expected_provider", "user_info_json"),
    [
        # Oura: personal_info returns {"id": ...}
        ("oura", "oura", {"id": "oura-user-1"}),
        # Google Health: identity endpoint returns healthUserId, userinfo returns email
        ("google_health", "google_health", {"healthUserId": "g-user-1", "email": "u@x.com"}),
    ],
)
def test_oauth_callback_dispatches_historical_sync(
    provider_slug: str,
    expected_provider: str,
    user_info_json: dict[str, Any],
    client: TestClient,
    db: Session,
) -> None:
    user = UserFactory()

    factory = ProviderFactory()
    strategy = factory.get_provider(expected_provider)
    assert strategy.oauth is not None
    _, state = strategy.oauth.get_authorization_url(str(user.id))

    with (
        patch(
            "httpx.post",
            return_value=_mock_httpx_response(
                {"access_token": "tok", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "ref"}
            ),
        ),
        patch("httpx.get", return_value=_mock_httpx_response(user_info_json)),
        patch("app.integrations.celery.tasks.sync_vendor_data.delay") as mock_delay,
    ):
        response = client.get(
            f"/api/v1/oauth/{provider_slug}/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )

    assert response.status_code in (303, 200), response.text

    # The connection must exist and be active.
    connection = UserConnectionRepository().get_by_user_and_provider(db, str(user.id), expected_provider)
    assert connection is not None, "connection was not saved"
    assert connection.status == "active" or connection.status.value == "active"

    # The backfill task must have been dispatched.
    assert mock_delay.called, f"backfill not dispatched for {expected_provider}"
    kwargs = mock_delay.call_args.kwargs
    assert kwargs["providers"] == [expected_provider]
    assert kwargs["is_historical"] is True


@pytest.mark.parametrize(
    ("provider", "workouts_path", "data247_path"),
    [
        # Patch where the strategy module binds the class name (it does `from x import Y`).
        (
            "oura",
            "app.services.providers.oura.strategy.OuraWorkouts",
            "app.services.providers.oura.strategy.Oura247Data",
        ),
        (
            "google_health",
            "app.services.providers.google_health.strategy.GoogleHealthApiWorkouts",
            "app.services.providers.google_health.strategy.GoogleHealth247Data",
        ),
    ],
)
def test_historical_sync_runs_for_new_connection(
    provider: str,
    workouts_path: str,
    data247_path: str,
    db: Session,
) -> None:
    """The connect-time backfill task must reach the provider fetch, not get filtered/skipped."""
    user = UserFactory()
    UserConnectionFactory(
        user=user,
        provider=provider,
        status=ConnectionStatus.ACTIVE,
        provider_user_id=f"{provider}-u-1",
    )

    workouts_module, workouts_cls = workouts_path.rsplit(".", 1)
    data247_module, data247_cls = data247_path.rsplit(".", 1)

    with (
        patch("app.integrations.celery.tasks.sync_vendor_data_task.SessionLocal") as mock_session_local,
        patch.object(importlib.import_module(workouts_module), workouts_cls) as mock_workouts_cls,
        patch.object(importlib.import_module(data247_module), data247_cls) as mock_data247_cls,
    ):
        mock_session_local.return_value.__enter__.return_value = db
        mock_session_local.return_value.__exit__.return_value = None
        mock_workouts_cls.return_value.load_data.return_value = 1
        mock_data247_cls.return_value.load_and_save_all.return_value = {"sleep": 2}

        result = sync_vendor_data(
            user_id=str(user.id),
            start_date="2026-07-01T00:00:00+00:00",
            end_date="2026-09-28T00:00:00+00:00",
            providers=[provider],
            is_historical=True,
        )

    assert provider in result["providers_synced"], result
    assert result["providers_synced"][provider]["success"] is True
    mock_workouts_cls.return_value.load_data.assert_called_once()
    mock_data247_cls.return_value.load_and_save_all.assert_called_once()
