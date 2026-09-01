"""Tests for the Apple XML presigned-POST service, focused on SSE enforcement."""

from logging import getLogger
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.config import settings
from app.schemas.providers.apple.apple_xml import PresignedURLRequest
from app.services.apple.apple_xml import presigned_url_service as presign_module
from app.services.apple.apple_xml.presigned_url_service import PresignedURLService

_clients: dict[str, MagicMock | None] = {"internal": None, "public": None}


@pytest.fixture(autouse=True)
def _patch_client_accessors(monkeypatch: pytest.MonkeyPatch) -> None:
    _clients["internal"] = None
    _clients["public"] = None
    monkeypatch.setattr(presign_module, "get_s3_client", lambda: _clients["internal"])
    monkeypatch.setattr(presign_module, "get_public_s3_client", lambda: _clients["public"])


def _service(client: MagicMock) -> PresignedURLService:
    # Same object for the presigning client by default, so single-client assertions hold.
    _clients["internal"] = client
    _clients["public"] = client
    return PresignedURLService(getLogger(__name__))


def _client() -> MagicMock:
    client = MagicMock()
    client.head_bucket.return_value = {}
    client.generate_presigned_post.return_value = {"url": "https://storage/bucket", "fields": {}}
    return client


class TestPublicEndpoint:
    """The presigned form must come from the browser-facing (public) client, while bucket
    validation (head_bucket) uses the internal client."""

    def test_presign_uses_public_client_and_validates_via_internal(self) -> None:
        internal = MagicMock()
        internal.head_bucket.return_value = {}
        public = MagicMock()
        public.generate_presigned_post.return_value = {"url": "http://localhost:8333/bucket", "fields": {}}

        _clients["internal"] = internal
        _clients["public"] = public
        service = PresignedURLService(getLogger(__name__))

        service.create_presigned_url("user-1", PresignedURLRequest(filename="export.xml"))

        internal.head_bucket.assert_called_once()
        public.generate_presigned_post.assert_called_once()
        internal.generate_presigned_post.assert_not_called()

    def test_missing_public_client_falls_back_to_internal(self) -> None:
        internal = _client()
        service = _service(internal)
        _clients["public"] = None

        service.create_presigned_url("user-1", PresignedURLRequest(filename="export.xml"))

        internal.generate_presigned_post.assert_called_once()


def test_missing_bucket_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "aws_bucket_name", None)
    client = _client()

    with pytest.raises(HTTPException) as exc:
        _service(client).create_presigned_url("user-1", PresignedURLRequest(filename="export.xml"))

    assert exc.value.status_code == 503
    assert exc.value.detail == "S3 bucket not configured"
    client.head_bucket.assert_not_called()
