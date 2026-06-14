"""Withings OAuth 2.0.

Token exchange and refresh are POSTed to a single RPC endpoint with
``action=requesttoken`` and the credentials in the body (``auth_method=BODY``),
and the response is wrapped in ``{"status", "body"}`` where ``status != 0`` is an
error even on HTTP 200. ``_exchange_token`` and ``refresh_access_token`` are
overridden to handle that envelope; the base template is untouched. The user's
Withings id is carried in the token body, so no follow-up call is needed.
"""

import logging
from uuid import UUID

import httpx
from fastapi import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR

from app.config import settings
from app.database import DbSession
from app.schemas.auth import AuthenticationMethod
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import (
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# Envelope statuses treated as client errors (HTTP 400) rather than server faults:
# bad userid (247/250), subscription/callback (283/286/293), bad code (303/304/305),
# invalid signature/token (342/343), rate limited (601).
_AUTH_ERROR_STATUSES = {247, 250, 283, 286, 293, 303, 304, 305, 342, 343, 601}


class WithingsOAuth(BaseOAuthTemplate):
    """Withings OAuth 2.0 implementation."""

    use_pkce: bool = False
    auth_method: AuthenticationMethod = AuthenticationMethod.BODY

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
                settings.withings_client_secret.get_secret_value() if settings.withings_client_secret else ""
            ),
            redirect_uri=settings.oauth_redirect_uri(ProviderName.WITHINGS),
            default_scope=settings.withings_default_scope,
        )

    # ------------------------------------------------------------------
    # Token exchange / refresh (full override — envelope handling)
    # ------------------------------------------------------------------

    def _exchange_token(self, code: str, code_verifier: str | None) -> OAuthTokenResponse:
        payload = {
            "action": "requesttoken",
            "grant_type": "authorization_code",
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
            "code": code,
            "redirect_uri": self.credentials.redirect_uri,
        }
        return self._request_token(payload, task="exchange_token")

    def refresh_access_token(self, db: DbSession, user_id: UUID, refresh_token: str) -> OAuthTokenResponse:
        payload = {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": self.credentials.client_id,
            "client_secret": self.credentials.client_secret,
            "refresh_token": refresh_token,
        }
        token_response = self._request_token(payload, task="refresh_access_token")

        connection = self.connection_repo.get_by_user_and_provider(db, user_id, self.provider_name)
        if connection:
            # Withings rotates the refresh token on refresh; keep the old one if omitted.
            self.connection_repo.update_tokens(
                db,
                connection,
                token_response.access_token,
                token_response.refresh_token or refresh_token,
                token_response.expires_in,
            )
        log_structured(
            logger,
            "info",
            "Withings token refreshed",
            provider=self.provider_name,
            task="refresh_access_token",
            user_id=str(user_id),
        )
        return token_response

    def _request_token(self, payload: dict[str, str], *, task: str) -> OAuthTokenResponse:
        """POST a token request and unwrap the Withings ``{status, body}`` envelope."""
        try:
            response = httpx.post(
                self.endpoints.token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()
            envelope = response.json()
        except httpx.HTTPStatusError as e:
            log_structured(
                logger,
                "error",
                f"Withings token HTTP error: {e.response.text}",
                provider=self.provider_name,
                task=task,
                status_code=e.response.status_code,
            )
            code = HTTP_500_INTERNAL_SERVER_ERROR if e.response.status_code >= 500 else HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=code, detail=f"Withings token request failed: {e.response.text}")
        except Exception as e:
            log_structured(
                logger,
                "error",
                f"Withings token request failed: {e}",
                provider=self.provider_name,
                task=task,
            )
            raise HTTPException(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Withings token request failed: {e}",
            )

        status = envelope.get("status")
        if status != 0:
            log_structured(
                logger,
                "error",
                "Withings token envelope status non-zero",
                provider=self.provider_name,
                task=task,
                withings_status=status,
            )
            code = HTTP_400_BAD_REQUEST if status in _AUTH_ERROR_STATUSES else HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(status_code=code, detail=f"Withings token error (status={status})")

        return OAuthTokenResponse.model_validate(envelope.get("body", {}))

    # ------------------------------------------------------------------
    # User info (read straight from the token body)
    # ------------------------------------------------------------------

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Return the Withings ``userid`` from the token body — the key for inbound notifications."""
        extra = token_response.model_extra or {}
        userid = extra.get("userid")
        return {"user_id": str(userid) if userid is not None else None, "username": None}
