"""Tests for reading SDK attribution headers into log fields."""

from starlette.datastructures import Headers

from app.utils.sdk_request_metadata import sdk_request_metadata


class TestSDKRequestMetadata:
    def test_header_names_are_case_insensitive(self) -> None:
        headers = Headers({"x-open-wearables-sdk-version": "0.15.0", "X-REQUEST-ID": "req-1"})

        assert sdk_request_metadata(headers) == {"sdk_version": "0.15.0", "request_id": "req-1"}

    def test_control_characters_are_stripped(self) -> None:
        fields = sdk_request_metadata({"user-agent": "Agent/1.0\n\tfake=line\r"})

        assert fields["user_agent"] == "Agent/1.0fake=line"

    def test_long_values_are_truncated(self) -> None:
        fields = sdk_request_metadata({"user-agent": "x" * 1000})

        assert len(fields["user_agent"]) == 256

    def test_blank_values_are_dropped(self) -> None:
        assert sdk_request_metadata({"x-request-id": "  ", "x-open-wearables-sdk-platform": "\n"}) == {}

    def test_header_version_wins_over_body(self) -> None:
        fields = sdk_request_metadata({"x-open-wearables-sdk-version": "0.15.0"}, body_sdk_version="0.14.0")

        assert fields["sdk_version"] == "0.15.0"

    def test_body_version_is_sanitized(self) -> None:
        fields = sdk_request_metadata({}, body_sdk_version="1.0.0\nfake=line" + "x" * 1000)

        assert "\n" not in fields["sdk_version"]
        assert len(fields["sdk_version"]) == 256

    def test_non_string_body_version_is_ignored(self) -> None:
        assert sdk_request_metadata({}, body_sdk_version={"nested": "1.0.0"}) == {}
