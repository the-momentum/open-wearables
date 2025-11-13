import os
from pathlib import Path

import boto3
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv

from app.config import settings


AWS_BUCKET_NAME = settings.aws_bucket_name
AWS_REGION = settings.aws_region
DEFAULT_EXPIRATION = 300  # 5 minutes

try:
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
except NoCredentialsError:
    raise Exception("AWS credentials not configured")
