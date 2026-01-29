"""Garmin Summary Service for fetching immediate data (last 7 days).

The Garmin Health API Summary endpoints return data immediately via HTTP 200,
unlike Backfill endpoints which are async (HTTP 202, data via webhooks).

Summary endpoints have data for the last 7 days (Garmin's retention window).
For historical data beyond 7 days, use the Backfill service.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx

from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.services.providers.garmin.pull_token import generate_garmin_pull_token


class GarminSummaryService:
    """Fetch immediate data from Garmin Summary endpoints (last 7 days).

    Summary endpoints require BOTH:
    - User's OAuth Bearer token in Authorization header
    - Consumer Pull Token (CPT) as query parameter

    Constraints:
    - Max 24-hour time range per request (86400 seconds)
    - Data retention: ~7 days from device sync

    This is much faster than Backfill for recent data since:
    - No webhook callback delay
    - Data returned in same HTTP response
    """

    API_BASE_URL = "https://apis.garmin.com"

    # Summary endpoints (NOT backfill - these return data immediately)
    # Full list of 16 endpoints for comprehensive Garmin data sync
    SUMMARY_ENDPOINTS = {
        # Core wellness data (original 5)
        "dailies": "/wellness-api/rest/dailies",
        "sleeps": "/wellness-api/rest/sleeps",
        "epochs": "/wellness-api/rest/epochs",
        "bodyComps": "/wellness-api/rest/bodyComps",
        "hrv": "/wellness-api/rest/hrv",
        # Activity data (new)
        "activities": "/wellness-api/rest/activities",
        "activityDetails": "/wellness-api/rest/activityDetails",
        "moveiq": "/wellness-api/rest/moveiq",
        # Health metrics (new)
        "healthSnapshot": "/wellness-api/rest/healthSnapshot",
        "stressDetails": "/wellness-api/rest/stressDetails",
        "respiration": "/wellness-api/rest/respiration",
        "pulseOx": "/wellness-api/rest/pulseOx",
        "bloodPressures": "/wellness-api/rest/bloodPressures",
        "userMetrics": "/wellness-api/rest/userMetrics",
        "skinTemp": "/wellness-api/rest/skinTemp",
        # Menstrual cycle tracking (new)
        "mct": "/wellness-api/rest/mct",
    }

    # Maximum days of data available via Summary endpoints (7-day REST sync)
    # For historical data beyond 7 days, use the Backfill service
    MAX_SUMMARY_DAYS = 7
    # Maximum seconds per single request (Garmin limit)
    MAX_REQUEST_SECONDS = 86400  # 24 hours

    # Rate limiting configuration to avoid Garmin 429 errors
    REQUEST_DELAY_SECONDS = 0.3  # Delay between API requests (300ms)
    MAX_RETRIES = 3  # Max retry attempts for 429 errors
    RETRY_BASE_DELAY = 1.0  # Base delay for exponential backoff (seconds)

    def __init__(self) -> None:
        """Initialize the summary service."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.connection_repo = UserConnectionRepository()

    def _get_user_access_token(self, db: DbSession, user_id: UUID) -> str | None:
        """Get user's OAuth access token for Garmin."""
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, "garmin")
        if not connection:
            self.logger.error(f"No Garmin connection found for user {user_id}")
            return None
        return connection.access_token

    def _make_summary_request(
        self,
        endpoint: str,
        access_token: str,
        pull_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Make a request to a Summary endpoint with rate limiting and retry logic.

        Args:
            endpoint: API endpoint path
            access_token: User's OAuth Bearer token
            pull_token: Consumer Pull Token (CPT)
            start_time: Start of date range
            end_time: End of date range (max 24 hours from start)

        Returns:
            List of data items from the endpoint
        """
        url = f"{self.API_BASE_URL}{endpoint}"
        # CPT token as query parameter
        params = {
            "uploadStartTimeInSeconds": int(start_time.timestamp()),
            "uploadEndTimeInSeconds": int(end_time.timestamp()),
            "token": pull_token,
        }
        # User's OAuth token in Authorization header
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        # Retry loop with exponential backoff for rate limiting
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                # Rate limiting: add delay before each request
                if attempt == 0:
                    time.sleep(self.REQUEST_DELAY_SECONDS)
                else:
                    # Exponential backoff for retries: 1s, 2s, 4s
                    backoff_delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    self.logger.info(
                        f"Retry {attempt}/{self.MAX_RETRIES} for {endpoint} after {backoff_delay}s backoff"
                    )
                    time.sleep(backoff_delay)

                self.logger.info(
                    f"Fetching summary: {endpoint} "
                    f"(range: {start_time.isoformat()} to {end_time.isoformat()}, "
                    f"cpt={pull_token[:15]}...)"
                )
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(url, params=params, headers=headers)

                    self.logger.info(f"Summary response: {endpoint} returned {response.status_code}")

                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list):
                            self.logger.info(f"Summary {endpoint}: received {len(data)} records")
                            return data
                        if data:
                            self.logger.info(f"Summary {endpoint}: received 1 record")
                            return [data]
                        self.logger.info(f"Summary {endpoint}: no records in response")
                        return []

                    if response.status_code == 204:
                        # No content - valid response, just no data
                        self.logger.info(f"Summary {endpoint}: no data (204)")
                        return []

                    if response.status_code == 429:
                        # Rate limited - retry with backoff
                        if attempt < self.MAX_RETRIES:
                            self.logger.warning(
                                f"Rate limited (429) on {endpoint}, will retry ({attempt + 1}/{self.MAX_RETRIES})"
                            )
                            continue
                        self.logger.error(
                            f"Rate limited (429) on {endpoint}, max retries exceeded"
                        )
                        return []

                    self.logger.warning(
                        f"Summary request failed: {endpoint} returned {response.status_code}: {response.text[:500]}"
                    )
                    return []

            except httpx.HTTPError as e:
                self.logger.error(f"HTTP error fetching {endpoint}: {e}")
                if attempt < self.MAX_RETRIES:
                    continue
                return []

        return []

    def _fetch_with_chunks(
        self,
        endpoint: str,
        access_token: str,
        pull_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch data in 24-hour chunks (Garmin limit).

        Args:
            endpoint: API endpoint path
            access_token: User's OAuth Bearer token
            pull_token: Consumer Pull Token (CPT)
            start_time: Start of date range
            end_time: End of date range

        Returns:
            Combined list of data items from all chunks
        """
        all_data: list[dict[str, Any]] = []
        current_start = start_time

        while current_start < end_time:
            # Calculate chunk end (max 24 hours)
            chunk_end = min(
                current_start + timedelta(seconds=self.MAX_REQUEST_SECONDS),
                end_time,
            )

            chunk_data = self._make_summary_request(endpoint, access_token, pull_token, current_start, chunk_end)
            all_data.extend(chunk_data)

            current_start = chunk_end

        return all_data

    def fetch_single_chunk(
        self,
        db: DbSession,
        user_id: UUID,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch a single 24-hour chunk of data for a specific data type.

        This method is designed for use by the Celery task for rate-limited
        chunk-by-chunk fetching over 365 days.

        Args:
            db: Database session
            user_id: User ID to fetch data for
            data_type: Data type key (e.g., "dailies", "sleeps", "hrv")
            start_time: Start of 24-hour chunk
            end_time: End of 24-hour chunk (max 24 hours from start)

        Returns:
            List of data items from the endpoint

        Raises:
            ValueError: If data_type is not recognized
        """
        endpoint = self.SUMMARY_ENDPOINTS.get(data_type)
        if not endpoint:
            raise ValueError(f"Unknown data type: {data_type}")

        # Get user's OAuth access token
        access_token = self._get_user_access_token(db, user_id)
        if not access_token:
            self.logger.error(f"No Garmin connection found for user {user_id}")
            return []

        # Generate Consumer Pull Token (CPT)
        pull_token = generate_garmin_pull_token()
        if not pull_token:
            self.logger.error("Failed to generate Garmin pull token")
            return []

        return self._make_summary_request(endpoint, access_token, pull_token, start_time, end_time)

    def fetch_and_save_single_chunk(
        self,
        db: DbSession,
        user_id: UUID,
        data_type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Fetch a single chunk and save to database.

        This method is the main entry point for the Celery task.
        It fetches one 24-hour chunk of a specific data type and persists it.

        Args:
            db: Database session
            user_id: User ID to fetch data for
            data_type: Data type key (e.g., "dailies", "sleeps", "hrv")
            start_time: Start of 24-hour chunk
            end_time: End of 24-hour chunk

        Returns:
            Dict with fetch and save results:
            {
                "data_type": str,
                "fetched": int,
                "saved": int,
                "error": str | None
            }
        """
        result = {
            "data_type": data_type,
            "fetched": 0,
            "saved": 0,
            "error": None,
        }

        try:
            # Fetch the chunk
            data = self.fetch_single_chunk(db, user_id, data_type, start_time, end_time)
            result["fetched"] = len(data)

            if not data:
                return result

            # Import Garmin247Data for saving
            from app.models.user import User
            from app.repositories.user_repository import UserRepository
            from app.services.providers.garmin.data_247 import Garmin247Data
            from app.services.providers.garmin.oauth import GarminOAuth

            user_repo = UserRepository(User)
            oauth = GarminOAuth(
                user_repo=user_repo,
                connection_repo=self.connection_repo,
                provider_name="garmin",
                api_base_url=self.API_BASE_URL,
            )
            data_247 = Garmin247Data(
                provider_name="garmin",
                api_base_url=self.API_BASE_URL,
                oauth=oauth,
            )

            # Save based on data type
            saved_count = 0
            if data_type == "dailies":
                for item in data:
                    normalized = data_247.normalize_dailies(item, user_id)
                    saved_count += data_247.save_dailies_data(db, user_id, normalized)
            elif data_type == "sleeps":
                for item in data:
                    normalized = data_247.normalize_sleep(item, user_id)
                    data_247.save_sleep_data(db, user_id, normalized)
                    saved_count += 1
            elif data_type == "epochs":
                normalized = data_247.normalize_epochs(data, user_id)
                saved_count = data_247.save_epochs_data(db, user_id, normalized)
            elif data_type == "bodyComps":
                for item in data:
                    saved_count += data_247.save_body_composition(db, user_id, item)
            elif data_type == "hrv":
                for item in data:
                    saved_count += data_247.save_hrv_data(db, user_id, item)
            elif data_type == "activities":
                for item in data:
                    saved_count += data_247.save_activity_data(db, user_id, item)
            elif data_type == "stressDetails":
                for item in data:
                    saved_count += data_247.save_stress_data(db, user_id, item)
            elif data_type == "respiration":
                for item in data:
                    saved_count += data_247.save_respiration_data(db, user_id, item)
            elif data_type == "pulseOx":
                for item in data:
                    saved_count += data_247.save_pulse_ox_data(db, user_id, item)
            elif data_type == "bloodPressures":
                for item in data:
                    saved_count += data_247.save_blood_pressure_data(db, user_id, item)
            elif data_type == "userMetrics":
                for item in data:
                    saved_count += data_247.save_user_metrics_data(db, user_id, item)
            elif data_type == "skinTemp":
                for item in data:
                    saved_count += data_247.save_skin_temp_data(db, user_id, item)
            elif data_type == "healthSnapshot":
                for item in data:
                    saved_count += data_247.save_health_snapshot_data(db, user_id, item)
            elif data_type == "moveiq":
                for item in data:
                    saved_count += data_247.save_moveiq_data(db, user_id, item)
            elif data_type == "mct":
                for item in data:
                    saved_count += data_247.save_mct_data(db, user_id, item)
            elif data_type == "activityDetails":
                # Activity details are supplementary; skip for now
                self.logger.debug("Skipping activityDetails save (supplementary data)")
            else:
                self.logger.warning(f"No save handler for data type: {data_type}")

            result["saved"] = saved_count

        except Exception as e:
            self.logger.error(f"Error processing {data_type} chunk: {e}")
            result["error"] = str(e)

        return result

    def fetch_all_summaries(
        self,
        db: DbSession,
        user_id: UUID,
        days: int = 7,
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch all summary data types for the last N days (max 7).

        This provides immediate data without waiting for backfill webhooks.

        Args:
            db: Database session
            user_id: User ID to fetch data for
            days: Number of days to fetch (max 7)
            data_types: List of data types to fetch (defaults to all)

        Returns:
            Dict with results for each data type:
            {
                "dailies": {"data": [...], "count": 7, "error": None},
                "sleeps": {"data": [...], "count": 7, "error": None},
                ...
                "summary": {
                    "total_records": 35,
                    "successful_types": ["dailies", "sleeps", ...],
                    "failed_types": [],
                    "days_requested": 7
                }
            }
        """
        # Get user's OAuth access token
        access_token = self._get_user_access_token(db, user_id)
        if not access_token:
            return {
                "error": f"No Garmin connection found for user {user_id}",
                "summary": {
                    "total_records": 0,
                    "successful_types": [],
                    "failed_types": list(self.SUMMARY_ENDPOINTS.keys()),
                    "days_requested": min(days, self.MAX_SUMMARY_DAYS),
                },
            }

        # Generate Consumer Pull Token (CPT)
        pull_token = generate_garmin_pull_token()
        if not pull_token:
            return {
                "error": "Failed to generate Garmin pull token",
                "summary": {
                    "total_records": 0,
                    "successful_types": [],
                    "failed_types": list(self.SUMMARY_ENDPOINTS.keys()),
                    "days_requested": min(days, self.MAX_SUMMARY_DAYS),
                },
            }

        # Calculate time range
        days = min(days, self.MAX_SUMMARY_DAYS)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        # Determine which data types to fetch
        if data_types is None:
            data_types = list(self.SUMMARY_ENDPOINTS.keys())

        results: dict[str, Any] = {}
        total_records = 0
        successful_types: list[str] = []
        failed_types: list[str] = []

        self.logger.info(f"Fetching {len(data_types)} summary types for last {days} days for user {user_id}")

        for data_type in data_types:
            endpoint = self.SUMMARY_ENDPOINTS.get(data_type)
            if not endpoint:
                results[data_type] = {"data": [], "error": f"Unknown type: {data_type}"}
                failed_types.append(data_type)
                continue

            try:
                # Fetch with 24-hour chunks
                data = self._fetch_with_chunks(endpoint, access_token, pull_token, start_time, end_time)
                results[data_type] = {
                    "data": data,
                    "count": len(data),
                    "error": None,
                }
                total_records += len(data)
                successful_types.append(data_type)
                self.logger.info(f"Fetched {len(data)} {data_type} records")

            except Exception as e:
                self.logger.error(f"Error fetching {data_type}: {e}")
                results[data_type] = {"data": [], "count": 0, "error": str(e)}
                failed_types.append(data_type)

        results["summary"] = {
            "total_records": total_records,
            "successful_types": successful_types,
            "failed_types": failed_types,
            "days_requested": days,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }

        return results

    def fetch_and_save_all_summaries(
        self,
        db: DbSession,
        user_id: UUID,
        days: int = 7,
    ) -> dict[str, Any]:
        """Fetch summary data and save to database.

        This combines fetch_all_summaries() with the save methods from
        Garmin247Data to persist the data.

        Args:
            db: Database session
            user_id: User ID to associate data with
            days: Number of days to fetch (max 7)

        Returns:
            Dict with fetch and save results
        """
        # Import here to avoid circular import
        from app.models.user import User
        from app.repositories.user_repository import UserRepository
        from app.services.providers.garmin.data_247 import Garmin247Data
        from app.services.providers.garmin.oauth import GarminOAuth

        # Fetch all summaries (now requires db and user_id)
        fetch_results = self.fetch_all_summaries(db=db, user_id=user_id, days=days)

        if fetch_results.get("error"):
            return fetch_results

        # Initialize Garmin247Data for saving
        user_repo = UserRepository(User)
        oauth = GarminOAuth(
            user_repo=user_repo,
            connection_repo=self.connection_repo,
            provider_name="garmin",
            api_base_url=self.API_BASE_URL,
        )
        data_247 = Garmin247Data(
            provider_name="garmin",
            api_base_url=self.API_BASE_URL,
            oauth=oauth,
        )

        save_results: dict[str, Any] = {}
        total_saved = 0

        # Save dailies
        if "dailies" in fetch_results and fetch_results["dailies"].get("data"):
            count = 0
            for item in fetch_results["dailies"]["data"]:
                try:
                    normalized = data_247.normalize_dailies(item, user_id)
                    count += data_247.save_dailies_data(db, user_id, normalized)
                except Exception as e:
                    self.logger.warning(f"Failed to save daily: {e}")
            save_results["dailies"] = count
            total_saved += count

        # Save sleeps
        if "sleeps" in fetch_results and fetch_results["sleeps"].get("data"):
            count = 0
            for item in fetch_results["sleeps"]["data"]:
                try:
                    normalized = data_247.normalize_sleep(item, user_id)
                    data_247.save_sleep_data(db, user_id, normalized)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to save sleep: {e}")
            save_results["sleeps"] = count
            total_saved += count

        # Save epochs
        if "epochs" in fetch_results and fetch_results["epochs"].get("data"):
            try:
                normalized = data_247.normalize_epochs(fetch_results["epochs"]["data"], user_id)
                count = data_247.save_epochs_data(db, user_id, normalized)
                save_results["epochs"] = count
                total_saved += count
            except Exception as e:
                self.logger.warning(f"Failed to save epochs: {e}")
                save_results["epochs"] = 0

        # Save body composition
        if "bodyComps" in fetch_results and fetch_results["bodyComps"].get("data"):
            count = 0
            for item in fetch_results["bodyComps"]["data"]:
                try:
                    count += data_247.save_body_composition(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save body comp: {e}")
            save_results["bodyComps"] = count
            total_saved += count

        # Save HRV
        if "hrv" in fetch_results and fetch_results["hrv"].get("data"):
            count = 0
            for item in fetch_results["hrv"]["data"]:
                try:
                    count += data_247.save_hrv_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save HRV: {e}")
            save_results["hrv"] = count
            total_saved += count

        # Save activities (workouts)
        if "activities" in fetch_results and fetch_results["activities"].get("data"):
            count = 0
            for item in fetch_results["activities"]["data"]:
                try:
                    count += data_247.save_activity_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save activity: {e}")
            save_results["activities"] = count
            total_saved += count

        # Save stress data
        if "stressDetails" in fetch_results and fetch_results["stressDetails"].get("data"):
            count = 0
            for item in fetch_results["stressDetails"]["data"]:
                try:
                    count += data_247.save_stress_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save stress: {e}")
            save_results["stressDetails"] = count
            total_saved += count

        # Save respiration data
        if "respiration" in fetch_results and fetch_results["respiration"].get("data"):
            count = 0
            for item in fetch_results["respiration"]["data"]:
                try:
                    count += data_247.save_respiration_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save respiration: {e}")
            save_results["respiration"] = count
            total_saved += count

        # Save pulse ox data
        if "pulseOx" in fetch_results and fetch_results["pulseOx"].get("data"):
            count = 0
            for item in fetch_results["pulseOx"]["data"]:
                try:
                    count += data_247.save_pulse_ox_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save pulse ox: {e}")
            save_results["pulseOx"] = count
            total_saved += count

        # Save blood pressure data
        if "bloodPressures" in fetch_results and fetch_results["bloodPressures"].get("data"):
            count = 0
            for item in fetch_results["bloodPressures"]["data"]:
                try:
                    count += data_247.save_blood_pressure_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save blood pressure: {e}")
            save_results["bloodPressures"] = count
            total_saved += count

        # Save user metrics (VO2max, fitness age)
        if "userMetrics" in fetch_results and fetch_results["userMetrics"].get("data"):
            count = 0
            for item in fetch_results["userMetrics"]["data"]:
                try:
                    count += data_247.save_user_metrics_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save user metrics: {e}")
            save_results["userMetrics"] = count
            total_saved += count

        # Save skin temperature data
        if "skinTemp" in fetch_results and fetch_results["skinTemp"].get("data"):
            count = 0
            for item in fetch_results["skinTemp"]["data"]:
                try:
                    count += data_247.save_skin_temp_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save skin temp: {e}")
            save_results["skinTemp"] = count
            total_saved += count

        # Save health snapshot data
        if "healthSnapshot" in fetch_results and fetch_results["healthSnapshot"].get("data"):
            count = 0
            for item in fetch_results["healthSnapshot"]["data"]:
                try:
                    count += data_247.save_health_snapshot_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save health snapshot: {e}")
            save_results["healthSnapshot"] = count
            total_saved += count

        # Save Move IQ data (auto-detected activities)
        if "moveiq" in fetch_results and fetch_results["moveiq"].get("data"):
            count = 0
            for item in fetch_results["moveiq"]["data"]:
                try:
                    count += data_247.save_moveiq_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save moveiq: {e}")
            save_results["moveiq"] = count
            total_saved += count

        # Save menstrual cycle data
        if "mct" in fetch_results and fetch_results["mct"].get("data"):
            count = 0
            for item in fetch_results["mct"]["data"]:
                try:
                    count += data_247.save_mct_data(db, user_id, item)
                except Exception as e:
                    self.logger.warning(f"Failed to save mct: {e}")
            save_results["mct"] = count
            total_saved += count

        return {
            "fetch_results": fetch_results["summary"],
            "save_results": save_results,
            "total_saved": total_saved,
        }


# Convenience function for easy import
def fetch_garmin_summaries(db: DbSession, user_id: UUID, days: int = 7) -> dict[str, Any]:
    """Fetch all Garmin summary data for the last N days.

    Args:
        db: Database session
        user_id: User ID to fetch data for
        days: Number of days to fetch (max 7)

    Returns:
        Dict with results for each data type
    """
    service = GarminSummaryService()
    return service.fetch_all_summaries(db=db, user_id=user_id, days=days)
