"""Tests for Strava workout normalization."""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models import EventRecord
from app.repositories.event_record_repository import EventRecordRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.enums import WorkoutType
from app.schemas.providers.strava import ActivityJSON as StravaActivityJSON
from app.services.providers.strava.oauth import StravaOAuth
from app.services.providers.strava.workouts import StravaWorkouts


class TestStravaWorkouts:
    """Test suite for StravaWorkouts."""

    @pytest.fixture
    def strava_workouts(self) -> StravaWorkouts:
        workout_repo = EventRecordRepository(EventRecord)
        connection_repo = UserConnectionRepository()
        oauth = StravaOAuth(
            user_repo=MagicMock(),
            connection_repo=connection_repo,
            provider_name="strava",
            api_base_url="https://www.strava.com",
        )
        return StravaWorkouts(
            workout_repo=workout_repo,
            connection_repo=connection_repo,
            provider_name="strava",
            api_base_url="https://www.strava.com",
            oauth=oauth,
        )

    def test_normalize_workout_keeps_activity_name_and_route(
        self,
        strava_workouts: StravaWorkouts,
    ) -> None:
        user_id = uuid4()
        activity = StravaActivityJSON(
            id=987654321,
            name="Morning River Loop",
            type="Run",
            sport_type="Run",
            start_date="2026-06-10T12:00:00Z",
            elapsed_time=3600,
            distance=10_000.0,
            calories=640.0,
            map={
                "id": "a987654321",
                "summary_polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
            },
        )

        record, detail = strava_workouts._normalize_workout(activity, user_id)

        assert record.name == "Morning River Loop"
        assert record.type == WorkoutType.RUNNING.value
        assert record.external_id == "987654321"
        assert detail.distance == Decimal("10000")
        assert detail.energy_burned == Decimal("640")
        assert detail.route_polyline == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"

    def test_build_metrics_prefers_full_polyline_when_present(
        self,
        strava_workouts: StravaWorkouts,
    ) -> None:
        activity = StravaActivityJSON(
            id=987654322,
            name="Detailed Route",
            type="Ride",
            sport_type="Ride",
            start_date="2026-06-10T12:00:00Z",
            elapsed_time=1800,
            map={
                "id": "a987654322",
                "summary_polyline": "summary",
                "polyline": "full-resolution",
            },
        )

        metrics = strava_workouts._build_metrics(activity)

        assert metrics["route_polyline"] == "full-resolution"
