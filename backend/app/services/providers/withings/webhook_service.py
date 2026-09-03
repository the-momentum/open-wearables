"""Per-user Withings webhook subscription management (Withings' Notify API).

Withings subscriptions are created with the user's own bearer token, so there is
one set per active connection instead of a single application-level registration.
``register_subscriptions`` therefore fans out over active connections rather than
registering anything itself.

Withings is also the only provider that builds its own callback URL: notifications
are unsigned, so the shared secret rides in the query string. That means "is this
profile already ours?" cannot be the plain ``==`` Oura uses — a rotated token has
to still read as ours — hence the two comparisons below.
"""

import logging
from typing import Any, Literal
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import UUID

from celery import current_app as celery_app
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.database import DbSession, SessionLocal
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.auth import LiveSyncMode
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.providers.templates.base_webhook_service import BaseWebhookService
from app.services.providers.withings.applis import SUBSCRIBED_APPLIS
from app.services.providers.withings.oauth import WithingsTokenError
from app.services.providers.withings.rpc_client import withings_request
from app.services.providers.withings.tasks import REGISTER_USER_WEBHOOKS_TASK
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured

logger = logging.getLogger(__name__)

# Shown against the profile in Withings' own UI.
MANAGED_COMMENT = "open-wearables"

# Reported status for a successful Notify call, per action.
_APPLIED_STATUS = {"subscribe": "subscribed", "revoke": "revoked"}


def _callback_url() -> str | None:
    """The shared-secret callback URL, or ``None`` when notifications are unconfigured.

    Withings' constraints on it (HTTPS, public host, port 80/443) are enforced by
    Withings and documented in the setup guide; a bad ``API_BASE_URL`` breaks the
    OAuth redirect long before it reaches here.
    """
    token = settings.withings_webhook_token
    if token is None or not token.get_secret_value():
        return None
    query = urlencode({"token": token.get_secret_value()})
    return f"{settings.api_base_url}{settings.api_v1}/providers/withings/webhooks?{query}"


def _urls_match(left: str, right: str) -> bool:
    """Compare full callback identity, shared-secret token included."""
    left_parts, right_parts = _url_parts(left), _url_parts(right)
    return left_parts is not None and left_parts == right_parts


def _endpoints_match(left: str, right: str) -> bool:
    """Compare origin and path only, so a rotated token still reads as ours.

    Guards the multi-environment case: two deployments sharing one Withings app
    each register their own callback for the same account, and neither should
    revoke the other's profiles.
    """
    left_parts, right_parts = _url_parts(left), _url_parts(right)
    return left_parts is not None and right_parts is not None and left_parts[:4] == right_parts[:4]


def _redact(url: str) -> str:
    """Remove query values before a callback URL reaches logs or task results."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "<invalid-callback-url>"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "redacted" if parsed.query else "", ""))


def _url_parts(url: str) -> tuple[str, str, int, str, str] | None:
    """Normalize a callback URL for comparison; ``None`` if it is unusable."""
    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        if not scheme or hostname is None or parsed.username or parsed.password or parsed.fragment:
            return None
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError:
        return None
    return scheme, hostname.lower(), port, parsed.path.rstrip("/") or "/", parsed.query


class WithingsNotifyProfile(BaseModel):
    """One profile returned by Withings Notify List."""

    appli: int
    callbackurl: str
    comment: str | None = None


class WithingsWebhookService(BaseWebhookService):
    """Reconciles a user's Notify subscriptions against the desired live-sync mode."""

    def __init__(
        self,
        connection_repo: UserConnectionRepository,
        oauth: BaseOAuthTemplate,
        default_live_sync_mode: LiveSyncMode | None = LiveSyncMode.PULL,
    ) -> None:
        self.connection_repo = connection_repo
        self.oauth = oauth
        self.provider_settings_repo = ProviderSettingsRepository()
        # Provider's default when no admin override is stored (Withings: PULL).
        self._default_live_sync_mode = default_live_sync_mode

    async def register_subscriptions(self, callback_url: str) -> list[dict[str, Any]]:
        """Fan out one reconciliation task per active connection.

        ``callback_url`` is ignored: each subscription carries the shared-secret
        callback built per request by ``withings_callback_url``.
        """
        with SessionLocal() as db:
            connections = self.connection_repo.get_all_active_by_provider(db, "withings")

        # The oldest active link owns each provider account's subscriptions, matching
        # inbound webhook attribution. A revoked grant yields ownership on the next fan-out.
        subscription_owners: dict[tuple[str, str], str] = {}
        for connection in sorted(connections, key=lambda item: (item.created_at, str(item.id))):
            owner_key = (
                ("provider_user_id", connection.provider_user_id)
                if connection.provider_user_id is not None
                else ("connection_id", str(connection.id))
            )
            subscription_owners.setdefault(owner_key, str(connection.user_id))

        results: list[dict[str, Any]] = []
        for user_id in subscription_owners.values():
            try:
                celery_app.send_task(
                    REGISTER_USER_WEBHOOKS_TASK,
                    args=["withings", user_id],
                    queue="webhook_sync",
                )
                results.append({"status": "dispatched", "user_id": user_id})
            except Exception as e:
                log_and_capture_error(
                    e,
                    logger,
                    "Withings subscription fan-out failed to dispatch",
                    extra={"provider": "withings", "user_id": user_id},
                )
                results.append({"status": "error", "user_id": user_id, "error": str(e)})

        log_structured(
            logger,
            "info",
            "Withings subscription sync fanned out",
            provider="withings",
            action="notify_fan_out",
            dispatched=sum(1 for result in results if result["status"] == "dispatched"),
        )
        return results

    def register_user_subscriptions(self, db: DbSession, user_id: UUID) -> list[dict[str, Any]]:
        """Bring one user's subscriptions in line with the configured live-sync mode.

        The per-user counterpart of ``register_subscriptions`` and idempotent in
        the same way, so a mode of ``pull`` revokes rather than creates. Entry
        point of the ``register_user_webhooks`` task.
        """
        mode = self.provider_settings_repo.get_live_sync_mode(db, "withings") or self._default_live_sync_mode
        if mode is None:
            return [{"status": "skipped", "reason": "no_live_sync_mode"}]
        return self.sync_user(db, user_id, mode)

    def sync_user(self, db: DbSession, user_id: UUID, mode: LiveSyncMode) -> list[dict[str, Any]]:
        """Reconcile the desired appli set without modifying foreign callback endpoints."""
        callback_url = _callback_url()
        if callback_url is None:
            return [{"status": "skipped", "reason": "webhook_token_unconfigured"}]
        desired_applis = set(SUBSCRIBED_APPLIS) if mode == LiveSyncMode.WEBHOOK else set()
        try:
            existing = self._list_subscriptions(db, user_id)
        except WithingsTokenError as e:
            if e.invalid_grant:
                # An invalid grant is terminal until the user reconnects.
                log_structured(
                    logger,
                    "info",
                    "Withings notify sync skipped: refresh token invalid",
                    provider="withings",
                    user_id=str(user_id),
                )
                return [{"status": "skipped", "reason": "invalid_grant"}]
            log_and_capture_error(
                e,
                logger,
                "Withings notify list failed",
                extra={"provider": "withings", "user_id": str(user_id)},
            )
            return [{"status": "error", "error": str(e)}]
        except Exception as e:
            log_and_capture_error(
                e,
                logger,
                "Withings notify list failed",
                extra={"provider": "withings", "user_id": str(user_id)},
            )
            return [{"status": "error", "error": str(e)}]

        existing_by_appli: dict[int, list[WithingsNotifyProfile]] = {}
        for entry in existing:
            existing_by_appli.setdefault(entry.appli, []).append(entry)

        results: list[dict[str, Any]] = []
        active_desired_applis: set[int] = set()
        for appli in desired_applis:
            entries = existing_by_appli.get(appli, [])
            if any(_urls_match(entry.callbackurl, callback_url) for entry in entries):
                active_desired_applis.add(appli)
                results.append({"appli": appli, "status": "unchanged"})
                continue
            result = self._change_subscription(db, user_id, "subscribe", callback_url, appli)
            results.append(result)
            if result["status"] == "subscribed":
                active_desired_applis.add(appli)

        for appli, entries in existing_by_appli.items():
            for entry in entries:
                if appli in desired_applis and _urls_match(entry.callbackurl, callback_url):
                    continue
                if not _endpoints_match(entry.callbackurl, callback_url):
                    continue  # registered by a different host — not ours to touch
                if appli in desired_applis and appli not in active_desired_applis:
                    continue  # replacement failed; retain the old profile until a retry succeeds
                results.append(self._change_subscription(db, user_id, "revoke", entry.callbackurl, appli))

        return results

    def _list_subscriptions(self, db: DbSession, user_id: UUID) -> list[WithingsNotifyProfile]:
        """List all applis and callback URLs in one request."""
        body = withings_request(
            db=db,
            user_id=user_id,
            connection_repo=self.connection_repo,
            oauth=self.oauth,
            service_path="/notify",
            action="list",
            params={},
        )
        profiles: list[WithingsNotifyProfile] = []
        for raw_profile in body.get("profiles", []) or []:
            try:
                profiles.append(WithingsNotifyProfile.model_validate(raw_profile))
            except ValidationError as exc:
                callback_url = raw_profile.get("callbackurl") if isinstance(raw_profile, dict) else None
                log_structured(
                    logger,
                    "warning",
                    "Skipping invalid Withings notify profile",
                    provider="withings",
                    action="notify_profile_validation_failed",
                    user_id=str(user_id),
                    error=exc.errors(include_input=False),
                    callback_url=_redact(callback_url) if isinstance(callback_url, str) else None,
                )
        return profiles

    def _change_subscription(
        self,
        db: DbSession,
        user_id: UUID,
        action: Literal["subscribe", "revoke"],
        callback_url: str,
        appli: int,
    ) -> dict[str, Any]:
        """Subscribe or revoke one appli against Withings' Notify API.

        The counterpart of ``_list_subscriptions``. Reports the outcome rather
        than raising, so one appli failing still leaves the rest of the
        reconciliation to run — and leaves the old profile in place until a
        retry succeeds.
        """
        params: dict[str, Any] = {"callbackurl": callback_url, "appli": appli}
        if action == "subscribe":
            params["comment"] = MANAGED_COMMENT
        try:
            withings_request(
                db=db,
                user_id=user_id,
                connection_repo=self.connection_repo,
                oauth=self.oauth,
                service_path="/notify",
                action=action,
                params=params,
            )
            return {"appli": appli, "status": _APPLIED_STATUS[action]}
        except Exception as e:
            log_and_capture_error(
                e,
                logger,
                f"Withings {action} failed",
                extra={"provider": "withings", "appli": appli, "user_id": str(user_id)},
            )
            return {"appli": appli, "status": "error", "error": str(e)}
