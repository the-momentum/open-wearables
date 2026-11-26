"""Spec'd stand-ins for boto3 clients."""

import functools
from typing import Any
from unittest.mock import MagicMock

import boto3


@functools.cache
def _real_client(service: str) -> Any:
    """A real, never-called client to spec from: botocore builds client classes at runtime.

    Built from its own Session, so tests that patch ``boto3.client`` don't end up caching their mock here.
    """
    session = boto3.session.Session(
        aws_access_key_id="testing", aws_secret_access_key="testing", region_name="us-east-1"
    )
    return session.client(service)


def mock_s3_client() -> MagicMock:
    """A mock that rejects attributes a real S3 client doesn't have.

    ``spec``, not autospec: botocore methods all take ``**kwargs``, so autospec would check no
    signatures and costs about 28 ms per mock instead of 0.4 ms.
    """
    return MagicMock(spec=_real_client("s3"))


def mock_sns_client() -> MagicMock:
    """Like ``mock_s3_client``, for SNS."""
    return MagicMock(spec=_real_client("sns"))
