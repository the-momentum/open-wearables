from abc import ABC
from logging import Logger
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException

from app.database import DbSession
from app.services.oauth_service import oauth_service


class BaseWorkoutService(ABC):
    """Base service for interacting with fitness vendor workout/exercise APIs."""

    def __init__(self, log: Logger, provider: str, api_base_url: str, extra_headers: dict[str, str] | None = None):
        """Initialize base workout service.

        Args:
            log: Logger instance
            provider: Provider name (e.g., 'suunto', 'polar')
            api_base_url: Base URL for the vendor API
            extra_headers: Optional vendor-specific headers (beyond Authorization)
        """
        self.logger = log
        self.provider = provider
        self.api_base_url = api_base_url
        self.extra_headers = extra_headers or {}

    def _get_api_headers(self, access_token: str) -> dict[str, str]:
        """Get headers for API requests.

        Args:
            access_token: OAuth access token

        Returns:
            dict: Headers for API requests
        """
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        headers.update(self.extra_headers)
        return headers

    def _make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
    ) -> dict:
        """Make authenticated request to vendor API.

        Args:
            db: Database session
            user_id: User ID
            endpoint: API endpoint path
            method: HTTP method (default: GET)
            params: Query parameters

        Returns:
            dict: API response

        Raises:
            HTTPException: If API request fails
        """
        # Get valid access token (will auto-refresh if needed)
        access_token = oauth_service.get_valid_token(db, user_id, self.provider)

        # Prepare headers
        headers = self._get_api_headers(access_token)

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
            self.logger.error(
                f"{self.provider.capitalize()} API error: {e.response.status_code} - {e.response.text}",
            )
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail=f"{self.provider.capitalize()} authorization expired. Please re-authorize.",
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"{self.provider.capitalize()} API error: {e.response.text}",
            )
        except Exception as e:
            self.logger.error(f"{self.provider.capitalize()} API request failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch data from {self.provider.capitalize()}",
            )
