"""Tests for Zepp247Data."""

import base64
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.auth import ConnectionStatus
from app.services.providers.zepp.client import ZeppAuthExpiredError
from app.services.providers.zepp.data_247 import Zepp247Data, _decode_band_summary


class TestZepp247Data:
    def test_decode_band_summary(self) -> None:
        raw_dict = {"slp": {"st": 1000, "ed": 2000, "dp": 60, "lt": 120}, "stp": {"ttl": 5000}}
        encoded = base64.b64encode(json.dumps(raw_dict).encode("utf-8")).decode("utf-8")

        decoded = _decode_band_summary(encoded)
        assert decoded == raw_dict

        assert _decode_band_summary(None) is None
        assert _decode_band_summary("not-valid-base64") is None

    def test_load_and_save_all_success(self) -> None:
        data_service = Zepp247Data()
        mock_db = MagicMock()
        user_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.access_token = "valid_token"
        mock_conn.provider_user_id = "12345"
        mock_conn.refresh_token = "api-mifit-us3.zepp.com"
        mock_conn.status = ConnectionStatus.ACTIVE

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client

        # Mock band data with sleep and steps
        summary_data = {
            "slp": {
                "st": 1714520000,
                "ed": 1714550000,
                "dp": 90,
                "lt": 210,
                "dt": 60,
                "wk": 10,
                "rhr": 55,
            },
            "stp": {"ttl": 8500, "dis": 6200, "cal": 420},
        }
        b64_summary = base64.b64encode(json.dumps(summary_data).encode("utf-8")).decode("utf-8")
        mock_client.get_band_data.return_value = {
            "data": [
                {
                    "date_time": "2026-05-01",
                    "summary": b64_summary,
                }
            ]
        }

        # Mock heart rate minute data
        mock_client.get_heart_rate.return_value = {
            "items": [
                {
                    "timestamp": 1714520000000,
                    "value": 65,
                    "type": 0,
                },
                {
                    "timestamp": 1714520060000,
                    "value": 54,
                    "type": 1,  # resting
                },
            ]
        }

        # Mock readiness events
        mock_client.get_events.side_effect = lambda et, st, *args, **kwargs: {
            ("readiness", "watch_score"): {
                "items": [
                    {
                        "timestamp": 1714550000000,
                        "value": {"rdnsScore": 88, "sleepHRV": 65},
                    }
                ]
            },
            ("Charge", "stress_data"): {
                "items": [
                    {
                        "timestamp": 1714530000000,
                        "value": {"stress": 32},
                    }
                ]
            },
            ("Charge", "real_data"): {
                "items": [
                    {
                        "timestamp": 1714540000000,
                        "value": {"bodyBattery": 78},
                    }
                ]
            },
        }.get((et, st), {"items": []})

        # Mock VO2 Max
        mock_client.get_vo2_max.return_value = {"items": [{"dayId": "2026-05-01", "vo2Max": 48.5}]}

        # Mock SpO2
        mock_client.get_user_events.return_value = {
            "items": [{"timestamp": 1714525000000, "value": {"bloodOxygen": 98}}]
        }

        # Mock Weight
        mock_client.get_weight_records.return_value = {
            "items": [
                {
                    "timestamp": 1714520000,
                    "summary": {"weight": 72.5, "bmi": 22.4},
                }
            ]
        }

        mock_counts = MagicMock()
        mock_counts.inserted = 10
        mock_counts.updated = 2

        with (
            patch.object(data_service.connection_repo, "get_active_connection", return_value=mock_conn),
            patch("app.services.providers.zepp.data_247.ZeppClient", return_value=mock_client),
            patch("app.services.providers.zepp.data_247.event_record_service") as mock_event_service,
            patch("app.services.providers.zepp.data_247.timeseries_service") as mock_ts_service,
            patch("app.services.providers.zepp.data_247.health_score_service") as mock_hs_service,
        ):
            mock_ts_service.bulk_create_samples.return_value = mock_counts

            res = data_service.load_and_save_all(mock_db, user_id)

            assert res["sleep_sessions_synced"] == 1
            assert res["activity_samples"] == 12
            mock_event_service.create_or_merge_sleep.assert_called_once()
            mock_ts_service.bulk_create_samples.assert_called_once()
            mock_hs_service.bulk_create.assert_called_once()

    def test_load_and_save_all_auth_expired(self) -> None:
        data_service = Zepp247Data()
        mock_db = MagicMock()
        user_id = uuid4()

        mock_conn = MagicMock()
        mock_conn.access_token = "expired_token"
        mock_conn.provider_user_id = "12345"
        mock_conn.status = ConnectionStatus.ACTIVE

        with (
            patch.object(data_service.connection_repo, "get_active_connection", return_value=mock_conn),
            patch("app.services.providers.zepp.data_247.ZeppClient") as mock_client_cls,
        ):
            mock_client = MagicMock()
            mock_client.__enter__.return_value = mock_client
            mock_client.get_band_data.side_effect = ZeppAuthExpiredError("Token expired")
            mock_client_cls.return_value = mock_client

            with pytest.raises(ZeppAuthExpiredError):
                data_service.load_and_save_all(mock_db, user_id)

            assert mock_conn.status == ConnectionStatus.EXPIRED
            mock_db.add.assert_called_with(mock_conn)
            mock_db.commit.assert_called_once()
