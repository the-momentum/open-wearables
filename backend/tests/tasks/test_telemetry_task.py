"""Tests for the send_telemetry_ping Celery task."""

from unittest.mock import MagicMock, patch

import httpx
from sqlalchemy.orm import Session

from app.integrations.celery.tasks.telemetry_task import send_telemetry_ping


class TestSendTelemetryPingTask:
    @patch("app.integrations.celery.tasks.telemetry_task.telemetry_service")
    @patch("app.integrations.celery.tasks.telemetry_task.SessionLocal")
    def test_sends_daily_ping(
        self,
        mock_session_local: MagicMock,
        mock_service: MagicMock,
        db: Session,
    ) -> None:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_service.send_ping.return_value = "sent"

        result = send_telemetry_ping(event="daily")

        assert result == "sent"
        mock_service.send_ping.assert_called_once_with(db, event="daily")

    @patch("app.integrations.celery.tasks.telemetry_task.telemetry_service")
    @patch("app.integrations.celery.tasks.telemetry_task.SessionLocal")
    def test_passes_startup_event_through(
        self,
        mock_session_local: MagicMock,
        mock_service: MagicMock,
        db: Session,
    ) -> None:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_service.send_ping.return_value = "not_due"

        result = send_telemetry_ping(event="startup")

        assert result == "not_due"
        mock_service.send_ping.assert_called_once_with(db, event="startup")

    @patch("app.integrations.celery.tasks.telemetry_task.telemetry_service")
    @patch("app.integrations.celery.tasks.telemetry_task.SessionLocal")
    def test_delivery_errors_are_swallowed(
        self,
        mock_session_local: MagicMock,
        mock_service: MagicMock,
        db: Session,
    ) -> None:
        """Telemetry is best-effort: a failed delivery must never raise.

        The hourly beat schedule acts as the natural retry - the ping stays
        due until a delivery succeeds.
        """
        mock_session_local.return_value.__enter__ = MagicMock(return_value=db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=None)
        mock_service.send_ping.side_effect = httpx.ConnectError("connection refused")

        result = send_telemetry_ping(event="daily")

        assert result == "failed"
