from cryptography.x509 import (
    Certificate,
    DNSName,
    load_pem_x509_certificate,
)
from cryptography.x509.verification import PolicyBuilder, Store
from logging import getLogger

import boto3
from botocore.exceptions import NoCredentialsError
import requests

from app.config import settings
from app.schemas.apple.apple_xml.aws import SNSConfirmRequest
from app.utils.structured_logging import log_structured

AWS_BUCKET_NAME = settings.aws_bucket_name
AWS_REGION = settings.aws_region
AWS_SNS_TOPIC_ARN = settings.aws_sns_topic_arn
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

class SNSService:
    def __init__(self):
        self.sns_client = boto3.client(
            "sns", region_name=AWS_REGION,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
        )

    def _verify_signature(self,
        signature: str,
        signing_cert_url: str,
    ) -> bool:
        cert_data = requests.get(signing_cert_url).text
        store = Store(load_pem_x509_certificate(cert_data.encode()))
        builder = PolicyBuilder().store(store)
        verifier = builder.build_server_verifier(DNSName(signing_cert_url))


    def confirm_sns_subscription(request: SNSConfirmRequest) -> bool:
        try:
            sns_client = boto3.client("sns", region_name=AWS_REGION)
            sns_client.confirm_subscription(
                TopicArn=request.topic_arn,
                Token=request.token,
                AuthenticateOnUnsubscribe="true",
            )

            return True
        except Exception as e:
            logger.error(f"Error confirming SNS subscription: {e}")
            return False