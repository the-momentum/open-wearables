"""Tests for multipart upload schema helpers."""

from math import ceil

import pytest
from pydantic import ValidationError

from app.config import settings
from app.schemas.providers.apple.apple_xml import (
    DEFAULT_PART_SIZE,
    MAX_FILE_SIZE,
    MAX_PART_SIZE,
    MAX_PARTS,
    MIN_PART_SIZE,
    MultipartCreateRequest,
    MultipartSignRequest,
    recommended_part_size,
)
from app.schemas.providers.apple.apple_xml.multipart import (
    DEFAULT_EXPIRATION_SECONDS,
    MAX_EXPIRATION_SECONDS,
)


class TestRecommendedPartSize:
    def test_product_file_size_limit_comes_from_settings(self) -> None:
        assert settings.apple_xml_max_file_size_bytes == MAX_FILE_SIZE

    def test_small_file_uses_default_part_size(self) -> None:
        assert recommended_part_size(50 * 1024 * 1024) == DEFAULT_PART_SIZE

    def test_runtime_default_is_configurable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        configured_size = 64 * 1024 * 1024
        monkeypatch.setattr(settings, "apple_xml_multipart_part_size_bytes", configured_size)

        assert recommended_part_size(50 * 1024 * 1024) == configured_size

    def test_file_at_default_capacity_stays_default(self) -> None:
        # DEFAULT_PART_SIZE * MAX_PARTS is the largest file the default handles
        capacity = DEFAULT_PART_SIZE * MAX_PARTS
        assert recommended_part_size(capacity) == DEFAULT_PART_SIZE

    def test_large_file_grows_part_size_within_part_limit(self) -> None:
        # 3 TiB would need > 10,000 parts at the default size
        file_size = 3 * 1024 * 1024 * 1024 * 1024
        part_size = recommended_part_size(file_size)

        assert part_size > DEFAULT_PART_SIZE
        assert ceil(file_size / part_size) <= MAX_PARTS
        # part size is aligned to a whole number of MiB
        assert part_size % (1024 * 1024) == 0

    def test_part_size_never_below_minimum(self) -> None:
        assert recommended_part_size(1) >= MIN_PART_SIZE

    def test_part_size_never_above_maximum(self) -> None:
        # Keep the generic sizing helper safe even beyond the product upload cap.
        assert recommended_part_size(5 * 1024 * 1024 * 1024 * 1024) <= MAX_PART_SIZE

    def test_default_needs_at_most_52_parts_at_product_limit(self) -> None:
        assert ceil(MAX_FILE_SIZE / DEFAULT_PART_SIZE) == 52


class TestMultipartCreateRequest:
    def test_accepts_product_file_size_limit(self) -> None:
        request = MultipartCreateRequest(filename="export.xml", file_size=MAX_FILE_SIZE)
        assert request.file_size == MAX_FILE_SIZE

    def test_rejects_file_above_product_limit(self) -> None:
        with pytest.raises(ValidationError):
            MultipartCreateRequest(filename="export.xml", file_size=MAX_FILE_SIZE + 1)


class TestMultipartSignRequest:
    def test_default_expiration_supports_slow_large_uploads(self) -> None:
        request = MultipartSignRequest(key="u/raw/x.xml", upload_id="up", part_numbers=[1])

        assert request.expiration_seconds == 24 * 60 * 60

    def test_accepts_maximum_expiration(self) -> None:
        request = MultipartSignRequest(
            key="u/raw/x.xml",
            upload_id="up",
            part_numbers=[1],
            expiration_seconds=MAX_EXPIRATION_SECONDS,
        )

        assert request.expiration_seconds == 24 * 60 * 60

    def test_rejects_expiration_above_application_maximum(self) -> None:
        with pytest.raises(ValidationError):
            MultipartSignRequest(
                key="u/raw/x.xml",
                upload_id="up",
                part_numbers=[1],
                expiration_seconds=MAX_EXPIRATION_SECONDS + 1,
            )

    def test_accepts_valid_part_numbers(self) -> None:
        req = MultipartSignRequest(key="u/raw/x.xml", upload_id="up", part_numbers=[1, 2, MAX_PARTS])
        assert req.part_numbers == [1, 2, MAX_PARTS]

    @pytest.mark.parametrize("part_number", [0, -1, MAX_PARTS + 1])
    def test_rejects_out_of_range_part_numbers(self, part_number: int) -> None:
        with pytest.raises(ValidationError):
            MultipartSignRequest(key="u/raw/x.xml", upload_id="up", part_numbers=[part_number])

    def test_rejects_empty_part_numbers(self) -> None:
        with pytest.raises(ValidationError):
            MultipartSignRequest(key="u/raw/x.xml", upload_id="up", part_numbers=[])

    def test_constant_matches_schema_default(self) -> None:
        assert MultipartSignRequest.model_fields["expiration_seconds"].default == DEFAULT_EXPIRATION_SECONDS
