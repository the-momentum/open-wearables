from app.schemas.auth import LiveSyncMode, resolve_live_sync_mode


def test_configured_live_sync_mode_wins() -> None:
    assert resolve_live_sync_mode(LiveSyncMode.WEBHOOK, LiveSyncMode.PULL) == LiveSyncMode.WEBHOOK


def test_live_sync_mode_falls_back_to_provider_default() -> None:
    assert resolve_live_sync_mode(None, LiveSyncMode.PULL) == LiveSyncMode.PULL


def test_live_sync_mode_remains_none_without_config_or_default() -> None:
    assert resolve_live_sync_mode(None, None) is None
