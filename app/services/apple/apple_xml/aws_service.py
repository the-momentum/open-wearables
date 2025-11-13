import os
from pathlib import Path

import boto3
from botocore.exceptions import NoCredentialsError
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[4] / "config" / ".env")

AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "open-wearables-xml")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
DEFAULT_EXPIRATION = 300  # 5 minutes

try:
    s3_client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        # Credentials should be set via environment variables or IAM roles
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
except NoCredentialsError:
    raise Exception("AWS credentials not configured")

