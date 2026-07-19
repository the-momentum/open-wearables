"""
Integration tests for Ultrahuman night_rhr (resting heart rate) parsing.

Covers the normalize_night_rhr helper introduced in data_247.py to resolve
https://github.com/the-momentum/open-wearables/issues/664.
"""

from uuid import UUID

import pytest

from app.models import User
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.services.providers.ultrahuman.data_247 import Ultrahuman247Data
from app.services.providers.ultrahuman.oauth import UltrahumanOAuth
from tests.factories import UserFactory


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_data_247() -> Ultrahuman247Data:
    """Construct an Ultrahuman247Data instance for unit-level tests."""
    user_repo = UserRepository(User)
    connection_repo = UserConnectionRepository()
    oauth = UltrahumanOAuth(
        user_repo=user_repo,
        connection_repo=connection_repo,
        provider_name="ultrahuman",
        api_base_url="https://partner.ultrahuman.com",
    )
    return Ultrahuman247Data(
        provider_name="ultrahuman",
        api_base_url="https://partner.ultrahuman.com",
        oauth=oauth,
    )


# ---------------------------------------------------------------------------
# Fixture data — matches the payload documented in issue #664 and
# pre-seeded in tests/providers/conftest.py:417
# ---------------------------------------------------------------------------

NIGHT_RHR_FIXTURE = {
    "type": "night_rhr",
    "object": {
        "day_start_timestamp": 1705276800,  # 2024-01-15 00:00:00 UTC
        "title": "Resting HR",
        "values": [
            {"value": 52, "timestamp": 1705290000},  # 2024-01-15 03:40:00 UTC
            {"value": 50, "timestamp": 1705293600},  # 2024-01-15 04:40:00 UTC
            {"value": 51, "timestamp": 1705297200},  # 2024-01-15 05:40:00 UTC
        ],
        "subtitle": "Sleep Time Average",
        "avg": 51,
    },
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNightRhrNormalization:
    """Unit tests for Ultrahuman247Data.normalize_night_rhr."""

    def test_values_array_produces_one_sample_per_entry(self, db) -> None:
        """Each entry in values[] should produce exactly one bpm sample."""
        data_247 = _make_data_247()
        user = UserFactory()
        raw_rhr = NIGHT_RHR_FIXTURE["object"]

        samples = data_247.normalize_night_rhr(raw_rhr, user.id)

        assert len(samples) == 3, "Expected one sample per values[] entry"

        for sample in samples:
            assert sample["unit"] == "bpm"
            assert sample["provider"] == "ultrahuman"
            assert sample["user_id"] == user.id
            assert isinstance(sample["value"], int)
            assert sample["recorded_at"] is not None
            # UUID shape check
            assert isinstance(sample["id"], UUID)

        # Values should round-trip correctly
        assert [s["value"] for s in samples] == [52, 50, 51]

    def test_avg_fallback_used_when_no_values_array(self, db) -> None:
        """When values[] is absent, avg + day_start_timestamp produces one sample."""
        data_247 = _make_data_247()
        user = UserFactory()
        raw_rhr = {
            "day_start_timestamp": 1705276800,
            "title": "Resting HR",
            "subtitle": "Sleep Time Average",
            "avg": 54,
            # no "values" key
        }

        samples = data_247.normalize_night_rhr(raw_rhr, user.id)

        assert len(samples) == 1, "Expected exactly one fallback sample from avg"
        assert samples[0]["value"] == 54
        assert samples[0]["unit"] == "bpm"
        assert samples[0]["provider"] == "ultrahuman"
        # Timestamp must decode to the day_start
        assert "2024-01-15" in samples[0]["recorded_at"]

    def test_empty_payload_returns_no_samples(self, db) -> None:
        """An empty dict (night_rhr absent from API) must not raise and returns []."""
        data_247 = _make_data_247()
        user = UserFactory()

        samples = data_247.normalize_night_rhr({}, user.id)

        assert samples == [], "Expected empty list for missing night_rhr data"

    def test_partial_values_entry_without_timestamp_skipped(self, db) -> None:
        """A values entry missing 'timestamp' is silently skipped."""
        data_247 = _make_data_247()
        user = UserFactory()
        raw_rhr = {
            "values": [
                {"value": 55, "timestamp": 1705290000},
                {"value": 53},  # missing timestamp — should be skipped
            ],
            "avg": 54,
            "day_start_timestamp": 1705276800,
        }

        samples = data_247.normalize_night_rhr(raw_rhr, user.id)

        # Only the valid entry should survive
        assert len(samples) == 1
        assert samples[0]["value"] == 55

    def test_partial_values_entry_without_value_skipped(self, db) -> None:
        """A values entry missing 'value' is silently skipped."""
        data_247 = _make_data_247()
        user = UserFactory()
        raw_rhr = {
            "values": [
                {"timestamp": 1705290000},  # missing value — should be skipped
                {"value": 48, "timestamp": 1705293600},
            ],
        }

        samples = data_247.normalize_night_rhr(raw_rhr, user.id)

        assert len(samples) == 1
        assert samples[0]["value"] == 48
