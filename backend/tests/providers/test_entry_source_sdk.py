"""Tests for the mobile SDK recordingMethod -> EntrySource mapping."""

import pytest

from app.constants.entry_source import get_unified_sdk_entry_source
from app.constants.entry_source.sdk import RECORDING_METHOD_TO_UNIFIED
from app.schemas.enums import EntrySource
from app.schemas.providers.mobile_sdk.sync_request import RecordingMethod


class TestSdkEntrySource:
    """RecordingMethod is the SDK's own vocabulary for the same concept as EntrySource."""

    @pytest.mark.parametrize(
        ("recording_method", "expected"),
        [
            (RecordingMethod.ACTIVE, EntrySource.AUTOMATIC),
            (RecordingMethod.AUTOMATIC, EntrySource.AUTOMATIC),
            (RecordingMethod.MANUAL, EntrySource.MANUAL),
            (RecordingMethod.UNKNOWN, EntrySource.UNKNOWN),
        ],
    )
    def test_maps_every_recording_method(self, recording_method: RecordingMethod, expected: EntrySource) -> None:
        assert get_unified_sdk_entry_source(recording_method) == expected

    def test_accepts_raw_strings_from_the_payload(self) -> None:
        """SourceInfo.recording_method is typed `RecordingMethod | str | None`."""
        assert get_unified_sdk_entry_source("manual") == EntrySource.MANUAL
        assert get_unified_sdk_entry_source("active") == EntrySource.AUTOMATIC

    def test_unmapped_value_from_a_newer_sdk_is_unknown(self) -> None:
        assert get_unified_sdk_entry_source("some_future_method") == EntrySource.UNKNOWN

    def test_absent_recording_method_yields_none(self) -> None:
        """A silent SDK must stay distinct from an explicit UNKNOWN."""
        assert get_unified_sdk_entry_source(None) is None

    def test_every_recording_method_is_mapped_explicitly(self) -> None:
        """A new member must be mapped deliberately, not hidden by the UNKNOWN default."""
        assert set(RECORDING_METHOD_TO_UNIFIED) == set(RecordingMethod)
