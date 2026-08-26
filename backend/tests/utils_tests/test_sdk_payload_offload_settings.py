"""Tests for the SDK_PAYLOAD_S3_OFFLOAD startup validation."""

import pytest
from pydantic import ValidationError

from app.config import Settings


class TestSdkPayloadOffloadValidation:
    """Misconfiguration must fail at startup, not degrade to inline payloads at runtime."""

    def test_offload_without_a_bucket_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="SDK_PAYLOAD_S3_OFFLOAD"):
            Settings(sdk_payload_s3_offload=True, raw_payload_s3_bucket=None, aws_bucket_name=None)

    def test_bucket_is_not_required_when_offload_is_off(self) -> None:
        settings = Settings(sdk_payload_s3_offload=False, raw_payload_s3_bucket=None, aws_bucket_name=None)

        assert settings.raw_payload_bucket is None

    def test_offload_does_not_require_s3_archival(self) -> None:
        """Archival is a debugging aid and must not gate queue reliability."""
        settings = Settings(
            sdk_payload_s3_offload=True,
            raw_payload_storage="disabled",
            raw_payload_s3_bucket=None,
            aws_bucket_name="open-wearables",
        )

        assert settings.sdk_payload_s3_offload is True


class TestRawPayloadBucket:
    def test_prefers_the_dedicated_bucket(self) -> None:
        settings = Settings(raw_payload_s3_bucket="payloads", aws_bucket_name="open-wearables")

        assert settings.raw_payload_bucket == "payloads"

    def test_falls_back_to_the_aws_bucket(self) -> None:
        settings = Settings(raw_payload_s3_bucket=None, aws_bucket_name="open-wearables")

        assert settings.raw_payload_bucket == "open-wearables"
