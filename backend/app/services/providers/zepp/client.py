from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import httpx

DEFAULT_HOST = "api-mifit-us3.zepp.com"

ALLOWED_HOSTS: set[str] = {
    "api-mifit-us3.zepp.com",
    "api-mifit-us2.zepp.com",
    "api-mifit-de2.zepp.com",
    "api-mifit.huami.com",
    "api-mifit-ru.zepp.com",
    "api-mifit-in2.zepp.com",
}


class ZeppAuthExpiredError(RuntimeError):
    """Raised when the Zepp app token is expired, invalid, or unauthorized."""

    pass


def _generate_r() -> str:
    """Generate the unique uppercase UUID required by Huami API."""
    return str(uuid.uuid4()).upper()


class ZeppClient:
    """HTTP client for Huami / Zepp REST API."""

    def __init__(
        self,
        apptoken: str,
        user_id: str,
        host: str = DEFAULT_HOST,
        app_platform: str = "ios_phone",
        timeout: float = 30.0,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        clean_host = (host or DEFAULT_HOST).strip().lower()
        if "://" in clean_host:
            clean_host = clean_host.split("://", 1)[1]
        clean_host = clean_host.split("/", 1)[0].split(":", 1)[0].strip()

        if clean_host not in ALLOWED_HOSTS:
            raise ValueError(
                f"Unauthorized Zepp host: '{clean_host}'. Allowed hosts: {', '.join(sorted(ALLOWED_HOSTS))}"
            )

        self.apptoken = apptoken.strip()
        self.user_id = str(user_id).strip()
        self.host = clean_host
        self.base_url = f"https://{clean_host}"
        self.timeout = timeout

        headers = self._build_headers(app_platform, extra_headers or {})
        self.client = httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)

    def _build_headers(self, app_platform: str, extra: dict[str, str]) -> dict[str, str]:
        defaults = {
            "apptoken": self.apptoken,
            "appname": "com.huami.midong",
            "appplatform": app_platform,
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "v": "2.0",
            "vn": "10.2.5",
            "cv": "1722_10.2.5",
            "vb": "202604132257",
            "user-agent": "Zepp/10.2.5 (iPhone; iOS 26.3.1; Scale/3.00)",
            "lang": "en",
            "country": "",
            "timezone": "UTC",
        }
        defaults.update({k: v for k, v in extra.items() if v})
        return defaults

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Perform an authenticated GET request with the required query parameters."""
        q = {"r": _generate_r()}
        if params:
            q.update(params)

        try:
            response = self.client.get(path, params=q)
        except httpx.RequestError as exc:
            raise RuntimeError(f"Network error communicating with Zepp API: {exc}") from exc

        if response.status_code in (401, 403):
            raise ZeppAuthExpiredError(f"Zepp authentication expired or rejected with HTTP {response.status_code}")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Zepp API returned error status: {exc}") from exc

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError("Invalid JSON returned by Zepp API") from exc

        if isinstance(data, dict):
            code = data.get("code")
            msg = str(data.get("message") or data.get("error") or "").lower()
            if code in (401, 403, 1004) or any(
                term in msg for term in ("token expired", "token invalid", "unauthorized", "login first")
            ):
                raise ZeppAuthExpiredError(f"Zepp session expired or invalid: {data}")

        return data

    def get_user_info(self) -> dict[str, Any]:
        """Fetch user profile information to validate credentials."""
        return self.get_json("/huami.health.getUserInfo.json", {"userid": self.user_id})

    def get_workouts(
        self,
        start_track_id: int = 0,
        stop_track_id: int | None = None,
        sport: str = "run",
    ) -> dict[str, Any]:
        """Fetch workout history for the given sport."""
        if stop_track_id is None:
            stop_track_id = int(datetime.now(timezone.utc).timestamp())

        return self.get_json(
            f"/v1/sport/{sport}/history.json",
            {
                "userid": self.user_id,
                "startTrackId": start_track_id,
                "stopTrackId": stop_track_id,
                "need_sub_data": 1,
                "type": "",
            },
        )

    def get_band_data(
        self,
        from_date: date,
        to_date: date,
        query_type: str = "detail",
    ) -> dict[str, Any]:
        """Fetch raw band sync payload (sleep segments, steps, active summaries)."""
        return self.get_json(
            "/v1/data/band_data.json",
            {
                "userid": self.user_id,
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "query_type": query_type,
                "byteLength": 8,
                "device_type": 0,
            },
        )

    def get_heart_rate(
        self,
        start_ts: int,
        end_ts: int,
        limit: int = 1000,
        hr_type: int = 2,
    ) -> dict[str, Any]:
        """Fetch heart rate minute samples and daily resting HR."""
        return self.get_json(
            f"/users/{self.user_id}/heartRate",
            {
                "startTime": start_ts,
                "endTime": end_ts,
                "limit": limit,
                "type": hr_type,
            },
        )

    def get_events(
        self,
        event_type: str,
        sub_type: str,
        from_ms: int,
        to_ms: int,
        limit: int = 500,
        reverse: bool = True,
    ) -> dict[str, Any]:
        """Fetch events from /v2/users/me/events (Charge/real_data, Charge/stress_data, readiness/watch_score)."""
        return self.get_json(
            "/v2/users/me/events",
            {
                "eventType": event_type,
                "subType": sub_type,
                "from": from_ms,
                "to": to_ms,
                "limit": limit,
                "reverse": 1 if reverse else 0,
            },
        )

    def get_user_events(
        self,
        event_type: str,
        from_ms: int,
        to_ms: int,
        sub_type: str | None = None,
        limit: int = 2000,
        reverse: bool = False,
    ) -> dict[str, Any]:
        """Fetch user timeline events (/users/{id}/events)."""
        params: dict[str, Any] = {
            "eventType": event_type,
            "from": from_ms,
            "to": to_ms,
            "limit": limit,
            "reverse": 1 if reverse else 0,
            "userId": self.user_id,
        }
        if sub_type:
            params["subType"] = sub_type
        return self.get_json(f"/users/{self.user_id}/events", params)

    def get_vo2_max(self, start_day: date, end_day: date) -> dict[str, Any]:
        """Fetch daily VO2 Max statistics."""
        return self.get_json(
            f"/v2/watch/users/{self.user_id}/WatchSportStatistics/VO2_MAX",
            {
                "startDay": start_day.isoformat(),
                "endDay": end_day.isoformat(),
                "limit": 900,
                "isReverse": "true",
            },
        )

    def get_weight_records(self, from_ts: int, to_ts: int, limit: int = 300) -> dict[str, Any]:
        """Fetch weight and body composition records."""
        return self.get_json(
            f"/users/{self.user_id}/members/-1/weightRecords",
            {
                "fromTime": from_ts,
                "toTime": to_ts,
                "limit": limit,
                "isForward": 0,
            },
        )

    def close(self) -> None:
        """Close the underlying HTTP client session."""
        self.client.close()

    def __enter__(self) -> ZeppClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
