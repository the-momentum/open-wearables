"""
Tests for env-driven feature flags.

Tests cover:
- GET /api/v1/config - exposes data_lifecycle_enabled to the admin panel
- /api/v1/settings/archival - 503 when DATA_LIFECYCLE_ENABLED is off
- Celery beat schedule - archival and OW score tasks registered only when enabled
- Sleep session merges - OW sleep score not recomputed when OW_SCORES_ENABLED is off
"""

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.celery.core import create_celery
from app.services.event_record_service import event_record_service
from tests.factories import DeveloperFactory
from tests.utils import developer_auth_headers


@pytest.mark.parametrize("enabled", [True, False])
def test_config_exposes_data_lifecycle_flag(client: TestClient, db: Session, api_v1_prefix: str, enabled: bool) -> None:
    headers = developer_auth_headers(DeveloperFactory().id)

    with patch.object(settings, "data_lifecycle_enabled", enabled):
        response = client.get(f"{api_v1_prefix}/config", headers=headers)

    assert response.status_code == 200
    assert response.json()["data_lifecycle_enabled"] is enabled


class TestArchivalDisabled:
    @pytest.mark.parametrize(
        ("method", "path"),
        [("get", "/settings/archival"), ("put", "/settings/archival"), ("post", "/settings/archival/run")],
    )
    def test_returns_503(self, client: TestClient, db: Session, api_v1_prefix: str, method: str, path: str) -> None:
        headers = developer_auth_headers(DeveloperFactory().id)

        with patch.object(settings, "data_lifecycle_enabled", False):
            response = client.request(method, f"{api_v1_prefix}{path}", headers=headers, json={})

        assert response.status_code == 503
        assert "DATA_LIFECYCLE_ENABLED" in response.json()["detail"]

    def test_requires_auth_first(self, client: TestClient, api_v1_prefix: str) -> None:
        with patch.object(settings, "data_lifecycle_enabled", False):
            response = client.get(f"{api_v1_prefix}/settings/archival")

        assert response.status_code == 401

    @patch("app.api.routes.v1.archival.run_daily_archival")
    def test_enabled_passes_through(
        self, mock_task: MagicMock, client: TestClient, db: Session, api_v1_prefix: str
    ) -> None:
        mock_task.delay.return_value.id = "task-123"
        headers = developer_auth_headers(DeveloperFactory().id)

        with patch.object(settings, "data_lifecycle_enabled", True):
            response = client.post(f"{api_v1_prefix}/settings/archival/run", headers=headers)

        assert response.status_code == 202
        mock_task.delay.assert_called_once()


class TestBeatSchedule:
    GATED = {
        "run-daily-archival": "data_lifecycle_enabled",
        "fill-missing-sleep-scores": "ow_scores_enabled",
        "fill-missing-resilience-scores": "ow_scores_enabled",
    }

    def test_all_registered_when_enabled(self) -> None:
        with patch.multiple(settings, **dict.fromkeys(self.GATED.values(), True)):
            schedule = create_celery().conf.beat_schedule

        assert set(self.GATED) <= set(schedule)

    @pytest.mark.parametrize("flag", sorted(set(GATED.values())))
    def test_disabled_flag_drops_only_its_tasks(self, flag: str) -> None:
        flags = dict.fromkeys(self.GATED.values(), True) | {flag: False}
        with patch.multiple(settings, **flags):
            schedule = create_celery().conf.beat_schedule

        dropped = {task for task, task_flag in self.GATED.items() if task_flag == flag}
        assert not dropped & set(schedule)
        assert set(self.GATED) - dropped <= set(schedule)
        assert "sync-all-users-periodic" in schedule


def test_sleep_merge_skips_score_recompute_when_disabled(db: Session) -> None:
    with (
        patch.object(settings, "ow_scores_enabled", False),
        patch("app.services.event_record_service.sleep_score_service") as mock_scores,
    ):
        event_record_service._recompute_sleep_scores(db, uuid4(), {date(2026, 9, 1)})

    mock_scores.build_internal_sleep_scores.assert_not_called()
