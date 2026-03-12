import json
from logging import getLogger
from typing import Any

import boto3

from app.integrations.celery.tasks.process_aws_upload_task import process_aws_upload
from app.schemas.apple.apple_xml.aws import SNSNotification
from app.services.apple.apple_xml.aws_service import AWS_REGION, get_sns_client
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)


class SNSService:
    def __init__(self) -> None:
        self.sns_client = get_sns_client()

    def _confirm_subscription(self, notification: SNSNotification) -> dict[str, Any]:
        try:
            sns_client = boto3.client("sns", region_name=AWS_REGION)
            sns_client.confirm_subscription(
                TopicArn=notification.topic_arn,
                Token=notification.token,
                AuthenticateOnUnsubscribe="true",
            )
            return {"status": "subscription_confirmed"}
        except Exception as e:
            logger.error(f"Error confirming SNS subscription: {e}")
            return {"status": "error", "reason": str(e)}

    def _process_s3_notification(self, notification: SNSNotification) -> dict[str, Any]:
        message_body = json.loads(notification.message)

        if message_body.get("Event") == "s3:TestEvent":
            logger.info("Received S3 test event, ignoring")
            return {"status": "ignored", "reason": "s3:TestEvent"}

        records = message_body.get("Records", [])
        dispatched = 0

        for record in records:
            if record.get("eventSource") != "aws:s3":
                continue

            bucket_name = record["s3"]["bucket"]["name"]
            object_key = record["s3"]["object"]["key"]

            object_key_parts = object_key.split("/")
            user_id = object_key_parts[0] if len(object_key_parts) >= 3 else None

            process_aws_upload.delay(
                bucket_name=bucket_name,
                object_key=object_key,
                user_id=user_id,
            )
            dispatched += 1

            log_structured(
                logger,
                "info",
                f"Dispatched processing for {object_key} (user {user_id})",
                provider="apple_xml",
                task="sns_notification",
            )

        return {"status": "ok", "tasks_dispatched": dispatched}

    def handle_sns_notification(self, notification: SNSNotification) -> dict[str, Any]:
        if notification.message_type == "SubscriptionConfirmation":
            return self._confirm_subscription(notification)
        if notification.message_type == "Notification":
            return self._process_s3_notification(notification)
        return {"status": "ignored", "reason": f"unknown type: {notification.message_type}"}


sns_service = SNSService()