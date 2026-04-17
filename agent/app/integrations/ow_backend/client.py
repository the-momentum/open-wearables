"""HTTP client for the Open Wearables backend REST API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import httpx

from app.config import settings


class OWClient:
    """Thin async HTTP client for the OW backend.

    Each method opens a short-lived httpx.AsyncClient per call so that the
    client is safe to use from Celery async contexts without keeping a
    persistent connection pool.
    """

    def _headers(self) -> dict[str, str]:
        return {"X-Open-Wearables-API-Key": settings.ow_api_key.get_secret_value()}

    def _base(self) -> str:
        return settings.ow_api_url.rstrip("/")

    async def get_user_profile(self, user_id: UUID) -> dict:
        """GET /users/{user_id} — basic profile (name, email, birth_date, sex, gender)."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_body_summary(self, user_id: UUID) -> dict:
        """GET /users/{user_id}/summaries/body — weight, height, BMI, body fat, resting HR, HRV."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/summaries/body",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_timeseries(
        self,
        user_id: UUID,
        start_time: str,
        end_time: str,
        types: list[str],
        resolution: str = "1hour",
    ) -> dict:
        """GET /users/{user_id}/timeseries — HR, SpO2, and other time-series data."""
        params: list[tuple[str, str]] = [
            ("start_time", start_time),
            ("end_time", end_time),
            ("resolution", resolution),
        ]
        for t in types:
            params.append(("types[]", t))
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/timeseries",
                headers=self._headers(),
                params=params,  # type: ignore
            )
            resp.raise_for_status()
            return resp.json()

    async def get_activity_summaries(
        self,
        user_id: UUID,
        start_date: date | str,
        end_date: date | str,
    ) -> dict:
        """GET /users/{user_id}/summaries/activity — daily steps, calories, HR."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/summaries/activity",
                headers=self._headers(),
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_sleep_summaries(
        self,
        user_id: UUID,
        start_date: date | str,
        end_date: date | str,
    ) -> dict:
        """GET /users/{user_id}/summaries/sleep — duration, efficiency, stages."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/summaries/sleep",
                headers=self._headers(),
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_recovery_summaries(
        self,
        user_id: UUID,
        start_date: date | str,
        end_date: date | str,
    ) -> dict:
        """GET /users/{user_id}/summaries/recovery — resting HR, HRV, SpO2, sleep efficiency."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/summaries/recovery",
                headers=self._headers(),
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_workout_events(
        self,
        user_id: UUID,
        start_date: date | str,
        end_date: date | str,
    ) -> dict:
        """GET /users/{user_id}/events/workouts — workout sessions with HR and calories."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/events/workouts",
                headers=self._headers(),
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_sleep_events(
        self,
        user_id: UUID,
        start_date: date | str,
        end_date: date | str,
    ) -> dict:
        """GET /users/{user_id}/events/sleep — detailed sleep sessions with stage intervals."""
        async with httpx.AsyncClient(timeout=settings.ow_api_timeout) as client:
            resp = await client.get(
                f"{self._base()}/api/v1/users/{user_id}/events/sleep",
                headers=self._headers(),
                params={"start_date": str(start_date), "end_date": str(end_date)},
            )
            resp.raise_for_status()
            return resp.json()


ow_client = OWClient()
