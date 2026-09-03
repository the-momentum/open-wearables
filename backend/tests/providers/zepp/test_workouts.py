"""Tests for ZeppWorkouts."""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.auth import ConnectionStatus
from app.schemas.enums import WorkoutType
from app.services.providers.zepp.client import ZeppAuthExpiredError
from app.services.providers.zepp.workouts import ZeppWorkouts


class TestZeppWorkouts:
    def test_normalize_workout(self) -> None:
        mock_workout_repo = MagicMock()
        mock_conn_repo = MagicMock()
        workouts_service = ZeppWorkouts(mock_workout_repo, mock_conn_repo)
        user_id = uuid4()

        raw_workout = {
            "trackid": "1714578120",
            "type": 1,  # Running
            "run_time": 1800,  # 30 mins
            "dis": 5000,  # 5 km
            "calorie": 350,
            "avg_heart_rate": 145,
            "max_heart_rate": 172,
            "total_step": 4200,
            "source": "run.cheetah-pro.huami.com",
        }

        record, detail = workouts_service._normalize_workout(raw_workout, user_id)

        assert record.user_id == user_id
        assert record.category == "workout"
        assert record.type == WorkoutType.RUNNING.value
        assert record.device_model == "cheetah-pro"
        assert record.duration_seconds == 1800
        assert record.external_id == "1714578120"
        assert detail.distance == Decimal("5000.0")
        assert detail.energy_burned == Decimal("350.0")
        assert detail.heart_rate_avg == Decimal("145")
        assert detail.heart_rate_max == 172
        assert detail.steps_count == 4200
        assert detail.moving_time_seconds == 1800

    def test_load_data_no_connection_returns_zero(self) -> None:
        mock_workout_repo = MagicMock()
        mock_conn_repo = MagicMock()
        mock_conn_repo.get_active_connection.return_value = None
        mock_db = MagicMock()

        workouts_service = ZeppWorkouts(mock_workout_repo, mock_conn_repo)
        count = workouts_service.load_data(mock_db, uuid4())

        assert count == 0

    def test_load_data_success(self) -> None:
        mock_workout_repo = MagicMock()
        mock_conn_repo = MagicMock()
        mock_conn = MagicMock()
        mock_conn.access_token = "valid_token"
        mock_conn.provider_user_id = "12345"
        mock_conn.refresh_token = "api-mifit-us3.zepp.com"
        mock_conn_repo.get_active_connection.return_value = mock_conn

        mock_db = MagicMock()
        workouts_service = ZeppWorkouts(mock_workout_repo, mock_conn_repo)
        user_id = uuid4()

        sample_response = {
            "data": {
                "summary": [
                    {
                        "trackid": "1714578120",
                        "type": 9,  # Cycling
                        "run_time": 3600,
                        "dis": 20000,
                        "calorie": 600,
                        "avg_heart_rate": 130,
                        "max_heart_rate": 155,
                        "total_step": 0,
                        "source": "ride.t-rex-ultra.huami.com",
                    }
                ]
            }
        }

        with patch("app.services.providers.zepp.workouts.ZeppClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_workouts.return_value = sample_response
            mock_client.__enter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            with patch("app.services.providers.zepp.workouts.event_record_service") as mock_event_service:
                mock_created = MagicMock()
                mock_created.id = uuid4()
                mock_event_service.create.return_value = mock_created

                count = workouts_service.load_data(mock_db, user_id)

                assert count == 1
                mock_event_service.create.assert_called_once()
                mock_event_service.create_detail.assert_called_once()

    def test_load_data_auth_expired_transitions_connection(self) -> None:
        mock_workout_repo = MagicMock()
        mock_conn_repo = MagicMock()
        mock_conn = MagicMock()
        mock_conn.access_token = "expired_token"
        mock_conn.provider_user_id = "12345"
        mock_conn.status = ConnectionStatus.ACTIVE
        mock_conn_repo.get_active_connection.return_value = mock_conn

        mock_db = MagicMock()
        workouts_service = ZeppWorkouts(mock_workout_repo, mock_conn_repo)
        user_id = uuid4()

        with patch("app.services.providers.zepp.workouts.ZeppClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.get_workouts.side_effect = ZeppAuthExpiredError("Expired")
            mock_client.__enter__.return_value = mock_client
            mock_client_cls.return_value = mock_client

            with pytest.raises(ZeppAuthExpiredError):
                workouts_service.load_data(mock_db, user_id)

            assert mock_conn.status == ConnectionStatus.EXPIRED
            mock_db.add.assert_called_with(mock_conn)
            mock_db.commit.assert_called_once()
