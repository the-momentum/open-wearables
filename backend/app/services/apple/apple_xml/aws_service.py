from logging import getLogger
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.config import settings
from app.integrations.celery.tasks.process_aws_upload_task import process_aws_upload
from app.integrations.redis_client import get_redis_client
from app.schemas.apple.apple_xml.aws import SNSNotification
from app.utils.structured_logging import log_structured

AWS_BUCKET_NAME = settings.aws_bucket_name
AWS_REGION = settings.aws_region
AWS_SNS_TOPIC_ARN = settings.aws_sns_topic_arn
REDIS_PREFIX = "sns:pending:"
logger = getLogger(__name__)


def get_s3_client():  # noqa: ANN201
    try:
        return boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
        )
    except (NoCredentialsError, AttributeError):
        log_structured(logger, "warning", "AWS credentials not configured")
        return None

def get_sns_client(): # noqa: ANN201
    try:
        return boto3.client(
            "sns",
            region_name=AWS_REGION,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
        )
    except (NoCredentialsError, AttributeError):
        log_structured(logger, "warning", "AWS credentials not configured")
        return None


class SNSService:
    def __init__(self) -> None:
        self.sns_client = get_sns_client()
        self.s3_client = get_s3_client()
        self.redis_client = get_redis_client()

    def confirm_sns_subscription(self, notification: SNSNotification) -> bool:
        try:
            sns_client = boto3.client("sns", region_name=AWS_REGION)
            sns_client.confirm_subscription(
                TopicArn=notification.topic_arn,
                Token=notification.token,
                AuthenticateOnUnsubscribe="true",
            )
            return True
        except Exception as e:
            logger.error(f"Error confirming SNS subscription: {e}")
            return False

    def process_pending_uploads(self) -> dict[str, Any]:
        """Scan all pending uploads in Redis, check if the file exists in S3, and dispatch processing."""
        if not self.s3_client:
            logger.error("S3 client not configured, cannot process pending uploads")
            return {"status": "error", "reason": "s3_not_configured"}

        keys = self.redis_client.keys(f"{REDIS_PREFIX}*")
        dispatched = 0

        for redis_key in keys:
            user_id = self.redis_client.get(redis_key)
            if not user_id:
                continue

            file_key = redis_key.removeprefix(REDIS_PREFIX)

            # Check if the file with key in redis was uploaded to S3
            try:
                self.s3_client.head_object(Bucket=AWS_BUCKET_NAME, Key=file_key)
            except ClientError:
                continue

            process_aws_upload.delay(
                bucket_name=AWS_BUCKET_NAME,
                object_key=file_key,
                user_id=user_id,
            )
            self.redis_client.delete(redis_key)
            dispatched += 1

            log_structured(
                logger,
                "info",
                f"Dispatched processing for {file_key} (user {user_id})",
                provider="apple_xml",
                task="sns_notification",
            )

        return {"status": "ok", "tasks_dispatched": dispatched}

    def handle_sns_notification(self, notification: SNSNotification) -> bool:
        if notification.message_type == "SubscriptionConfirmation":
            return self.confirm_sns_subscription(notification)
        elif notification.message_type == "Notification":
            return self.process_pending_uploads()
        else:
            return False


sns_service = SNSService()