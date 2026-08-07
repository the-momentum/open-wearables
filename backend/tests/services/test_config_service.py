from app.models import AppSetting
from app.schemas.app_config import MANAGED_SETTING_KEYS, RESTART_REQUIRED_KEYS, AppConfig


def test_managed_keys_match_model_and_schema() -> None:
    """AppConfig, the managed key set, and the app_settings columns must stay in lockstep.

    Adding a column to AppSetting without a matching AppConfig field (or vice versa) breaks
    resolution/serialization, so fail loudly here.
    """
    columns = {c.name for c in AppSetting.__table__.columns} - {"id", "created_at"}
    assert set(MANAGED_SETTING_KEYS) == set(AppConfig.model_fields) == columns


def test_restart_required_keys_are_managed() -> None:
    assert set(RESTART_REQUIRED_KEYS) <= set(MANAGED_SETTING_KEYS)
