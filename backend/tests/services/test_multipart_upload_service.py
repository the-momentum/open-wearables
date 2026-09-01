"""Tests for the Apple XML multipart upload service."""

from logging import getLogger
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.config import settings
from app.schemas.providers.apple.apple_xml import CompletedPart
from app.services.apple.apple_xml import multipart_upload_service as mp_module
from app.services.apple.apple_xml.multipart_upload_service import MultipartUploadService

USER_ID = "user-123"

# The service resolves its S3 clients per call via the module-level accessors, so tests
# inject their mocks here rather than on the instance. The autouse fixture points the
# accessors at this holder and resets it between tests.
_clients: dict[str, MagicMock | None] = {"internal": None, "public": None}


@pytest.fixture(autouse=True)
def _patch_client_accessors(monkeypatch: pytest.MonkeyPatch) -> None:
    _clients["internal"] = None
    _clients["public"] = None
    monkeypatch.setattr(mp_module, "get_s3_client", lambda: _clients["internal"])
    monkeypatch.setattr(mp_module, "get_public_s3_client", lambda: _clients["public"])


def _service(client: MagicMock | None) -> MultipartUploadService:
    # By default the public (presigning) client is the same object, so tests that assert on
    # `client` see the presigned calls too. TestPublicEndpoint overrides it with a distinct mock.
    _clients["internal"] = client
    _clients["public"] = client
    return MultipartUploadService(getLogger(__name__))


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "Operation")


class TestCreate:
    def test_create_returns_upload_metadata(self) -> None:
        client = MagicMock()
        client.create_multipart_upload.return_value = {"UploadId": "upload-1"}
        service = _service(client)

        result = service.create_upload(USER_ID, "export.xml", "application/xml", file_size=50 * 1024 * 1024)

        assert result.upload_id == "upload-1"
        assert result.key.startswith(f"{USER_ID}/raw/")
        assert result.bucket == "test-bucket"
        assert result.part_size > 0
        client.create_multipart_upload.assert_called_once()

    def test_create_without_client_raises_503(self) -> None:
        service = _service(None)
        with pytest.raises(HTTPException) as exc:
            service.create_upload(USER_ID, "export.xml", "application/xml", file_size=1024 * 1024 * 5)
        assert exc.value.status_code == 503

    def test_create_without_bucket_raises_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(settings, "aws_bucket_name", None)
        client = MagicMock()
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.create_upload(USER_ID, "export.xml", "application/xml", file_size=1024 * 1024 * 5)

        assert exc.value.status_code == 503
        assert exc.value.detail == "S3 bucket not configured"
        client.create_multipart_upload.assert_not_called()

    def test_create_transient_client_error_raises_503(self) -> None:
        client = MagicMock()
        client.create_multipart_upload.side_effect = _client_error("InternalError")
        service = _service(client)
        with pytest.raises(HTTPException) as exc:
            service.create_upload(USER_ID, "export.xml", "application/xml", file_size=1024 * 1024 * 5)
        assert exc.value.status_code == 503


class TestSignParts:
    def test_sign_parts_returns_one_url_per_part(self) -> None:
        client = MagicMock()
        client.generate_presigned_url.side_effect = ["url-1", "url-2", "url-3"]
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"

        result = service.sign_upload_parts(USER_ID, key, "upload-1", [1, 2, 3], expiration_seconds=3600)

        assert [p.part_number for p in result.urls] == [1, 2, 3]
        assert [p.url for p in result.urls] == ["url-1", "url-2", "url-3"]
        assert client.generate_presigned_url.call_count == 3

    def test_sign_parts_rejects_foreign_key(self) -> None:
        service = _service(MagicMock())
        with pytest.raises(HTTPException) as exc:
            service.sign_upload_parts(USER_ID, "other-user/raw/x.xml", "upload-1", [1], expiration_seconds=3600)
        assert exc.value.status_code == 403


class TestComplete:
    def test_complete_sorts_parts_and_returns_key(self) -> None:
        client = MagicMock()
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"
        parts = [
            CompletedPart(part_number=2, etag="etag-2"),
            CompletedPart(part_number=1, etag="etag-1"),
        ]

        returned_key = service.complete_upload(USER_ID, key, "upload-1", parts)

        assert returned_key == key
        _, kwargs = client.complete_multipart_upload.call_args
        sent_parts = kwargs["MultipartUpload"]["Parts"]
        assert [p["PartNumber"] for p in sent_parts] == [1, 2]

    def test_complete_preserves_quoted_etag(self) -> None:
        client = MagicMock()
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"

        service.complete_upload(
            USER_ID,
            key,
            "upload-1",
            [CompletedPart(part_number=1, etag='  "etag-1"  ')],
        )

        sent_parts = client.complete_multipart_upload.call_args.kwargs["MultipartUpload"]["Parts"]
        assert sent_parts == [{"ETag": '"etag-1"', "PartNumber": 1}]

    def test_complete_rejects_foreign_key(self) -> None:
        service = _service(MagicMock())
        with pytest.raises(HTTPException) as exc:
            service.complete_upload(
                USER_ID,
                "other/raw/x.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="e")],
            )
        assert exc.value.status_code == 403

    def test_complete_missing_upload_raises_404(self) -> None:
        client = MagicMock()
        client.complete_multipart_upload.side_effect = _client_error("NoSuchUpload")
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"
        with pytest.raises(HTTPException) as exc:
            service.complete_upload(USER_ID, key, "upload-1", [CompletedPart(part_number=1, etag="e")])
        assert exc.value.status_code == 404

    def test_complete_invalid_part_raises_400(self) -> None:
        client = MagicMock()
        client.complete_multipart_upload.side_effect = _client_error("InvalidPart")
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"

        with pytest.raises(HTTPException) as exc:
            service.complete_upload(USER_ID, key, "upload-1", [CompletedPart(part_number=1, etag="e")])

        assert exc.value.status_code == 400

    def test_complete_access_denied_raises_403(self) -> None:
        client = MagicMock()
        client.complete_multipart_upload.side_effect = _client_error("AccessDenied")
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"

        with pytest.raises(HTTPException) as exc:
            service.complete_upload(USER_ID, key, "upload-1", [CompletedPart(part_number=1, etag="e")])

        assert exc.value.status_code == 403

    def test_complete_accepts_explicit_bucket_for_background_job(self) -> None:
        client = MagicMock()
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"

        service.complete_upload(
            USER_ID,
            key,
            "upload-1",
            [CompletedPart(part_number=1, etag="e")],
            bucket_name="queued-bucket",
        )

        assert client.complete_multipart_upload.call_args.kwargs["Bucket"] == "queued-bucket"


class TestAbort:
    def test_abort_calls_s3(self) -> None:
        client = MagicMock()
        service = _service(client)
        key = f"{USER_ID}/raw/export.xml"

        service.abort_upload(USER_ID, key, "upload-1")

        client.abort_multipart_upload.assert_called_once_with(Bucket="test-bucket", Key=key, UploadId="upload-1")

    def test_abort_rejects_foreign_key(self) -> None:
        service = _service(MagicMock())
        with pytest.raises(HTTPException) as exc:
            service.abort_upload(USER_ID, "other/raw/x.xml", "upload-1")
        assert exc.value.status_code == 403

    def test_abort_is_idempotent_when_upload_no_longer_exists(self) -> None:
        client = MagicMock()
        client.abort_multipart_upload.side_effect = _client_error("NoSuchUpload")
        service = _service(client)

        service.abort_upload(USER_ID, f"{USER_ID}/raw/export.xml", "upload-1")

        client.abort_multipart_upload.assert_called_once()


class TestValidateCompletionRequest:
    def test_returns_configured_bucket_when_uploaded_parts_match(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": "etag-1"}],
            "IsTruncated": False,
        }
        service = _service(client)

        assert (
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )
            == "test-bucket"
        )

    def test_rejects_foreign_key_before_queueing(self) -> None:
        service = _service(MagicMock())

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                "other/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 403

    def test_rejects_parts_that_do_not_match_storage(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": "stored-etag"}],
            "IsTruncated": False,
        }
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="different-etag")],
            )

        assert exc.value.status_code == 400

    def test_rejects_quoted_and_unquoted_etag_mismatch(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": '"etag-1"'}],
            "IsTruncated": False,
        }
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 400

    def test_accepts_matching_quoted_etags(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": '"etag-1"'}],
            "IsTruncated": False,
        }
        service = _service(client)

        bucket = service.validate_completion_request(
            USER_ID,
            f"{USER_ID}/raw/export.xml",
            "upload-1",
            [CompletedPart(part_number=1, etag='"etag-1"')],
        )

        assert bucket == "test-bucket"

    def test_missing_upload_is_reported_as_404(self) -> None:
        client = MagicMock()
        client.list_parts.side_effect = _client_error("NoSuchUpload")
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 404

    def test_non_advancing_pagination_marker_raises_502_and_does_not_hang(self) -> None:
        # A misbehaving S3-compatible server that keeps the same NextPartNumberMarker must
        # not wedge the request thread in an infinite loop.
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": "etag-1"}],
            "IsTruncated": True,
            "NextPartNumberMarker": 1,
        }
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 502

    def test_non_numeric_pagination_marker_raises_502(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": 1, "ETag": "etag-1"}],
            "IsTruncated": True,
            "NextPartNumberMarker": "not-a-number",
        }
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 502

    def test_invalid_part_number_from_storage_raises_502(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": [{"PartNumber": "not-a-number", "ETag": "etag-1"}],
            "IsTruncated": False,
        }
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 502

    def test_invalid_parts_collection_from_storage_raises_502(self) -> None:
        client = MagicMock()
        client.list_parts.return_value = {
            "Parts": None,
            "IsTruncated": False,
        }
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 502

    def test_repeated_part_across_pages_raises_502(self) -> None:
        client = MagicMock()
        client.list_parts.side_effect = [
            {
                "Parts": [{"PartNumber": 1, "ETag": "etag-1"}],
                "IsTruncated": True,
                "NextPartNumberMarker": 1,
            },
            {
                "Parts": [{"PartNumber": 1, "ETag": "etag-1"}],
                "IsTruncated": False,
            },
        ]
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 502

    def test_truncated_listing_is_bounded_by_maximum_page_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mp_module, "MAX_PARTS", 3)
        client = MagicMock()
        client.list_parts.side_effect = [
            {
                "Parts": [{"PartNumber": page, "ETag": f"etag-{page}"}],
                "IsTruncated": True,
                "NextPartNumberMarker": page,
            }
            for page in range(1, 4)
        ]
        service = _service(client)

        with pytest.raises(HTTPException) as exc:
            service.validate_completion_request(
                USER_ID,
                f"{USER_ID}/raw/export.xml",
                "upload-1",
                [CompletedPart(part_number=1, etag="etag-1")],
            )

        assert exc.value.status_code == 502
        assert client.list_parts.call_count == 3


class TestPublicEndpoint:
    """Presigned part URLs must be generated by the browser-facing (public) client, while
    the backend-side create/complete/abort calls use the internal client."""

    def test_sign_uses_public_client(self) -> None:
        internal = MagicMock()
        public = MagicMock()
        public.generate_presigned_url.return_value = "https://localhost:8333/signed"
        _clients["internal"] = internal
        _clients["public"] = public
        service = MultipartUploadService(getLogger(__name__))

        key = f"{USER_ID}/raw/export.xml"
        result = service.sign_upload_parts(USER_ID, key, "upload-1", [1, 2], expiration_seconds=3600)

        assert len(result.urls) == 2
        assert public.generate_presigned_url.call_count == 2
        internal.generate_presigned_url.assert_not_called()

    def test_create_uses_internal_client(self) -> None:
        internal = MagicMock()
        internal.create_multipart_upload.return_value = {"UploadId": "upload-1"}
        public = MagicMock()
        _clients["internal"] = internal
        _clients["public"] = public
        service = MultipartUploadService(getLogger(__name__))

        service.create_upload(USER_ID, "export.xml", "application/xml", file_size=50 * 1024 * 1024)

        internal.create_multipart_upload.assert_called_once()
        public.create_multipart_upload.assert_not_called()

    def test_sign_falls_back_to_internal_client(self) -> None:
        internal = MagicMock()
        internal.generate_presigned_url.return_value = "https://storage/signed"
        service = _service(internal)
        _clients["public"] = None

        key = f"{USER_ID}/raw/export.xml"
        service.sign_upload_parts(USER_ID, key, "upload-1", [1], expiration_seconds=3600)

        internal.generate_presigned_url.assert_called_once()
