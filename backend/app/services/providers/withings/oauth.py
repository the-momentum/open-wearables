"""Handle Withings OAuth token RPC envelopes and provider user identity."""

import logging
from uuid import UUID

import httpx
from celery import current_app as celery_app
from fastapi import HTTPException
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from app.config import settings
from app.database import DbSession, SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.schemas.auth import AuthenticationMethod, LiveSyncMode
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import (
    OAuthState,
    OAuthTokenResponse,
    ProviderCredentials,
    ProviderEndpoints,
)
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.withings.tasks import REGISTER_USER_WEBHOOKS_TASK
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# Token-request statuses caused by invalid request inputs rather than provider faults.
_TOKEN_CLIENT_ERROR_STATUSES = {247, 250, 283, 286, 293, 303, 304, 342}
# Withings' "Authentication failed" family. On refresh these also mean the grant
# is spent; on exchange they usually mean an expired authorization code.
_AUTHENTICATION_FAILED_STATUSES = {100, 101, 102, 200, 401}
_RATE_LIMIT_STATUS = 601


class WithingsTokenError(HTTPException):
    """Typed token failure preserving provider status and grant finality."""

    def __init__(
        self,
        *,
        task: str,
        withings_status: int | None = None,
        http_status: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.withings_status = withings_status
        self.http_status = http_status
        authentication_failed = withings_status in _AUTHENTICATION_FAILED_STATUSES or http_status in {400, 401}
        self.invalid_grant = task == "refresh_access_token" and authentication_failed
        if withings_status == _RATE_LIMIT_STATUS or http_status == 429:
            status_code = 429
        elif authentication_failed:
            status_code = 401
        elif withings_status in _TOKEN_CLIENT_ERROR_STATUSES or (http_status is not None and http_status < 500):
            status_code = 400
        else:
            status_code = 500
        super().__init__(
            status_code=status_code,
            detail=detail or f"Withings token error (status={withings_status})",
        )


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
        try:
            token_response = self._request_token(payload, task="refresh_access_token")
        except WithingsTokenError as exc:
            if exc.invalid_grant:
                self._revoke_connection(db, user_id, reason="refresh_failed")
            raise

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
            raise WithingsTokenError(
                task=task,
                http_status=e.response.status_code,
                detail=f"Withings token request failed: {e.response.text}",
            ) from e
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
            ) from e

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
            raise WithingsTokenError(task=task, withings_status=status)

        return OAuthTokenResponse.model_validate(envelope.get("body", {}))

    def _get_provider_user_info(self, token_response: OAuthTokenResponse, user_id: str) -> dict[str, str | None]:
        """Return the Withings ``userid`` from the token body — the key for inbound notifications."""
        extra = token_response.model_extra or {}
        userid = extra.get("userid")
        return {"user_id": str(userid) if userid is not None else None, "username": None}

    def _save_connection(
        self,
        db: DbSession,
        user_id: UUID,
        token_response: OAuthTokenResponse,
        user_info: dict[str, str | None],
        oauth_state: OAuthState,
    ) -> None:
        """Persist the connection, then subscribe this user to notifications.

        Subscribing needs the stored bearer token, so it cannot run any earlier;
        it is enqueued rather than awaited because it is a list plus one call per
        appli, which the OAuth callback cannot wait on.
        """
        super()._save_connection(db, user_id, token_response, user_info, oauth_state)
        # Withings defaults to pull, so an unset override means no subscriptions.
        if ProviderSettingsRepository().get_live_sync_mode(db, self.provider_name) != LiveSyncMode.WEBHOOK:
            return
        try:
            celery_app.send_task(
                REGISTER_USER_WEBHOOKS_TASK,
                args=[self.provider_name, str(user_id)],
                queue="webhook_sync",
            )
        except Exception as e:
            # The account is linked either way; a broker failure must not fail the callback.
            log_structured(
                logger,
                "error",
                "Withings notify subscription scheduling failed",
                provider=self.provider_name,
                user_id=str(user_id),
                error=str(e),
            )

    def deregister_user(self, access_token: str, provider_user_id: str | None = None) -> None:
        """Revoke this account's notify subscriptions.

        Withings has no app-deregistration endpoint; disconnecting means dropping
        the notify profiles this account owns. Called by disconnect, data purge
        and account deletion while the connection is still active, so a
        ``provider_user_id`` with exactly one active connection is this one.
        """
        # Subscriptions belong to the Withings account, not to one local profile,
        # so a sibling profile still linked to it keeps them.
        if not provider_user_id:
            return
        with SessionLocal() as db:
            linked = self.connection_repo.get_all_by_provider_user_id(db, self.provider_name, provider_user_id)
            if len(linked) != 1:
                return
            # Imported here: webhook_service imports WithingsTokenError from this module.
            from app.services.providers.withings.webhook_service import WithingsWebhookService

            service = WithingsWebhookService(connection_repo=self.connection_repo, oauth=self)
            # Reconciling toward PULL means "no subscriptions desired", which
            # prunes exactly the set this account owns.
            service.sync_user(db, linked[0].user_id, LiveSyncMode.PULL)
