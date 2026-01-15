"""Garmin Pull Token Service for programmatic token generation.

This service authenticates with the Garmin Developer Dashboard and generates
pull tokens that can be used to fetch user data directly from the API.
"""

import logging
import re

import httpx

from app.config import settings


class GarminPullTokenService:
    """Generate Garmin pull tokens programmatically.

    Pull tokens are normally only available via:
    1. PING webhooks (callbackURL contains token)
    2. Manual generation in Garmin Developer Dashboard

    This service automates option 2 by:
    1. Authenticating with consumerKey/consumerSecret
    2. POSTing to the consumerPullToken endpoint
    3. Extracting the token from the HTML response

    Tokens are valid for 24 hours.
    """

    LOGIN_URL = "https://apis.garmin.com/tools/login"
    TOKEN_URL = "https://apis.garmin.com/tools/consumerPullToken"

    def __init__(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
    ):
        """Initialize with Garmin API credentials.

        Args:
            consumer_key: Garmin client ID (defaults to settings.GARMIN_CLIENT_ID)
            consumer_secret: Garmin client secret (defaults to settings.GARMIN_CLIENT_SECRET)
        """
        self.consumer_key = consumer_key or settings.GARMIN_CLIENT_ID
        self.consumer_secret = consumer_secret or settings.GARMIN_CLIENT_SECRET
        self.logger = logging.getLogger(self.__class__.__name__)

        if not self.consumer_key or not self.consumer_secret:
            raise ValueError("Garmin consumer key and secret are required")

    def _login(self, client: httpx.Client) -> bool:
        """Authenticate with Garmin Developer Dashboard.

        Args:
            client: httpx client with cookie persistence

        Returns:
            True if login successful, False otherwise
        """
        try:
            response = client.post(
                self.LOGIN_URL,
                data={
                    "consumerKey": self.consumer_key,
                    "consumerSecret": self.consumer_secret,
                },
                follow_redirects=False,
            )

            # Successful login redirects to /tools/endpoints
            if response.status_code == 302:
                location = response.headers.get("location", "")
                if "endpoints" in location:
                    self.logger.info("Successfully authenticated with Garmin Dashboard")
                    return True
                if "unknownCredentials" in location:
                    self.logger.error("Invalid Garmin credentials")
                    return False

            self.logger.error(f"Unexpected login response: {response.status_code}")
            return False

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error during login: {e}")
            return False

    def _generate_token(self, client: httpx.Client) -> dict[str, str] | None:
        """Generate a new pull token.

        Args:
            client: Authenticated httpx client with session cookie

        Returns:
            Dict with 'token' and 'expires' keys, or None on failure
        """
        try:
            response = client.post(
                self.TOKEN_URL,
                headers={"Content-Length": "0"},
            )

            if response.status_code != 200:
                self.logger.error(f"Token generation failed: {response.status_code}")
                return None

            html = response.text

            # Extract token from HTML
            token_match = re.search(r'value="(CPT[^"]+)"', html)
            if not token_match:
                self.logger.error("Could not extract token from response")
                return None

            token = token_match.group(1)

            # Extract expiry from HTML: value="2026-01-15T12:38:33.094959160Z"
            expires_match = re.search(
                r'id="expires"[^>]*value="([^"]+)"',
                html,
            )
            expires = expires_match.group(1) if expires_match else ""

            self.logger.info(f"Generated pull token: {token[:20]}... (expires: {expires})")

            return {
                "token": token,
                "expires": expires,
            }

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error generating token: {e}")
            return None

    def generate_pull_token(self) -> dict[str, str] | None:
        """Generate a new Garmin pull token.

        This method:
        1. Authenticates with Garmin Developer Dashboard
        2. Generates a new pull token
        3. Returns the token and expiry

        Returns:
            Dict with 'token' and 'expires' keys:
            {
                "token": "<token>",
                "expires": "2026-01-15T12:38:33.094959160Z"
            }
            Returns None on failure.

        Example:
            service = GarminPullTokenService()
            result = service.generate_pull_token()
            if result:
                token = result["token"]
                # Use token with API: ?token=CPT...
        """
        with httpx.Client(follow_redirects=False) as client:
            if not self._login(client):
                return None

            return self._generate_token(client)

    def get_token_for_request(self) -> str | None:
        """Get a pull token ready to use in API requests.

        Convenience method that returns just the token string.

        Returns:
            Token string or None on failure
        """
        result = self.generate_pull_token()
        return result["token"] if result else None


# Singleton instance for easy import
_pull_token_service: GarminPullTokenService | None = None


def get_pull_token_service() -> GarminPullTokenService:
    """Get singleton pull token service instance."""
    global _pull_token_service
    if _pull_token_service is None:
        _pull_token_service = GarminPullTokenService()
    return _pull_token_service


def generate_garmin_pull_token() -> str | None:
    """Convenience function to generate a Garmin pull token.

    Returns:
        Token string or None on failure
    """
    try:
        service = get_pull_token_service()
        return service.get_token_for_request()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to generate pull token: {e}")
        return None
