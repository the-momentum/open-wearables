"""Garmin Backfill Service for triggering historical data sync.

The Garmin Health API backfill endpoints allow requesting historical data
without pull tokens. Data is sent asynchronously to configured webhooks.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException

from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.services.providers.api_client import make_authenticated_request
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class GarminBackfillService:
    """Trigger Garmin backfill to send historical data to webhooks.

    Backfill endpoints:
    - Don't require pull tokens (unlike regular summary endpoints)
    - Use summaryStartTimeInSeconds/summaryEndTimeInSeconds params
    - Return 202 Accepted (async processing)
    - Data is sent to configured webhook endpoints

    Official Garmin backfill limits (from documentation):
    - Max per request: 90 days
    - Per user limit: 1 month since first connection
    - Total history available: 2 years (Health) / 5 years (Activity)
    - Rate limit (prod): 10,000 days/minute
    - Duplicate requests: HTTP 409
    """

    # Backfill configuration
    BACKFILL_CHUNK_DAYS = 1  # Per request (1 day at a time)
    MAX_BACKFILL_DAYS = 30  # Target: 1 month of history
    MAX_REQUEST_DAYS = 90  # Max days per single backfill request (Garmin limit)

    # Mapping of data type to backfill endpoint
    BACKFILL_ENDPOINTS = {
        "sleeps": "/wellness-api/rest/backfill/sleeps",
        "dailies": "/wellness-api/rest/backfill/dailies",
        "epochs": "/wellness-api/rest/backfill/epochs",
        "bodyComps": "/wellness-api/rest/backfill/bodyComps",
        "hrv": "/wellness-api/rest/backfill/hrv",
        "stressDetails": "/wellness-api/rest/backfill/stressDetails",
        "respiration": "/wellness-api/rest/backfill/respiration",
        "pulseOx": "/wellness-api/rest/backfill/pulseOx",
        "activities": "/wellness-api/rest/backfill/activities",
        "activityDetails": "/wellness-api/rest/backfill/activityDetails",
        "userMetrics": "/wellness-api/rest/backfill/userMetrics",
        "bloodPressures": "/wellness-api/rest/backfill/bloodPressures",
        "skinTemp": "/wellness-api/rest/backfill/skinTemp",
        "healthSnapshot": "/wellness-api/rest/backfill/healthSnapshot",
        "moveiq": "/wellness-api/rest/backfill/moveiq",
        "mct": "/wellness-api/rest/backfill/mct",
    }

    # Default data types to backfill for wellness sync
    DEFAULT_DATA_TYPES = [
        "sleeps",
        "dailies",
        "epochs",
        "bodyComps",
        "hrv",
    ]

    DEFAULT_BACKFILL_DAYS = 1  # Default for subsequent syncs
    REQUEST_DELAY_SECONDS = 0.5  # Small delay between requests (prod limit: 10,000 days/min)

    def __init__(
        self,
        provider_name: str,
        api_base_url: str,
        oauth: BaseOAuthTemplate,
    ):
        self.provider_name = provider_name
        self.api_base_url = api_base_url
        self.oauth = oauth
        self.connection_repo = UserConnectionRepository()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Make authenticated request to Garmin Wellness API.

        Backfill endpoints return 202 Accepted with empty body,
        so we set expect_json=False to avoid JSON parsing errors.
        """
        return make_authenticated_request(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            api_base_url=self.api_base_url,
            provider_name=self.provider_name,
            endpoint=endpoint,
            method="GET",
            params=params,
            expect_json=False,
        )

    def trigger_backfill(
        self,
        db: DbSession,
        user_id: UUID,
        data_types: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        is_first_sync: bool = False,
    ) -> dict[str, Any]:
        """Trigger backfill for specified data types.

        Args:
            db: Database session
            user_id: User ID
            data_types: List of data types to backfill (defaults to DEFAULT_DATA_TYPES)
            start_time: Start of date range (defaults based on is_first_sync)
            end_time: End of date range (defaults to now)
            is_first_sync: If True, use max timeframe (2 years). If False, use DEFAULT_BACKFILL_DAYS.

        Returns:
            Dict with backfill results for each data type:
            {
                "triggered": ["sleeps", "dailies", ...],
                "failed": {"epochs": "error message", ...},
                "start_time": "2024-01-01T00:00:00Z",
                "end_time": "2024-01-31T00:00:00Z",
            }

        Note:
            Data is sent asynchronously to configured webhooks.
            The response only indicates if the backfill request was accepted.
        """
        if data_types is None:
            data_types = self.DEFAULT_DATA_TYPES

        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            # Use 30 days for first sync (per user limit), otherwise 1 day
            days = self.BACKFILL_CHUNK_DAYS if is_first_sync else self.DEFAULT_BACKFILL_DAYS
            start_time = end_time - timedelta(days=days)
            self.logger.info(
                f"Backfill timeframe: {days} days ({'first sync' if is_first_sync else 'subsequent sync'})"
            )

        results: dict[str, Any] = {
            "triggered": [],
            "failed": {},
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

        for i, data_type in enumerate(data_types):
            # Small delay between requests (prod rate limit: 10,000 days/min)
            if i > 0:
                time.sleep(self.REQUEST_DELAY_SECONDS)

            endpoint = self.BACKFILL_ENDPOINTS.get(data_type)
            if not endpoint:
                results["failed"][data_type] = f"Unknown data type: {data_type}"
                continue

            params = {
                "summaryStartTimeInSeconds": int(start_time.timestamp()),
                "summaryEndTimeInSeconds": int(end_time.timestamp()),
            }

            try:
                self.logger.info(
                    f"Triggering backfill for {data_type} "
                    f"({start_time.isoformat()} to {end_time.isoformat()}) "
                    f"for user {user_id}"
                )
                # Backfill endpoints return 202 Accepted on success
                self._make_api_request(db, user_id, endpoint, params)
                results["triggered"].append(data_type)
                self.logger.info(f"Backfill triggered for {data_type}")

            except HTTPException as e:
                # 409 = duplicate backfill already processed - treat as success
                if e.status_code == 409:
                    self.logger.info(f"Backfill for {data_type} already requested (409 duplicate)")
                    results["triggered"].append(data_type)
                else:
                    self.logger.error(f"Backfill failed for {data_type}: {e.detail}")
                    results["failed"][data_type] = str(e.detail)

            except Exception as e:
                self.logger.error(f"Backfill failed for {data_type}: {e}")
                results["failed"][data_type] = str(e)

        return results

    def trigger_sleep_backfill(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> bool:
        """Trigger backfill for sleep data only."""
        result = self.trigger_backfill(db, user_id, ["sleeps"], start_time, end_time)
        return "sleeps" in result["triggered"]

    def trigger_dailies_backfill(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> bool:
        """Trigger backfill for dailies data only."""
        result = self.trigger_backfill(db, user_id, ["dailies"], start_time, end_time)
        return "dailies" in result["triggered"]

    def trigger_epochs_backfill(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> bool:
        """Trigger backfill for epochs data only."""
        result = self.trigger_backfill(db, user_id, ["epochs"], start_time, end_time)
        return "epochs" in result["triggered"]

    def trigger_activities_backfill(
        self,
        db: DbSession,
        user_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> bool:
        """Trigger backfill for activities data only."""
        result = self.trigger_backfill(db, user_id, ["activities"], start_time, end_time)
        return "activities" in result["triggered"]
