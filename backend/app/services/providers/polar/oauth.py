from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_409_CONFLICT, HTTP_500_INTERNAL_SERVER_ERROR

from app.config import settings
from app.database import DbSession
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import (
    OAuthState,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate


class PolarOAuth(BaseOAuthTemplate):
    """Polar OAuth 2.0 implementation."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://flow.polar.com/oauth2/authorization",
            token_url="https://polarremote.com/v2/oauth2/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        return ProviderCredentials(
            client_id=settings.polar_client_id or "",
            client_secret=(settings.polar_client_secret.get_secret_value() if settings.polar_client_secret else ""),
            redirect_uri=settings.oauth_redirect_uri(ProviderName.POLAR),
            default_scope=settings.polar_default_scope,
        )

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Extracts Polar user ID from token response and registers user."""
        raw = token_response.model_extra.get("x_user_id") if token_response.model_extra else None
        provider_user_id = str(raw) if raw is not None else None

        if provider_user_id:
            self._register_user(token_response.access_token, user_id)

        return {"user_id": provider_user_id, "username": None}

    def _register_user(self, access_token: str, member_id: str) -> None:
        """Registers the user with Polar API."""

        try:
            register_url = f"{self.api_base_url}/v3/users"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            payload = {"member-id": member_id}

            httpx.post(register_url, json=payload, headers=headers, timeout=10.0)
        except Exception:
            # Don't fail the entire flow - user might already be registered
            pass

    def deregister_user(self, access_token: str, provider_user_id: str | None = None) -> None:
        """Call Polar's user deregistration endpoint to remove the app association."""

        if not provider_user_id:
            raise ValueError("Polar deregistration requires provider_user_id")

        deregister_url = f"{self.api_base_url}/v3/users/{provider_user_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        response = httpx.delete(deregister_url, headers=headers, timeout=10.0)
        response.raise_for_status()


class PolarSleepV4OAuth(BaseOAuthTemplate):
    """Separate v4 OAuth grant, kept alongside the legacy v3 Polar connection."""

    @property
    def endpoints(self) -> ProviderEndpoints:
        return ProviderEndpoints(
            authorize_url="https://auth.polar.com/oauth/authorize",
            token_url="https://auth.polar.com/oauth/token",
        )

    @property
    def credentials(self) -> ProviderCredentials:
        client_secret = settings.polar_v4_client_secret or settings.polar_client_secret
        return ProviderCredentials(
            client_id=settings.polar_v4_client_id or settings.polar_client_id or "",
            client_secret=client_secret.get_secret_value() if client_secret else "",
            redirect_uri=f"{settings.api_base_url.rstrip('/')}/api/v1/oauth/polar-sleep/callback",
            default_scope="sleep:read",
        )

    def _save_connection(
        self,
        db: DbSession,
        user_id: UUID,
        token_response: OAuthTokenResponse,
        _user_info: dict[str, str | None],
        _oauth_state: OAuthState,
    ) -> None:
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, "polar")
        if not connection:
            raise HTTPException(
                status_code=HTTP_409_CONFLICT,
                detail="Connect the legacy Polar integration before authorizing Polar sleep v4.",
            )

        connection.polar_v4_access_token = token_response.access_token
        connection.polar_v4_refresh_token = token_response.refresh_token
        connection.polar_v4_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=token_response.expires_in
        )
        connection.polar_v4_scope = token_response.scope or "sleep:read"
        connection.updated_at = datetime.now(timezone.utc)
        db.add(connection)
        db.commit()
        db.refresh(connection)

    def get_sleep_access_token(self, db: DbSession, user_id: UUID) -> str | None:
        connection = self.connection_repo.get_by_user_and_provider(db, user_id, "polar")
        if not connection or not connection.polar_v4_access_token:
            return None
        expires_at = connection.polar_v4_token_expires_at
        if expires_at and expires_at >= datetime.now(timezone.utc) + timedelta(minutes=5):
            return connection.polar_v4_access_token
        if not connection.polar_v4_refresh_token:
            return None

        data, headers = self._prepare_refresh_request(connection.polar_v4_refresh_token)
        try:
            response = httpx.post(self.endpoints.token_url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            token = OAuthTokenResponse.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST, detail="Failed to refresh Polar v4 sleep authorization"
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to refresh Polar v4 sleep authorization"
            ) from exc

        connection.polar_v4_access_token = token.access_token
        if token.refresh_token:
            connection.polar_v4_refresh_token = token.refresh_token
        connection.polar_v4_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token.expires_in)
        connection.polar_v4_scope = token.scope or connection.polar_v4_scope
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return connection.polar_v4_access_token
