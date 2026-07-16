from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
from redis import Redis

from app.config import settings
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.schemas.enums import ProviderName
from app.schemas.model_crud.credentials import (
    OAuthHandoffBootstrapRequest,
    OAuthHandoffBootstrapResponse,
    OAuthHandoffClaimRequest,
    OAuthHandoffClaimResponse,
    OAuthHandoffInspectRequest,
    OAuthHandoffInspectResponse,
    OAuthHandoffPurpose,
    OAuthState,
    OAuthTokenResponse,
)
from app.services.providers.base_strategy import BaseProviderStrategy
from app.services.providers.factory import ProviderFactory
from app.services.user_connection_service import user_connection_service
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)


class OAuthHandoffService:
    """Encrypted, single-use Strava identity handoffs for Team42."""

    _state_prefix = "team42_oauth_handoff_state:"
    _inspect_prefix = "team42_oauth_handoff_inspect:"
    _claim_prefix = "team42_oauth_handoff_claim:"
    _subject_lock_prefix = "team42_oauth_handoff_subject_lock:"
    _user_lock_prefix = "team42_oauth_handoff_user_lock:"
    _envelope_version = 1

    def __init__(self) -> None:
        self.factory = ProviderFactory()

    @property
    def redis(self) -> Redis:
        return get_redis_client()

    def bootstrap(self, payload: OAuthHandoffBootstrapRequest) -> OAuthHandoffBootstrapResponse:
        self._require_enabled()
        self._validate_return_uri(payload.return_uri)

        scopes = self._normalize_scopes(payload.scopes, payload.purpose)
        internal_state = secrets.token_urlsafe(32)
        strategy = self._strategy()
        assert strategy.oauth
        authorization_url, pkce_data = strategy.oauth._build_auth_url(internal_state, ",".join(scopes))

        envelope: dict[str, Any] = {
            "version": self._envelope_version,
            "kind": "state",
            "client_state": payload.state,
            "return_uri": payload.return_uri,
            "purpose": payload.purpose.value,
            "requested_scopes": scopes,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if pkce_data:
            envelope.update(pkce_data)

        self._store_encrypted(
            f"{self._state_prefix}{internal_state}",
            envelope,
            settings.team42_oauth_handoff_state_ttl_seconds,
        )
        log_structured(
            logger,
            "info",
            "Team42 OAuth handoff bootstrapped",
            provider=ProviderName.STRAVA.value,
            task="oauth_handoff_bootstrap",
            purpose=payload.purpose.value,
        )
        return OAuthHandoffBootstrapResponse(authorization_url=authorization_url)

    def handle_callback(
        self,
        code: str | None,
        state: str | None,
        error: str | None,
        error_description: str | None,
        granted_scope: str | None,
    ) -> RedirectResponse | None:
        """Handle Team42 state or return None for the normal OAuth flow."""
        if not state:
            return None

        encrypted = self.redis.getdel(f"{self._state_prefix}{state}")
        if not encrypted:
            return None

        state_data = self._decrypt(encrypted, expected_kind="state")
        return_uri = str(state_data["return_uri"])
        client_state = str(state_data["client_state"])
        self._validate_return_uri(return_uri)

        if not settings.team42_oauth_handoff_enabled:
            return self._error_redirect(return_uri, client_state, "temporarily_unavailable")

        if error or not code:
            return self._error_redirect(
                return_uri,
                client_state,
                error or "access_denied",
                error_description or "Authorization was not completed",
            )

        strategy = self._strategy()
        assert strategy.oauth
        try:
            token = strategy.oauth._exchange_token(code, state_data.get("code_verifier"))
            user_info = strategy.oauth._get_provider_user_info(token, "team42-handoff")
        except HTTPException:
            log_structured(
                logger,
                "warning",
                "Team42 OAuth handoff token exchange failed",
                provider=ProviderName.STRAVA.value,
                task="oauth_handoff_callback",
                purpose=str(state_data["purpose"]),
            )
            return self._error_redirect(return_uri, client_state, "oauth_exchange_failed")

        subject = str(user_info.get("user_id") or "")
        if not subject:
            return self._error_redirect(return_uri, client_state, "identity_unavailable")

        granted_scopes = self._scope_set(user_info.get("scope") or token.scope or granted_scope or "")
        inspect_code = secrets.token_urlsafe(48)
        inspect_envelope = {
            "version": self._envelope_version,
            "kind": "inspect",
            "provider_subject": subject,
            "provider_username": user_info.get("username"),
            "first_name": user_info.get("first_name") or "",
            "last_name": user_info.get("last_name") or "",
            "scopes": sorted(granted_scopes),
            "purpose": str(state_data["purpose"]),
            "token": token.model_dump(mode="json"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store_encrypted(
            f"{self._inspect_prefix}{inspect_code}",
            inspect_envelope,
            settings.team42_oauth_handoff_code_ttl_seconds,
        )

        log_structured(
            logger,
            "info",
            "Team42 OAuth handoff callback completed",
            provider=ProviderName.STRAVA.value,
            task="oauth_handoff_callback",
            purpose=str(state_data["purpose"]),
            subject_hash=self._subject_hash(subject),
        )
        fragment = urlencode({"state": client_state, "handoff": inspect_code})
        return RedirectResponse(f"{return_uri}#{fragment}", status_code=status.HTTP_303_SEE_OTHER)

    def inspect(self, payload: OAuthHandoffInspectRequest) -> OAuthHandoffInspectResponse:
        self._require_enabled()
        data = self._consume_encrypted(f"{self._inspect_prefix}{payload.handoff_code}", expected_kind="inspect")
        purpose = OAuthHandoffPurpose(str(data["purpose"]))
        scopes = self._scope_set(data.get("scopes", []))
        activity_sync_authorized = purpose == OAuthHandoffPurpose.REGISTER and "activity:read_all" in scopes

        claim_code = None
        if activity_sync_authorized:
            claim_code = secrets.token_urlsafe(48)
            claim_envelope = dict(data)
            claim_envelope["kind"] = "claim"
            claim_envelope["created_at"] = datetime.now(timezone.utc).isoformat()
            self._store_encrypted(
                f"{self._claim_prefix}{claim_code}",
                claim_envelope,
                settings.team42_oauth_handoff_code_ttl_seconds,
            )

        subject = str(data["provider_subject"])
        log_structured(
            logger,
            "info",
            "Team42 OAuth handoff inspected",
            provider=ProviderName.STRAVA.value,
            task="oauth_handoff_inspect",
            purpose=purpose.value,
            subject_hash=self._subject_hash(subject),
            claimable=bool(claim_code),
        )
        return OAuthHandoffInspectResponse(
            provider_subject=subject,
            provider_username=data.get("provider_username"),
            scope=",".join(sorted(scopes)),
            first_name=str(data.get("first_name") or ""),
            last_name=str(data.get("last_name") or ""),
            purpose=purpose,
            activity_sync_authorized=activity_sync_authorized,
            claim_code=claim_code,
        )

    def claim(self, payload: OAuthHandoffClaimRequest, db: DbSession) -> OAuthHandoffClaimResponse:
        self._require_enabled()
        data = self._consume_encrypted(f"{self._claim_prefix}{payload.handoff_code}", expected_kind="claim")
        purpose = OAuthHandoffPurpose(str(data["purpose"]))
        scopes = self._scope_set(data.get("scopes", []))
        if purpose != OAuthHandoffPurpose.REGISTER or "activity:read_all" not in scopes:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Handoff cannot create a data connection")

        subject = str(data["provider_subject"])
        subject_lock_key = f"{self._subject_lock_prefix}{self._subject_hash(subject)}"
        if not self.redis.set(subject_lock_key, "1", nx=True, ex=60):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Strava identity is already being claimed")

        user_lock_key = f"{self._user_lock_prefix}{payload.user_id}"
        if not self.redis.set(user_lock_key, "1", nx=True, ex=60):
            self.redis.delete(subject_lock_key)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Open Wearables user is already receiving a provider connection",
            )

        try:
            strategy = self._strategy()
            assert strategy.oauth
            if not strategy.oauth.user_repo.get(db, payload.user_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Open Wearables user was not found")

            target_connection = strategy.oauth.connection_repo.get_by_user_and_provider(
                db,
                payload.user_id,
                ProviderName.STRAVA.value,
            )
            if (
                target_connection
                and target_connection.provider_user_id
                and target_connection.provider_user_id != subject
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Open Wearables user is connected to a different Strava identity",
                )

            subject_connections = strategy.oauth.connection_repo.get_all_by_provider_user_id_any_status(
                db,
                ProviderName.STRAVA.value,
                subject,
            )
            if any(connection.user_id != payload.user_id for connection in subject_connections):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Strava identity belongs to another Open Wearables user",
                )

            token = OAuthTokenResponse.model_validate(data["token"])
            user_info = {
                "user_id": subject,
                "username": data.get("provider_username"),
                "scope": ",".join(sorted(scopes)),
            }
            oauth_state = OAuthState(user_id=payload.user_id, provider=ProviderName.STRAVA.value)
            strategy.oauth._save_connection(db, payload.user_id, token, user_info, oauth_state)
            user_connection_service.stamp_last_synced_at(db, payload.user_id, ProviderName.STRAVA.value)

            log_structured(
                logger,
                "info",
                "Team42 OAuth handoff claimed",
                provider=ProviderName.STRAVA.value,
                task="oauth_handoff_claim",
                user_id=str(payload.user_id),
                subject_hash=self._subject_hash(subject),
            )
            return OAuthHandoffClaimResponse(
                claimed=True,
                provider_subject=subject,
                scope=",".join(sorted(scopes)),
            )
        finally:
            self.redis.delete(user_lock_key, subject_lock_key)

    def _strategy(self) -> BaseProviderStrategy:
        strategy = self.factory.get_provider(ProviderName.STRAVA.value)
        if not strategy.oauth:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Strava OAuth is unavailable")
        return strategy

    def _require_enabled(self) -> None:
        if not settings.team42_oauth_handoff_enabled:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        self._fernet()

    def _fernet(self) -> Fernet:
        configured = settings.team42_oauth_handoff_key
        if configured is None or not configured.get_secret_value():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OAuth handoff encryption is not configured",
            )
        try:
            return Fernet(configured.get_secret_value().encode())
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OAuth handoff encryption is invalid",
            ) from exc

    def _allowed_return_uris(self) -> set[str]:
        return {uri.strip() for uri in settings.team42_oauth_handoff_return_uris.split(",") if uri.strip()}

    def _validate_return_uri(self, return_uri: str) -> None:
        if return_uri not in self._allowed_return_uris():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unregistered return URI")

    def _normalize_scopes(self, requested: list[str], purpose: OAuthHandoffPurpose) -> list[str]:
        default_scopes = ["read", "activity:read_all"] if purpose == OAuthHandoffPurpose.REGISTER else ["read"]
        scopes = self._scope_set(requested or default_scopes)
        allowed = self._scope_set(settings.team42_oauth_handoff_allowed_scopes)
        if not scopes or "read" not in scopes or not scopes.issubset(allowed):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported Strava OAuth scopes")
        if purpose != OAuthHandoffPurpose.REGISTER and any(scope.startswith("activity:") for scope in scopes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Login and identity linking cannot request activity scopes",
            )
        return sorted(scopes)

    @staticmethod
    def _scope_set(value: Any) -> set[str]:
        if isinstance(value, str):
            parts = value.replace(" ", ",").split(",")
        elif isinstance(value, list):
            parts = value
        else:
            parts = []
        return {str(part).strip() for part in parts if str(part).strip()}

    def _store_encrypted(self, key: str, value: dict[str, Any], ttl: int) -> None:
        encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        self.redis.setex(key, ttl, self._fernet().encrypt(encoded).decode())

    def _consume_encrypted(self, key: str, expected_kind: str) -> dict[str, Any]:
        encrypted = self.redis.getdel(key)
        if not encrypted:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Handoff is invalid or expired")
        return self._decrypt(encrypted, expected_kind)

    def _decrypt(self, encrypted: Any, expected_kind: str) -> dict[str, Any]:
        encoded = encrypted.decode() if isinstance(encrypted, bytes) else str(encrypted)
        try:
            data = json.loads(self._fernet().decrypt(encoded.encode()))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Handoff is invalid or expired") from exc
        if data.get("version") != self._envelope_version or data.get("kind") != expected_kind:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Handoff is invalid or expired")
        return data

    @staticmethod
    def _subject_hash(subject: str) -> str:
        return hashlib.sha256(subject.encode()).hexdigest()

    @staticmethod
    def _error_redirect(
        return_uri: str,
        client_state: str,
        error: str,
        description: str | None = None,
    ) -> RedirectResponse:
        fragment_data = {"state": client_state, "error": error}
        if description:
            fragment_data["error_description"] = description
        return RedirectResponse(
            f"{return_uri}#{urlencode(fragment_data)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


oauth_handoff_service = OAuthHandoffService()
