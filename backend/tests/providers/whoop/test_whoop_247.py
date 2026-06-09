"""Tests for Whoop 247 data implementation."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import HealthScore
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import HealthScoreCategory
from app.services.providers.whoop.data_247 import Whoop247Data
from app.services.providers.whoop.oauth import WhoopOAuth
from tests.factories import UserFactory


class TestWhoop247Data:
    """Tests for Whoop247Data class."""

    @pytest.fixture
    def whoop_247(self, db: Session) -> Whoop247Data:
        """Create Whoop247Data instance for testing."""
        connection_repo = UserConnectionRepository()
        oauth = WhoopOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="whoop",
            api_base_url="https://api.prod.whoop.com/developer",
        )
        return Whoop247Data(
            provider_name="whoop",
            api_base_url="https://api.prod.whoop.com/developer",
            oauth=oauth,
        )

    @pytest.fixture
    def sample_cycle(self) -> dict[str, Any]:
        """Sample Whoop cycle record."""
        return {
            "id": 93845,
            "user_id": 10129,
            "created_at": "2024-01-15T11:25:44.774Z",
            "updated_at": "2024-01-16T14:25:44.774Z",
            "start": "2024-01-15T02:25:44.774Z",
            "end": "2024-01-16T03:25:44.774Z",
            "timezone_offset": "-05:00",
            "score_state": "SCORED",
            "score": {
                "strain": 5.2951527,
                "kilojoule": 8288.297,
                "average_heart_rate": 68,
                "max_heart_rate": 141,
            },
        }

    def test_normalize_cycle_scored(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """Scored, completed cycle becomes a strain health score."""
        user_id = uuid4()

        health_score = whoop_247.normalize_cycle(sample_cycle, user_id)

        assert health_score is not None
        assert health_score.category == HealthScoreCategory.STRAIN
        assert health_score.user_id == user_id
        assert health_score.qualifier == "daily"
        assert health_score.zone_offset == "-05:00"
        assert float(health_score.value) == pytest.approx(5.2951527)
        assert health_score.recorded_at == datetime(2024, 1, 15, 2, 25, 44, 774000, tzinfo=timezone.utc)
        assert health_score.components is not None
        assert health_score.components["kilojoule"].value == pytest.approx(8288.297)
        assert health_score.components["average_heart_rate"].value == 68
        assert health_score.components["max_heart_rate"].value == 141

    def test_normalize_cycle_unscored(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """Unscored cycle is skipped."""
        sample_cycle["score_state"] = "PENDING_SCORE"

        assert whoop_247.normalize_cycle(sample_cycle, uuid4()) is None

    def test_normalize_cycle_in_progress(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """Cycle without end time (still in progress) is skipped."""
        sample_cycle["end"] = None

        assert whoop_247.normalize_cycle(sample_cycle, uuid4()) is None

    def test_normalize_cycle_missing_strain(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """Cycle without strain in score is skipped."""
        sample_cycle["score"] = {"kilojoule": 8288.297}

        assert whoop_247.normalize_cycle(sample_cycle, uuid4()) is None

    def test_normalize_cycle_null_score(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """SCORED state with a null score object is skipped."""
        sample_cycle["score"] = None

        assert whoop_247.normalize_cycle(sample_cycle, uuid4()) is None

    def test_normalize_cycle_malformed_start(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """Unparseable start timestamp is skipped."""
        sample_cycle["start"] = "not-a-date"

        assert whoop_247.normalize_cycle(sample_cycle, uuid4()) is None

    def test_get_cycle_data_paginates(self, whoop_247: Whoop247Data, sample_cycle: dict[str, Any]) -> None:
        """Cycle fetch follows next_token pagination on /v2/cycle."""
        page_one = {"records": [sample_cycle], "next_token": "token123"}
        page_two = {"records": [dict(sample_cycle, id=93846)], "next_token": None}

        with patch.object(whoop_247, "_make_api_request", side_effect=[page_one, page_two]) as mock_request:
            records = whoop_247.get_cycle_data(
                MagicMock(),
                uuid4(),
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 31, tzinfo=timezone.utc),
            )

        assert len(records) == 2
        assert mock_request.call_count == 2
        first_call = mock_request.call_args_list[0]
        assert first_call.args[2] == "/v2/cycle"
        second_call = mock_request.call_args_list[1]
        assert second_call.kwargs["params"]["nextToken"] == "token123"

    def test_load_and_save_cycles(
        self,
        db: Session,
        whoop_247: Whoop247Data,
        sample_cycle: dict[str, Any],
    ) -> None:
        """Cycle records are saved as strain health scores."""
        user = UserFactory()

        with patch.object(whoop_247, "get_cycle_data", return_value=[sample_cycle]):
            count = whoop_247.load_and_save_cycles(
                db,
                user.id,
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 31, tzinfo=timezone.utc),
            )

        assert count == 1
        saved = db.query(HealthScore).filter(HealthScore.user_id == user.id).all()
        assert len(saved) == 1
        assert saved[0].category == HealthScoreCategory.STRAIN
        assert float(saved[0].value) == pytest.approx(5.2951527, abs=1e-3)

    def test_load_and_save_cycles_resync_does_not_duplicate(
        self,
        db: Session,
        whoop_247: Whoop247Data,
        sample_cycle: dict[str, Any],
    ) -> None:
        """Re-syncing the same cycle relies on the unique-constraint dedupe."""
        user = UserFactory()
        window = (datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 31, tzinfo=timezone.utc))

        with patch.object(whoop_247, "get_cycle_data", return_value=[sample_cycle]):
            whoop_247.load_and_save_cycles(db, user.id, *window)
            whoop_247.load_and_save_cycles(db, user.id, *window)

        assert db.query(HealthScore).filter(HealthScore.user_id == user.id).count() == 1

    def test_get_cycle_data_returns_partial_results_on_later_page_error(
        self,
        whoop_247: Whoop247Data,
        sample_cycle: dict[str, Any],
    ) -> None:
        """A failure after the first page returns the records fetched so far."""
        page_one = {"records": [sample_cycle], "next_token": "token123"}

        with patch.object(whoop_247, "_make_api_request", side_effect=[page_one, RuntimeError("boom")]):
            records = whoop_247.get_cycle_data(
                MagicMock(),
                uuid4(),
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 31, tzinfo=timezone.utc),
            )

        assert len(records) == 1

    def test_get_cycle_data_raises_on_first_page_error(self, whoop_247: Whoop247Data) -> None:
        """A failure on the first page propagates instead of returning empty data."""
        with (
            patch.object(whoop_247, "_make_api_request", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError),
        ):
            whoop_247.get_cycle_data(
                MagicMock(),
                uuid4(),
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 31, tzinfo=timezone.utc),
            )
