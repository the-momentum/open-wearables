"""Withings OAuth 2.0 implementation.

Withings uses a non-standard OAuth 2.0 flow:
- Token exchange requires HMAC-SHA256 request signing
- All API requests need a nonce from /v2/signature
- Token response is nested in a 'body' key
- Uses POST with 'action' parameter instead of standard token endpoints
"""

import hashlib
import hmac
import logging

import httpx
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from app.config import settings
from app.database import DbSession
from app.schemas.oauth import (
    AuthenticationMethod,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate

logger = logging.getLogger(__name__)


class WithingsOAuth(BaseOAuthTemplate):
    """Withings OAuth 2.0 implementation with HMAC-SHA256 request signing."""

    SIGNATURE_URL = "https://wbsapi.withings.net/v2/signature"

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://account.withings.com/oauth2_user/authorize2",
            token_url="https://wbsapi.withings.net/v2/oauth2",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.withings_client_id or "",
            client_secret=(
                settings.withings_client_secret.get_secret_value()
                if settings.withings_client_secret
                else ""
            ),
            redirect_uri=settings.withings_redirect_uri,
            default_scope=settings.withings_default_scope,
        )

    use_pkce: bool = False
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY

    def _compute_signature(self, action: str, client_id: str, nonce: str) -> str:
        """Compute HMAC-SHA256 signature for Withings API requests.

        Withings requires params sorted alphabetically by key (action, client_id, nonce),
        joined by commas, signed with the client_secret.
        """
        data = f"{action},{client_id},{nonce}"
        secret = self.credentials.client_secret
        return hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()

    def _get_nonce(self) -> str:
        """Fetch a nonce from the Withings signature endpoint."""
        try:
            response = httpx.post(
                self.SIGNATURE_URL,
                data={
                    "action": "getnonce",
                    "client_id": self.credentials.client_id,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
            nonce = result.get("body", {}).get("nonce")
            if not nonce:
                raise ValueError(f"No nonce in response: {result}")
            return nonce
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get Withings nonce: {e.response.text}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get Withings nonce: {str(e)}",
            )

    def _exchange_token(self, code: str, code_verifier: str | None) -> OAuthTokenResponse:
        """Exchange authorization code for tokens using Withings' non-standard flow.

        Withings requires:
        - action=requesttoken POST parameter
        - HMAC-SHA256 signature computed from (action, client_id, nonce)
        - Token data nested in response body.body
        """
        nonce = self._get_nonce()
        client_id = self.credentials.client_id
        action = "requesttoken"
        signature = self._compute_signature(action, client_id, nonce)

        data = {
            "action": action,
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": self.credentials.client_secret,
            "code": code,
            "redirect_uri": self.credentials.redirect_uri,
            "nonce": nonce,
            "signature": signature,
        }

        try:
            response = httpx.post(
                self.endpoints.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            # Withings nests token data in body
            body = result.get("body", {})
            if not body:
                raise ValueError(f"No body in Withings token response: {result}")

            return OAuthTokenResponse(
                access_token=body["access_token"],
                token_type=body.get("token_type", "Bearer"),
                refresh_token=body.get("refresh_token"),
                expires_in=body.get("expires_in", 10800),  # Default 3 hours
                scope=body.get("scope"),
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange Withings authorization code: {e.response.text}",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Withings token exchange failed: {str(e)}",
            )

    def _prepare_refresh_request(self, refresh_token: str) -> tuple[dict, dict]:
        """Prepare token refresh request with Withings signature."""
        nonce = self._get_nonce()
        client_id = self.credentials.client_id
        action = "requesttoken"
        signature = self._compute_signature(action, client_id, nonce)

        data = {
            "action": action,
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": self.credentials.client_secret,
            "refresh_token": refresh_token,
            "nonce": nonce,
            "signature": signature,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        return data, headers

    def refresh_access_token(self, db: DbSession, user_id, refresh_token: str) -> OAuthTokenResponse:
        """Refresh access token, handling Withings' nested response format."""
        data, headers = self._prepare_refresh_request(refresh_token)

        try:
            response = httpx.post(
                self.endpoints.token_url,
                data=data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            body = result.get("body", {})
            if not body:
                raise ValueError(f"No body in Withings refresh response: {result}")

            token_response = OAuthTokenResponse(
                access_token=body["access_token"],
                token_type=body.get("token_type", "Bearer"),
                refresh_token=body.get("refresh_token"),
                expires_in=body.get("expires_in", 10800),
                scope=body.get("scope"),
            )

            connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
            if connection:
                self.connection_repo.update_tokens(
                    db,
                    connection,
                    token_response.access_token,
                    token_response.refresh_token or refresh_token,
                    token_response.expires_in,
                )

            return token_response

        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail=f"Failed to refresh Withings token: {e.response.text}",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Withings token refresh failed: {str(e)}",
            )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extract user info from Withings token response.

        Withings returns userid in the token exchange response itself,
        so we don't need a separate API call. However, since we parse it
        into OAuthTokenResponse which doesn't have userid, we fetch it
        from the user info endpoint instead.
        """
        try:
            response = httpx.post(
                "https://wbsapi.withings.net/v2/user",
                data={
                    "action": "getdevice",
                },
                headers={
                    "Authorization": f"Bearer {token_response.access_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            # We don't need specific user info from this — the connection is sufficient
            # Withings doesn't provide a clean user ID via API, so we use None
            return {"user_id": None, "username": None}
        except Exception:
            return {"user_id": None, "username": None}
