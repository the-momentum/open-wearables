"""Tests for the raw-payload replay script."""

import sys

import pytest

from scripts.replay_raw_payloads import parse_args


def test_shared_s3_endpoint_is_used_as_replay_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAW_PAYLOAD_S3_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("OPEN_WEARABLES_API_KEY", "test-api-key")
    monkeypatch.setenv("AWS_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(sys, "argv", ["replay_raw_payloads.py", "--user-id", "user-1"])

    args = parse_args()

    assert args.s3_endpoint_url == "http://minio:9000"
