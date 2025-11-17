import secrets
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from logging import Logger, getLogger
from uuid import UUID

import httpx
import jwt
import redis
from fastapi import HTTPException

from app.config import settings
from app.database import DbSession
from app.repositories import UserConnectionRepository
from app.schemas import (
    AuthorizationURLResponse,
    OAuthState,
    OAuthTokenResponse,
    ProviderConfig,
    UserConnectionCreate,
)


class OAuthService:
    """Service for managing OAuth flows with fitness providers."""

    def __init__(self, log: Logger):
        self.logger = log
        self.repository = UserConnectionRepository()
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        self.state_ttl = 900  # 15 minutes

    def get_provider_config(self, provider: str) -> ProviderConfig:
        """Get configuration for a specific provider."""
        configs = {
            "suunto": ProviderConfig(
                name="suunto",
                client_id=settings.suunto_client_id or "",
                client_secret=(
                    settings.suunto_client_secret.get_secret_value() if settings.suunto_client_secret else ""
                ),
                redirect_uri=settings.suunto_redirect_uri,
                authorize_url=settings.suunto_authorize_url,
                token_url=settings.suunto_token_url,
                api_base_url=settings.suunto_api_base_url,
                default_scope=settings.suunto_default_scope,
                subscription_key=(
                    settings.suunto_subscription_key.get_secret_value() if settings.suunto_subscription_key else ""
                ),
            ),
            "garmin": ProviderConfig(
                name="garmin",
                client_id=settings.garmin_client_id or "",
                client_secret=(
                    settings.garmin_client_secret.get_secret_value() if settings.garmin_client_secret else ""
                ),
                redirect_uri=settings.garmin_redirect_uri,
                authorize_url=settings.garmin_authorize_url,
                token_url=settings.garmin_token_url,
                api_base_url=settings.garmin_api_base_url,
                default_scope=settings.garmin_default_scope,
            ),
            "polar": ProviderConfig(
                name="polar",
                client_id=settings.polar_client_id or "",
                client_secret=(settings.polar_client_secret.get_secret_value() if settings.polar_client_secret else ""),
                redirect_uri=settings.polar_redirect_uri,
                authorize_url=settings.polar_authorize_url,
                token_url=settings.polar_token_url,
                api_base_url=settings.polar_api_base_url,
                default_scope=settings.polar_default_scope,
            ),
        }

        if provider not in configs:
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' not supported")

        config = configs[provider]
        if not config.client_id or not config.client_secret:
            raise HTTPException(
                status_code=503,
                detail=f"Provider '{provider}' is not configured. Missing credentials.",
            )

        return config

    def generate_authorization_url(
        self,
        user_id: UUID,
        provider: str,
        redirect_uri: str | None = None,
    ) -> AuthorizationURLResponse:
        """Generate authorization URL and save state to Redis."""
        config = self.get_provider_config(provider)

        # Generate random state
        state = secrets.token_urlsafe(32)

        # Save state to Redis
        oauth_state = OAuthState(
            user_id=user_id,
            provider=provider,
            redirect_uri=redirect_uri,
        )
        redis_key = f"oauth_state:{state}"
        self.redis_client.setex(
            redis_key,
            self.state_ttl,
            oauth_state.model_dump_json(),
        )

        # Build authorization URL
        auth_url = (
            f"{config.authorize_url}?"
            f"response_type=code&"
            f"client_id={config.client_id}&"
            f"redirect_uri={config.redirect_uri}&"
            f"state={state}"
        )

        if config.default_scope:
            auth_url += f"&scope={config.default_scope}"

        self.logger.info(f"Generated authorization URL for user {user_id} and provider {provider}")

        return AuthorizationURLResponse(authorization_url=auth_url, state=state)

    def validate_and_consume_state(self, state: str) -> OAuthState:
        """Validate state from Redis and consume it (one-time use)."""
        redis_key = f"oauth_state:{state}"
        state_data = self.redis_client.get(redis_key)

        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid or expired state parameter")

        # Delete state immediately (one-time use)
        self.redis_client.delete(redis_key)

        return OAuthState.model_validate_json(state_data)

    def exchange_code_for_tokens(
        self,
        db: DbSession,
        provider: str,
        code: str,
        state: str,
    ) -> dict:
        """Exchange authorization code for access tokens."""
        # Validate state
        oauth_state = self.validate_and_consume_state(state)

        if oauth_state.provider != provider:
            raise HTTPException(status_code=400, detail="Provider mismatch in state")

        config = self.get_provider_config(provider)

        # Prepare token request
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        }

        # Prepare Basic Auth header
        credentials = f"{config.client_id}:{config.client_secret}"
        b64_credentials = b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Exchange code for tokens
        try:
            response = httpx.post(
                config.token_url,
                data=token_data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            token_response = OAuthTokenResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Token exchange failed: {e.response.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
        except Exception as e:
            self.logger.error(f"Token exchange error: {str(e)}")
            raise HTTPException(status_code=500, detail="Token exchange failed")

        # Parse JWT to extract provider username (Suunto-specific)
        provider_username = None
        provider_user_id = None
        if provider == "suunto":
            try:
                decoded = jwt.decode(token_response.access_token, options={"verify_signature": False})
                provider_username = decoded.get("user")
                provider_user_id = decoded.get("sub")
            except Exception as e:
                self.logger.warning(f"Failed to parse JWT: {str(e)}")
        elif provider == "polar":
            # Polar returns x_user_id in token response
            provider_user_id = token_response.x_user_id

            # Register user with Polar API (required before accessing data)
            try:
                from app.services.polar_service import polar_service

                polar_service.register_user(
                    access_token=token_response.access_token,
                    member_id=str(oauth_state.user_id),
                )
                self.logger.info(f"Registered user {oauth_state.user_id} with Polar API")
            except Exception as e:
                self.logger.error(f"Failed to register user with Polar: {str(e)}")
                # Don't fail the entire flow - user might already be registered
                pass

        # Calculate token expiration
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_response.expires_in)

        # Create or update connection in database
        existing_connection = self.repository.get_by_user_and_provider(
            db,
            oauth_state.user_id,
            provider,
        )

        if existing_connection:
            # Update existing connection
            self.repository.update_tokens(
                db,
                existing_connection,
                token_response.access_token,
                token_response.refresh_token,
                token_response.expires_in,
            )
            self.logger.info(f"Updated connection for user {oauth_state.user_id} and provider {provider}")
        else:
            # Create new connection
            connection_create = UserConnectionCreate(
                user_id=oauth_state.user_id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_username=provider_username,
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                token_expires_at=token_expires_at,
                scope=token_response.scope,
            )
            self.repository.create(db, connection_create)
            self.logger.info(f"Created connection for user {oauth_state.user_id} and provider {provider}")

        return {
            "success": True,
            "user_id": str(oauth_state.user_id),
            "provider": provider,
            "redirect_uri": oauth_state.redirect_uri,
        }

    def refresh_access_token(
        self,
        db: DbSession,
        user_id: UUID,
        provider: str,
    ) -> str:
        """Refresh access token using refresh token."""
        connection = self.repository.get_active_connection(db, user_id, provider)

        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"No active connection found for user {user_id} and provider {provider}",
            )

        if not connection.refresh_token:
            raise HTTPException(status_code=400, detail="No refresh token available")

        config = self.get_provider_config(provider)

        # Prepare refresh request
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": connection.refresh_token,
        }

        # Prepare Basic Auth header
        credentials = f"{config.client_id}:{config.client_secret}"
        b64_credentials = b64encode(credentials.encode()).decode()
        headers = {
            "Authorization": f"Basic {b64_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            response = httpx.post(
                config.token_url,
                data=refresh_data,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            token_response = OAuthTokenResponse.model_validate(response.json())

            # Update tokens in database
            self.repository.update_tokens(
                db,
                connection,
                token_response.access_token,
                token_response.refresh_token or connection.refresh_token,
                token_response.expires_in,
            )

            self.logger.info(f"Refreshed token for user {user_id} and provider {provider}")
            return token_response.access_token

        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                # Refresh token is invalid/revoked
                self.repository.mark_as_revoked(db, connection)
                self.logger.warning(f"Refresh token revoked for user {user_id} and provider {provider}")
                raise HTTPException(
                    status_code=401,
                    detail="Authorization revoked. Please re-authorize the application.",
                )
            raise HTTPException(status_code=500, detail="Failed to refresh token")

    def get_valid_token(
        self,
        db: DbSession,
        user_id: UUID,
        provider: str,
    ) -> str:
        """Get valid access token, refreshing if necessary."""
        connection = self.repository.get_active_connection(db, user_id, provider)

        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"No active connection for provider '{provider}'. Please authorize first.",
            )

        # Check if token is expired or expiring soon (within 5 minutes)
        now = datetime.now(timezone.utc)
        if connection.token_expires_at <= now + timedelta(minutes=5):
            self.logger.info(f"Token expiring soon, refreshing for user {user_id} and provider {provider}")
            return self.refresh_access_token(db, user_id, provider)

        return connection.access_token


oauth_service = OAuthService(log=getLogger(__name__))
