import base64
import json
import re
from logging import getLogger

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509 import load_pem_x509_certificate
from fastapi import status

from app.integrations.celery.tasks.process_aws_upload_task import process_aws_upload
from app.schemas import UploadDataResponse
from app.schemas.apple.apple_xml.aws import SNSNotification
from app.services.apple.apple_xml.aws_service import get_sns_client
from app.utils.structured_logging import log_structured

logger = getLogger(__name__)

_SNS_CERT_URL_RE = re.compile(r"^https://sns\.[a-z0-9-]+\.amazonaws\.com/SimpleNotificationService-[a-f0-9]+\.pem$")

_NOTIFICATION_FIELDS = ("Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type")
_SUBSCRIPTION_FIELDS = ("Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type")

_FIELD_MAP: dict[str, str] = {
    "Message": "message",
    "MessageId": "message_id",
    "Subject": "subject",
    "Timestamp": "timestamp",
    "TopicArn": "topic_arn",
    "Type": "message_type",
    "SubscribeURL": "subscribe_url",
    "Token": "token",
}


class SNSService:
    def __init__(self) -> None:
        self.sns_client = get_sns_client()

    def _build_string_to_sign(self, notification: SNSNotification) -> str:
        fields = _NOTIFICATION_FIELDS if notification.message_type == "Notification" else _SUBSCRIPTION_FIELDS

        pairs: list[str] = []
        for field in fields:
            attr = _FIELD_MAP[field]
            value = getattr(notification, attr)
            if value is None:
                continue
            pairs.append(f"{field}\n{value}")

        return "\n".join(pairs) + "\n"

    def _verify_signature(self, notification: SNSNotification) -> bool:
        cert_url = notification.signing_cert_url
        if not _SNS_CERT_URL_RE.match(cert_url):
            log_structured(
                logger,
                "warning",
                f"Untrusted signing cert URL: {cert_url}",
                provider="apple_xml",
                task="sns_notification",
            )
            return False

        response = requests.get(cert_url, timeout=10)
        response.raise_for_status()
        cert = load_pem_x509_certificate(response.content)
        public_key = cert.public_key()

        string_to_sign = self._build_string_to_sign(notification)
        decoded_signature = base64.b64decode(notification.signature)

        hash_algo = hashes.SHA256() if notification.signature_version == "2" else hashes.SHA1()

        try:
            # sns uses PKCS1v15 padding for the signature
            public_key.verify(decoded_signature, string_to_sign.encode("utf-8"), padding.PKCS1v15(), hash_algo)  # type: ignore[call-arg]
        except InvalidSignature:
            log_structured(
                logger,
                "warning",
                "SNS message signature verification failed",
                provider="apple_xml",
                task="sns_notification",
            )
            return False

        return True

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
            status_code=status.HTTP_202_ACCEPTED, response=f"{dispatched} tasks dispatched", user_id=None
        )

    def handle_sns_notification(self, notification: SNSNotification) -> UploadDataResponse:
        if not self._verify_signature(notification):
            return UploadDataResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                response="invalid SNS signature",
                user_id=None,
            )

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
