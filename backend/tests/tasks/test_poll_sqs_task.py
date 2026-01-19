"""
Tests for poll_sqs_task Celery tasks.

Tests SQS message polling and S3 event processing.
"""

import json
from typing import Generator
from unittest.mock import ANY, MagicMock, patch

import pytest

from app.integrations.celery.tasks.poll_sqs_task import poll_sqs_messages, poll_sqs_task


@pytest.fixture
def mock_sqs() -> Generator[MagicMock, None, None]:
    """Mock boto3 SQS client."""
    with patch("app.integrations.celery.tasks.poll_sqs_task.sqs") as mock:
        yield mock


@pytest.fixture
def mock_process_upload() -> Generator[MagicMock, None, None]:
    """Mock process_aws_upload task."""
    with patch("app.integrations.celery.tasks.poll_sqs_task.process_aws_upload") as mock:
        yield mock


class TestPollSqsMessages:
    """Test suite for poll_sqs_messages task."""

    def test_poll_sqs_no_messages(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test SQS returns empty messages list."""
        # Arrange
        mock_sqs.receive_message.return_value = {"Messages": []}

        # Act
        result = poll_sqs_messages()

        # Assert
        assert result == {"messages_processed": 0, "messages_failed": 0, "total_messages": 0}
        mock_process_upload.delay.assert_not_called()
        mock_sqs.delete_message.assert_not_called()

    def test_poll_sqs_single_message_processed(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test processing a single valid S3 event message."""
        # Arrange
        message = {
            "Body": json.dumps(
                {
                    "Records": [
                        {
                            "eventSource": "aws:s3",
                            "s3": {"bucket": {"name": "test-bucket"}, "object": {"key": "test-key"}},
                        },
                    ],
                },
            ),
            "ReceiptHandle": "receipt-123",
            "MessageId": "msg-123",
        }
        mock_sqs.receive_message.return_value = {"Messages": [message]}

        # Act
        result = poll_sqs_messages()

        # Assert
        assert result == {"messages_processed": 1, "messages_failed": 0, "total_messages": 1}
        mock_process_upload.delay.assert_called_once_with(
            bucket_name="test-bucket", object_key="test-key", user_id=None
        )
        mock_sqs.delete_message.assert_called_once()

    def test_poll_sqs_multiple_messages_processed(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test processing multiple S3 event messages."""
        # Arrange
        messages = [
            {
                "Body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventSource": "aws:s3",
                                "s3": {"bucket": {"name": "bucket-1"}, "object": {"key": "key-1"}},
                            },
                        ],
                    },
                ),
                "ReceiptHandle": "receipt-1",
                "MessageId": "msg-1",
            },
            {
                "Body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventSource": "aws:s3",
                                "s3": {"bucket": {"name": "bucket-2"}, "object": {"key": "key-2"}},
                            },
                        ],
                    },
                ),
                "ReceiptHandle": "receipt-2",
                "MessageId": "msg-2",
            },
            {
                "Body": json.dumps(
                    {
                        "Records": [
                            {
                                "eventSource": "aws:s3",
                                "s3": {"bucket": {"name": "bucket-3"}, "object": {"key": "key-3"}},
                            },
                        ],
                    },
                ),
                "ReceiptHandle": "receipt-3",
                "MessageId": "msg-3",
            },
        ]
        mock_sqs.receive_message.return_value = {"Messages": messages}

        # Act
        result = poll_sqs_messages()

        # Assert
        assert result == {"messages_processed": 3, "messages_failed": 0, "total_messages": 3}
        assert mock_process_upload.delay.call_count == 3
        assert mock_sqs.delete_message.call_count == 3

    def test_poll_sqs_invalid_message_format_skipped(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test non-JSON message is skipped, deleted, and counted as failed."""
        # Arrange
        message = {"Body": "not-valid-json{{{", "ReceiptHandle": "receipt-123", "MessageId": "msg-123"}
        mock_sqs.receive_message.return_value = {"Messages": [message]}

        # Act
        result = poll_sqs_messages()

        # Assert
        assert result == {"messages_processed": 0, "messages_failed": 1, "total_messages": 1}
        mock_process_upload.delay.assert_not_called()
        mock_sqs.delete_message.assert_called_once_with(
            QueueUrl=mock_sqs.receive_message.return_value.get("QueueUrl", None) or ANY,
            ReceiptHandle="receipt-123",
        )

    def test_poll_sqs_no_records_field(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test message without Records field is skipped and deleted."""
        # Arrange
        message = {
            "Body": json.dumps({"some": "other", "fields": "here"}),
            "ReceiptHandle": "receipt-123",
            "MessageId": "msg-123",
        }
        mock_sqs.receive_message.return_value = {"Messages": [message]}

        # Act
        result = poll_sqs_messages()

        # Assert
        assert result == {"messages_processed": 0, "messages_failed": 1, "total_messages": 1}
        mock_process_upload.delay.assert_not_called()
        mock_sqs.delete_message.assert_called_once()

    def test_poll_sqs_deletes_processed_messages(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test SQS delete_message is called with correct receipt handle."""
        # Arrange
        message = {
            "Body": json.dumps(
                {
                    "Records": [
                        {
                            "eventSource": "aws:s3",
                            "s3": {"bucket": {"name": "test-bucket"}, "object": {"key": "test-key"}},
                        },
                    ],
                },
            ),
            "ReceiptHandle": "unique-receipt-handle-789",
            "MessageId": "msg-456",
        }
        mock_sqs.receive_message.return_value = {"Messages": [message]}

        # Act
        poll_sqs_messages()

        # Assert
        # Verify delete was called with the correct receipt handle
        delete_calls = mock_sqs.delete_message.call_args_list
        assert len(delete_calls) == 1
        assert delete_calls[0].kwargs["ReceiptHandle"] == "unique-receipt-handle-789"

    def test_poll_sqs_connection_error_handled(self, mock_sqs: MagicMock, mock_process_upload: MagicMock) -> None:
        """Test SQS client raises exception, returns error status."""
        # Arrange
        mock_sqs.receive_message.side_effect = Exception("SQS connection failed")

        # Act
        result = poll_sqs_messages()

        # Assert
        assert result["status"] == "error"
        assert "SQS connection failed" in result["error"]
        mock_process_upload.delay.assert_not_called()


class TestPollSqsTask:
    """Test suite for poll_sqs_task wrapper task."""

    def test_poll_sqs_task_schedules_next_iteration(self, mock_sqs: MagicMock) -> None:
        """Test poll_sqs_task schedules next iteration."""
        # Arrange
        mock_sqs.receive_message.return_value = {"Messages": []}

        # Act - patch at module level for Celery task
        with patch(
            "app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task.apply_async",
        ) as mock_apply_async:
            result = poll_sqs_task(expiration_seconds=60, iterations_done=0)

            # Assert
            assert result == {"status": "scheduled", "iteration": 1}
            mock_apply_async.assert_called_once()
            call_kwargs = mock_apply_async.call_args.kwargs
            assert call_kwargs["kwargs"] == {
                "expiration_seconds": 60,
                "iterations_done": 1,
                "user_id": None,
            }
            assert call_kwargs["countdown"] == 20

    def test_poll_sqs_task_stops_after_max_iterations(self, mock_sqs: MagicMock) -> None:
        """Test poll_sqs_task stops after reaching max iterations."""
        # Arrange
        mock_sqs.receive_message.return_value = {"Messages": []}
        expiration_seconds = 60
        num_polls = expiration_seconds // 20  # 3 iterations

        # Act - patch at module level for Celery task
        with patch(
            "app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task.apply_async",
        ) as mock_apply_async:
            result = poll_sqs_task(expiration_seconds=expiration_seconds, iterations_done=num_polls)

            # Assert
            assert result == {"polls_completed": num_polls}
            mock_apply_async.assert_not_called()

    def test_poll_sqs_task_calls_poll_sqs_messages(self, mock_sqs: MagicMock) -> None:
        """Test poll_sqs_task calls poll_sqs_messages."""
        # Arrange
        mock_sqs.receive_message.return_value = {"Messages": []}

        # Act - patch at module level for Celery task
        with (
            patch("app.integrations.celery.tasks.poll_sqs_task.poll_sqs_task.apply_async"),
            patch("app.integrations.celery.tasks.poll_sqs_task.poll_sqs_messages") as mock_poll,
        ):
            poll_sqs_task(expiration_seconds=60, iterations_done=0)

            # Assert
            mock_poll.assert_called_once()
