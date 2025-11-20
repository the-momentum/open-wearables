import boto3
from botocore.exceptions import NoCredentialsError

from app.config import settings


AWS_BUCKET_NAME = settings.aws_bucket_name
AWS_REGION = settings.aws_region

try:
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
except NoCredentialsError:
    raise Exception("AWS credentials not configured")
