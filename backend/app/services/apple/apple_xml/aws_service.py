from logging import getLogger

import boto3
from botocore.exceptions import NoCredentialsError

from app.config import settings
from app.utils.structured_logging import log_structured

AWS_BUCKET_NAME = settings.aws_bucket_name
AWS_REGION = settings.aws_region
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


def get_sns_client():  # noqa: ANN201
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
