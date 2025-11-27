import json
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
import hashlib
from base64 import b64encode, urlsafe_b64encode

import httpx
import redis
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from app.config import settings
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.oauth import (
    AuthenticationMethod,
    OAuthState,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
    UserConnectionCreate,
)


class BaseOAuthTemplate(ABC):
    """Base template for OAuth 2.0 authentication flow."""

    def __init__(
        self,
        user_repo: UserRepository,
        connection_repo: UserConnectionRepository,
    ):
        self.user_repo = user_repo
        self.connection_repo = connection_repo
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self.state_ttl = 900  # 15 minutes

    @property
    @abstractmethod
    def endpoints(self) -> ProviderEndpoints:
        pass

    @property
    @abstractmethod
    def credentials(self) -> ProviderCredentials:
        pass

    use_pkce: bool = False
    auth_method: AuthenticationMethod = AuthenticationMethod.BASIC_AUTH

    def get_authorization_url(self, user_id: UUID, redirect_uri: str | None = None) -> tuple[str, str]:
        """Generates the provider's authorization URL.

        Returns:
            tuple[str, str]: The authorization URL and the state.
        """
        state = secrets.token_urlsafe(32)  # random state 32-bytes (Base64 encoding)

        oauth_state = OAuthState(
            user_id=user_id,
            provider=self.credentials.name,
            redirect_uri=redirect_uri or self.credentials.redirect_uri,
        )

        auth_url, pkce_data = self._build_auth_url(state)

        redis_key = f"oauth_state:{state}"
        state_data = oauth_state.model_dump(mode="json")
        if pkce_data:
            state_data.update(pkce_data)
        self.redis_client.setex(redis_key, self.state_ttl, json.dumps(state_data))

        return auth_url, state

    def handle_callback(self, db: DbSession, user_id: UUID, code: str, state: str) -> OAuthState:
        """Handles the OAuth callback, exchanges code, and saves the connection."""
        oauth_state, code_verifier = self._validate_state(state)

        if oauth_state.user_id != user_id:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="User mismatch in state")

        if oauth_state.provider != self.credentials.name:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Provider mismatch in state")

        token_response = self._exchange_token(code, code_verifier)

        user_info = self._get_provider_user_info(token_response, str(user_id))

        self._save_connection(db, user_id, token_response, user_info, oauth_state)

        return oauth_state

    def refresh_access_token(self, db: DbSession, user_id: UUID, refresh_token: str) -> OAuthTokenResponse:
        """Refreshes the access token using the refresh token."""
        data, headers = self._prepare_refresh_request(refresh_token)

        try:
            response = httpx.post(
                self.endpoints.token_url,
                data=data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            token_response = OAuthTokenResponse.model_validate(response.json())

            connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.credentials.name)
            if connection:
                self.connection_repo.update_tokens(
                    db,
                    connection,
                    token_response.access_token,
                    token_response.refresh_token or refresh_token,  # Use old refresh token if new one not provided
                    token_response.expires_in,
                )

            return token_response

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail=f"Failed to refresh token: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Token refresh failed: {str(e)}")

    def _build_auth_url(self, state: str) -> tuple[str, dict[str, Any] | None]:
        """Builds the authorization URL.

        Returns:
            tuple: (authorization_url, pkce_data_or_None)
        """
        pkce_data = None
        extra_params = ""

        if self.use_pkce:
            code_verifier, code_challenge = self._generate_pkce_pair()
            extra_params = f"&code_challenge={code_challenge}&code_challenge_method=S256"
            pkce_data = {"code_verifier": code_verifier}

        auth_url = (
            f"{self.endpoints.authorize_url}?"
            f"response_type=code&"
            f"client_id={self.credentials.client_id}&"
            f"redirect_uri={self.credentials.redirect_uri}&"
            f"state={state}"
            f"{extra_params}"
        )

        if self.credentials.default_scope:
            auth_url += f"&scope={self.credentials.default_scope}"

        # pkce_data will be None for non-PKCE providers
        return auth_url, pkce_data

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generates PKCE code verifier and challenge."""
        code_verifier = secrets.token_urlsafe(43)
        challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = urlsafe_b64encode(challenge_bytes).decode().rstrip("=")

        return code_verifier, code_challenge

    def _validate_state(self, state: str) -> tuple[OAuthState, str | None]:
        """Validates and consumes the OAuth state from Redis."""
        redis_key = f"oauth_state:{state}"
        state_data = self.redis_client.get(redis_key)

        if not state_data:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Invalid or expired state parameter")

        # Delete state immediately (one-time use)
        self.redis_client.delete(redis_key)

        state_dict = json.loads(state_data)
        code_verifier = state_dict.pop("code_verifier", None)
        oauth_state = OAuthState.model_validate(state_dict)

        # code_verifier will be None for non-PKCE providers
        return oauth_state, code_verifier

    def _exchange_token(self, code: str, code_verifier: str | None) -> OAuthTokenResponse:
        """Exchanges authorization code for tokens."""
        data, headers = self._prepare_token_request(code, code_verifier)

        try:
            response = httpx.post(
                self.endpoints.token_url,
                data=data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return OAuthTokenResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST, detail=f"Failed to exchange authorization code: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Token exchange failed: {str(e)}")

    def _prepare_token_request(self, code: str, code_verifier: str | None) -> tuple[dict, dict]:
        """Prepares the token exchange request. Default implementation uses Basic Auth."""

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.credentials.redirect_uri,
        }

        if self.use_pkce and code_verifier:
            token_data["code_verifier"] = code_verifier

        if self.auth_method == AuthenticationMethod.BODY:
            token_data["client_id"] = self.credentials.client_id
            token_data["client_secret"] = self.credentials.client_secret
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
        else:
            headers = self._get_basic_auth_headers()

        return token_data, headers

    def _prepare_refresh_request(self, refresh_token: str) -> tuple[dict, dict]:
        """Prepares the token refresh request. Default implementation uses Basic Auth."""
        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        if self.auth_method == AuthenticationMethod.BODY:
            token_data["client_id"] = self.credentials.client_id
            token_data["client_secret"] = self.credentials.client_secret
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
        else:
            headers = self._get_basic_auth_headers()

        return token_data, headers

    def _get_basic_auth_headers(self) -> dict:
        """Generates Basic Auth headers for token requests."""
        credentials = f"{self.credentials.client_id}:{self.credentials.client_secret}"
        b64_credentials = b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts provider user info. Default implementation returns None."""
        return {"user_id": None, "username": None}

    def _save_connection(
        self,
        db: DbSession,
        user_id: UUID,
        token_response: OAuthTokenResponse,
        user_info: dict[str, str | None],
        oauth_state: OAuthState,
    ) -> None:
        """Saves or updates the user connection."""
        provider_user_id = user_info.get("user_id")
        provider_username = user_info.get("username")

        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_response.expires_in)

        existing_connection = self.connection_repo.get_by_user_and_provider(
            db,
            user_id,
            self.credentials.name,
        )

        if existing_connection:
            self.connection_repo.update_tokens(
                db,
                existing_connection,
                token_response.access_token,
                token_response.refresh_token,
                token_response.expires_in,
            )
        else:
            connection_create = UserConnectionCreate(
                user_id=user_id,
                provider=self.credentials.name,
                provider_user_id=provider_user_id,
                provider_username=provider_username,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_expires_at=token_expires_at,
                scope=token_response.scope,
            )
            self.connection_repo.create(db, connection_create)

    def get_valid_token(self, db: DbSession, user_id: UUID) -> str:
        """Get a valid access token, refreshing if necessary."""
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.credentials.name)
        if not connection:
            raise HTTPException(
                status_code=401,
                detail=f"User not connected to {self.credentials.name}",
            )

        # Check if token is expired (with 5 minute buffer)
        if connection.token_expires_at < datetime.now(timezone.utc) + timedelta(minutes=5):
            if not connection.refresh_token:
                raise HTTPException(
                    status_code=401,
                    detail=f"Token expired and no refresh token available for {self.credentials.name}",
                )
            token_response = self.refresh_access_token(db, user_id, connection.refresh_token)
            return token_response.access_token

        return connection.access_token

    def make_api_request(
        self,
        db: DbSession,
        user_id: UUID,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Make authenticated request to vendor API.

        Args:
            db: Database session
            user_id: User ID
            endpoint: API endpoint path
            method: HTTP method (default: GET)
            params: Query parameters
            headers: Additional headers

        Returns:
            Any: API response JSON

        Raises:
            HTTPException: If API request fails
        """
        # Get valid access token (will auto-refresh if needed)
        access_token = self.get_valid_token(db, user_id)

        # Prepare headers
        request_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        # Make request
        url = f"{self.endpoints.api_base_url}{endpoint}"

        try:
            response = httpx.request(
                method=method,
                url=url,
                headers=request_headers,
                params=params or {},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            # No logger here, so we just raise
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail=f"{self.credentials.name.capitalize()} authorization expired. Please re-authorize.",
                )
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"{self.credentials.name.capitalize()} API error: {e.response.text}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch data from {self.credentials.name.capitalize()}: {str(e)}",
            )
