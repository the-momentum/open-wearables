import json
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
import redis
from fastapi import HTTPException
from fastapi.status import HTTP_400_BAD_REQUEST

from app.config import settings
from app.database import DbSession
from app.repositories.user_connection_repository import UserConnectionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.oauth import OAuthState, OAuthTokenResponse, ProviderConfig, UserConnectionCreate


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
    def config(self) -> ProviderConfig:
        """Returns the provider configuration."""
        pass

    def get_authorization_url(self, user_id: UUID, redirect_uri: str | None = None) -> str:
        """Generates the provider's authorization URL.

        Returns:
            str: The authorization URL to redirect the user to.
        """
        state = secrets.token_urlsafe(32)  # random state 32-bytes (Base64 encoding)

        oauth_state = OAuthState(
            user_id=user_id,
            provider=self.config.name,
            redirect_uri=redirect_uri or self.config.redirect_uri,
        )

        auth_url, pkce_data = self._build_auth_url(state)

        # Save state to Redis
        redis_key = f"oauth_state:{state}"
        if pkce_data:
            state_data = oauth_state.model_dump(mode="json")
            state_data.update(pkce_data)
            self.redis_client.setex(redis_key, self.state_ttl, json.dumps(state_data))
        else:
            self.redis_client.setex(redis_key, self.state_ttl, oauth_state.model_dump_json())

        return auth_url

    def handle_callback(self, db: DbSession, user_id: UUID, code: str, state: str) -> None:
        """Handles the OAuth callback, exchanges code, and saves the connection.

        Args:
            db: The database session.
            user_id: The ID of the user authenticating.
            code: The authorization code received from the provider.
            state: The state parameter received from the provider.
        """
        # 1. Validate state and get PKCE data
        oauth_state, code_verifier = self._validate_state(state)

        if oauth_state.user_id != user_id:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="User mismatch in state")

        if oauth_state.provider != self.config.name:
            raise HTTPException(status_code=HTTP_400_BAD_REQUEST, detail="Provider mismatch in state")

        # 2. Exchange code for token
        token_response = self._exchange_token(code, code_verifier)

        # 3. Get provider user info
        user_info = self._get_provider_user_info(token_response, str(user_id))

        # 4. Create or update the user connection
        self._save_connection(db, user_id, token_response, user_info, oauth_state)

    def _build_auth_url(self, state: str) -> tuple[str, dict[str, Any] | None]:
        """Builds the authorization URL.

        Returns:
            tuple: (authorization_url, pkce_data_or_None)
        """
        auth_url = (
            f"{self.config.authorize_url}?"
            f"response_type=code&"
            f"client_id={self.config.client_id}&"
            f"redirect_uri={self.config.redirect_uri}&"
            f"state={state}"
        )

        if self.config.default_scope:
            auth_url += f"&scope={self.config.default_scope}"

        return auth_url, None

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

        # try:
        #     state_dict = json.loads(state_data)
        #     code_verifier = state_dict.pop("code_verifier", None)
        #     oauth_state = OAuthState.model_validate(state_dict)
        #     return oauth_state, code_verifier
        # except (json.JSONDecodeError, KeyError):
        #     # Fallback for non-PKCE providers
        #     oauth_state = OAuthState.model_validate_json(state_data)
        #     return oauth_state, None

    def _exchange_token(self, code: str, code_verifier: str | None) -> OAuthTokenResponse:
        """Exchanges authorization code for tokens."""
        data, headers = self._prepare_token_request(code, code_verifier)

        try:
            response = httpx.post(
                self.config.token_url,
                data=data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return OAuthTokenResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            # Log error here if logger available
            raise HTTPException(status_code=400, detail=f"Failed to exchange authorization code: {e.response.text}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Token exchange failed: {str(e)}")

    def _prepare_token_request(self, code: str, code_verifier: str | None) -> tuple[dict, dict]:
        """Prepares the token exchange request. Default implementation uses Basic Auth."""
        from base64 import b64encode

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }

        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        b64_credentials = b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        return token_data, headers

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
            self.config.name,
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
                provider=self.config.name,
                provider_user_id=provider_user_id,
                provider_username=provider_username,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_expires_at=token_expires_at,
                scope=token_response.scope,
            )
            self.connection_repo.create(db, connection_create)

    # Deprecated abstract methods removed
