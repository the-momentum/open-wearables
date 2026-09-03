"""Tests for ZeppClient."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.providers.zepp.client import (
    ALLOWED_HOSTS,
    DEFAULT_HOST,
    ZeppAuthExpiredError,
    ZeppClient,
)


class TestZeppClient:
    def test_allowed_hosts_configuration(self) -> None:
        assert DEFAULT_HOST in ALLOWED_HOSTS
        assert "api-mifit-us3.zepp.com" in ALLOWED_HOSTS

    def test_init_valid_host(self) -> None:
        client = ZeppClient(apptoken="test_token", user_id="12345", host="api-mifit-us3.zepp.com")
        assert client.host == "api-mifit-us3.zepp.com"
        assert client.base_url == "https://api-mifit-us3.zepp.com"
        assert client.apptoken == "test_token"
        assert client.user_id == "12345"
        client.close()

    def test_init_invalid_host_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unauthorized Zepp host"):
            ZeppClient(apptoken="test_token", user_id="12345", host="malicious.evil.com")

    def test_headers_included(self) -> None:
        client = ZeppClient(apptoken="token_abc", user_id="999")
        headers = client.client.headers
        assert headers["apptoken"] == "token_abc"
        assert headers["appname"] == "com.huami.midong"
        assert "Zepp" in headers["user-agent"]
        client.close()

    def test_get_json_success(self) -> None:
        client = ZeppClient(apptoken="tok", user_id="123")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": "ok", "data": {"summary": []}}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client.client, "get", return_value=mock_resp) as mock_get:
            res = client.get_json("/test/path", {"param1": "val1"})
            assert res == {"result": "ok", "data": {"summary": []}}
            mock_get.assert_called_once()
            called_params = mock_get.call_args[1]["params"]
            assert called_params["param1"] == "val1"
            assert "r" in called_params
        client.close()

    def test_get_json_401_raises_zepp_auth_expired(self) -> None:
        client = ZeppClient(apptoken="tok", user_id="123")
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with (
            patch.object(client.client, "get", return_value=mock_resp),
            pytest.raises(ZeppAuthExpiredError),
        ):
            client.get_json("/test")
        client.close()

    def test_get_json_error_payload_raises_zepp_auth_expired(self) -> None:
        client = ZeppClient(apptoken="tok", user_id="123")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"code": 1004, "message": "token expired"}
        mock_resp.raise_for_status = MagicMock()

        with (
            patch.object(client.client, "get", return_value=mock_resp),
            pytest.raises(ZeppAuthExpiredError),
        ):
            client.get_json("/test")
        client.close()

    def test_methods_build_expected_params(self) -> None:
        client = ZeppClient(apptoken="tok", user_id="123")
        with patch.object(client, "get_json", return_value={"ok": True}) as mock_get_json:
            client.get_user_info()
            mock_get_json.assert_called_with("/huami.health.getUserInfo.json", {"userid": "123"})

            client.get_workouts(start_track_id=100, stop_track_id=200, sport="run")
            mock_get_json.assert_called_with(
                "/v1/sport/run/history.json",
                {"userid": "123", "startTrackId": 100, "stopTrackId": 200, "need_sub_data": 1, "type": ""},
            )

            client.get_band_data(date(2026, 4, 1), date(2026, 4, 2))
            mock_get_json.assert_called_with(
                "/v1/data/band_data.json",
                {
                    "userid": "123",
                    "from_date": "2026-04-01",
                    "to_date": "2026-04-02",
                    "query_type": "detail",
                    "byteLength": 8,
                    "device_type": 0,
                },
            )
        client.close()
