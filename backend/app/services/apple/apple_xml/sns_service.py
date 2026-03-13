import json
from logging import getLogger

from fastapi import status

from app.integrations.celery.tasks.process_aws_upload_task import process_aws_upload
from app.schemas import UploadDataResponse
from app.schemas.apple.apple_xml.aws import SNSNotification
from app.services.apple.apple_xml.aws_service import get_sns_client
from app.utils.structured_logging import log_structured


logger = getLogger(__name__)


class SNSService:
    def __init__(self) -> None:
        self.sns_client = get_sns_client()

    def _confirm_subscription(self, notification: SNSNotification) -> UploadDataResponse:
        try:
            self.sns_client.confirm_subscription(
                TopicArn=notification.topic_arn,
                Token=notification.token,
                AuthenticateOnUnsubscribe="true",
            )
            return UploadDataResponse(status_code=status.HTTP_200_OK, response="subscription_confirmed", user_id=None)
        except Exception as e:
            log_structured(
                logger,
                "error",
                f"Error confirming SNS subscription: {e}",
                provider="apple_xml",
                task="sns_notification",
            )
            return UploadDataResponse(status_code=status.HTTP_400_BAD_REQUEST, response=str(e), user_id=None)

    def _process_s3_notification(self, notification: SNSNotification) -> UploadDataResponse:
        message_body = json.loads(notification.message)

        if message_body.get("Event") == "s3:TestEvent":
            log_structured(
                logger, "info", "Received S3 test event, ignoring", provider="apple_xml", task="sns_notification"
            )
            return UploadDataResponse(status_code=status.HTTP_200_OK, response="ignored: s3:TestEvent", user_id=None)

        records = message_body.get("Records", [])
        dispatched = 0

        for record in records:
            if record.get("eventSource") != "aws:s3":
                continue

            bucket_name = record["s3"]["bucket"]["name"]
            object_key = record["s3"]["object"]["key"]

            object_key_parts = object_key.split("/")
            user_id = object_key_parts[0] if len(object_key_parts) >= 3 else None
            if not user_id:
                log_structured(
                    logger,
                    "warning",
                    f"No user_id found in object key: {object_key}",
                    provider="apple_xml",
                    task="sns_notification",
                )
                continue

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

        return UploadDataResponse(
            status_code=status.HTTP_200_OK, response=f"{dispatched} tasks dispatched", user_id=None
        )

    def handle_sns_notification(self, notification: SNSNotification) -> UploadDataResponse:
        if notification.message_type == "SubscriptionConfirmation":
            return self._confirm_subscription(notification)
        if notification.message_type == "Notification":
            return self._process_s3_notification(notification)
        return UploadDataResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            response=f"unknown message type: {notification.message_type}",
            user_id=None,
        )


sns_service = SNSService()
