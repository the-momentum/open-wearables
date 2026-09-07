"""sync_vendor_data steals a shared pull lock whose holder has no live run (worker died mid-run).

Regression for the orphaned-lock failure mode: a periodic pull killed with its worker never
releases ``linked_sync:{provider}:{provider_user_id}:pull:primary``; with a 4 h TTL every
following pull logged "Skipping … — another linked profile is syncing" for hours.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.integrations.celery.tasks.sync_vendor_data_task import sync_vendor_data
from app.schemas.auth import ConnectionStatus
from tests.factories import UserConnectionFactory, UserFactory

TASK = "app.integrations.celery.tasks.sync_vendor_data_task"


def _strategy() -> tuple[MagicMock, MagicMock]:
    workouts = MagicMock()
    workouts.load_data.return_value = True
    strategy = MagicMock()
    strategy.capabilities.rest_pull = True
    strategy.capabilities.webhook_stream = False
    strategy.workouts = workouts
    return strategy, workouts


@patch(f"{TASK}.SessionLocal")
@patch("app.services.providers.factory.ProviderFactory.get_provider")
@patch(f"{TASK}.release_stale_primary")
@patch(f"{TASK}.primary_is_idle", return_value=True)
@patch(f"{TASK}.try_become_primary")
def test_idle_holder_lock_is_stolen_and_pull_proceeds(
    mock_try_become_primary: MagicMock,
    mock_primary_is_idle: MagicMock,
    mock_release_stale: MagicMock,
    mock_get_provider: MagicMock,
    mock_session_local: MagicMock,
    db: Session,
    mock_celery_app: MagicMock,
) -> None:
    user = UserFactory()
    holder = UserFactory()
    UserConnectionFactory(
        user=user, provider="garmin", status=ConnectionStatus.ACTIVE, provider_user_id="shared-account"
    )
    UserConnectionFactory(
        user=holder, provider="garmin", status=ConnectionStatus.ACTIVE, provider_user_id="shared-account"
    )
    mock_session_local.return_value.__enter__.return_value = db
    mock_session_local.return_value.__exit__.return_value = None
    strategy, workouts = _strategy()
    mock_get_provider.return_value = strategy
    # first election lost to the (dead) holder, second one won after the steal
    mock_try_become_primary.side_effect = [(False, "", holder.id), (True, "token", user.id)]

    result = sync_vendor_data(str(user.id))

    mock_primary_is_idle.assert_called_once_with("garmin", holder.id)
    mock_release_stale.assert_called_once_with("garmin", "shared-account", scope="pull")
    assert mock_try_become_primary.call_count == 2
    workouts.load_data.assert_called_once()
    assert result["providers_synced"]["garmin"]["success"] is True
    assert result["providers_synced"]["garmin"]["params"].get("linked_account") is None


@patch(f"{TASK}.SessionLocal")
@patch("app.services.providers.factory.ProviderFactory.get_provider")
@patch(f"{TASK}.release_stale_primary")
@patch(f"{TASK}.primary_is_idle", return_value=False)
@patch(f"{TASK}.try_become_primary")
def test_live_holder_keeps_the_lock_and_pull_is_skipped(
    mock_try_become_primary: MagicMock,
    mock_primary_is_idle: MagicMock,
    mock_release_stale: MagicMock,
    mock_get_provider: MagicMock,
    mock_session_local: MagicMock,
    db: Session,
    mock_celery_app: MagicMock,
) -> None:
    user = UserFactory()
    holder = UserFactory()
    UserConnectionFactory(
        user=user, provider="garmin", status=ConnectionStatus.ACTIVE, provider_user_id="shared-account"
    )
    UserConnectionFactory(
        user=holder, provider="garmin", status=ConnectionStatus.ACTIVE, provider_user_id="shared-account"
    )
    mock_session_local.return_value.__enter__.return_value = db
    mock_session_local.return_value.__exit__.return_value = None
    strategy, workouts = _strategy()
    mock_get_provider.return_value = strategy
    mock_try_become_primary.return_value = (False, "", holder.id)

    result = sync_vendor_data(str(user.id))

    mock_release_stale.assert_not_called()
    workouts.load_data.assert_not_called()
    assert result["providers_synced"]["garmin"]["params"] == {"linked_account": True}
