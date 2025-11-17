from logging import Logger, getLogger
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException

from app.config import settings
from app.database import DbSession
from app.services.oauth_service import oauth_service


class SuuntoService:
    """Service for interacting with Suunto API."""

    def __init__(self, log: Logger):
        self.logger = log
        self.provider = "suunto"
        self.api_base_url = settings.suunto_api_base_url
        self.subscription_key = settings.suunto_subscription_key.get_secret_value()

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
    ) -> dict:
        """Make authenticated request to Suunto API."""
        # Get valid access token (will auto-refresh if needed)
        access_token = oauth_service.get_valid_token(db, user_id, self.provider)

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }

        # Make request
        url = f"{self.api_base_url}{endpoint}"

        try:
            response = httpx.request(
                method=method,
                url=url,
                headers=headers,
                params=params or {},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"Suunto API error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail="Suunto authorization expired. Please re-authorize.",
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Suunto API error: {e.response.text}",
            )
        except Exception as e:
            self.logger.error(f"Suunto API request failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch data from Suunto")

    def get_workouts(
        self,
        db: DbSession,
        user_id: UUID,
        since: int = 0,
        limit: int = 50,
        offset: int = 0,
        filter_by_modification_time: bool = True,
    ) -> dict:
        """Get workouts from Suunto API.

        Args:
            db: Database session
            user_id: User ID
            since: Unix timestamp to get workouts since (default: 0 = all)
            limit: Maximum number of workouts to return (default: 50, max: 100)
            offset: Offset for pagination (default: 0)
            filter_by_modification_time: Filter by modification time instead of creation time

        Returns:
            dict: Suunto API response with workouts list
        """
        params = {
            "since": since,
            "limit": min(limit, 100),  # Suunto max is 100
            "offset": offset,
            "filter-by-modification-time": str(filter_by_modification_time).lower(),
        }

        self.logger.info(f"Fetching workouts for user {user_id} from Suunto API")
        return self._make_api_request(db, user_id, "/v3/workouts/", params=params)

    def get_workout_detail(
        self,
        db: DbSession,
        user_id: UUID,
        workout_key: str,
    ) -> dict:
        """Get detailed workout data from Suunto API.

        Args:
            db: Database session
            user_id: User ID
            workout_key: Suunto workout key/ID

        Returns:
            dict: Detailed workout data
        """
        self.logger.info(f"Fetching workout {workout_key} for user {user_id} from Suunto API")
        return self._make_api_request(db, user_id, f"/v3/workouts/{workout_key}")


suunto_service = SuuntoService(log=getLogger(__name__))
