"""Tests for SNS notification dispatch gating by completion mode."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.schemas.providers.apple.apple_xml import SNSNotification
from app.services.apple.apple_xml.sns_service import SNSService

S3_RECORDS = {
    "Records": [
        {
            "eventSource": "aws:s3",
            "s3": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "user-123/raw/export.xml"},
            },
        }
    ]
}


def _notification(message: dict) -> SNSNotification:
    return SNSNotification.model_validate(
        {
            "Type": "Notification",
            "MessageId": "m-1",
            "TopicArn": "arn:aws:sns:eu-north-1:123456789012:owear",
            "Message": json.dumps(message),
            "Timestamp": "2026-01-01T00:00:00.000Z",
            "Signature": "sig",
            "SignatureVersion": "1",
            "SigningCertURL": "https://sns.eu-north-1.amazonaws.com/cert.pem",
        }
    )


def _service() -> SNSService:
    service = SNSService()
    service.sns_client = MagicMock()
    return service


class TestProcessS3Notification:
    def test_client_mode_does_not_dispatch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "apple_xml_upload_completion_mode", "client")
        service = _service()

        with patch("app.services.apple.apple_xml.sns_service.process_aws_upload") as mock_task:
            result = service._process_s3_notification(_notification(S3_RECORDS))

        assert result.status_code == 200
        assert "client-driven" in result.response
        mock_task.delay.assert_not_called()

    def test_sns_mode_dispatches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "apple_xml_upload_completion_mode", "sns")
        service = _service()

        with patch("app.services.apple.apple_xml.sns_service.process_aws_upload") as mock_task:
            result = service._process_s3_notification(_notification(S3_RECORDS))

        assert result.status_code == 202
        mock_task.delay.assert_called_once_with(
            bucket_name="test-bucket", object_key="user-123/raw/export.xml", user_id="user-123"
        )

    def test_test_event_ignored_in_any_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "apple_xml_upload_completion_mode", "sns")
        service = _service()

        with patch("app.services.apple.apple_xml.sns_service.process_aws_upload") as mock_task:
            result = service._process_s3_notification(_notification({"Event": "s3:TestEvent"}))

        assert result.status_code == 200
        assert "TestEvent" in result.response
        mock_task.delay.assert_not_called()
