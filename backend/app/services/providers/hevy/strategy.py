"""Hevy provider implementation (API-key auth, no OAuth)."""

from datetime import datetime, timezone
from uuid import UUID

import httpx
from pydantic import ValidationError

from app.database import DbSession
from app.models import UserConnection
from app.schemas.auth import ConnectionStatus
from app.schemas.model_crud.user_management import UserConnectionCreate
from app.schemas.providers.hevy import HevyUserInfo
from app.services.outgoing_webhooks.events import on_connection_created
from app.services.providers.base_strategy import (
    BaseProviderStrategy,
    InvalidApiKeyError,
    ProviderCapabilities,
    ProviderCoverage,
    ProviderUnavailableError,
)
from app.services.providers.hevy.coverage import HEALTH_SCORES, SLEEP_FIELDS, TIMESERIES, WORKOUT_FIELDS
from app.services.providers.hevy.workouts import HevyWorkouts


class HevyStrategy(BaseProviderStrategy):
    """Hevy gym-workout tracker.

    Auth model: no OAuth — each user supplies their personal API key
    (hevy.com/settings?developer, Hevy Pro required). The key is unscoped and
    long-lived; it is stored on the connection's ``access_token`` and sent as
    the ``api-key`` header on every request.
    """

    def __init__(self) -> None:
        super().__init__()
        self.workouts = HevyWorkouts(
            workout_repo=self.workout_repo,
            connection_repo=self.connection_repo,
            provider_name=self.name,
            api_base_url=self.api_base_url,
            # API-key auth: there is no OAuth template to pass. The base template types
            # oauth as required because every upstream provider has one; relaxing it there
            # would cascade None-checks through every provider, so the mismatch is pinned
            # here instead. Goes away if Hevy lands upstream with an optional oauth.
            oauth=None,  # ty: ignore[invalid-argument-type]
        )

    @property
    def name(self) -> str:
        return "hevy"

    @property
    def display_name(self) -> str:
        return "Hevy"

    @property
    def api_base_url(self) -> str:
        return "https://api.hevyapp.com"

    @property
    def has_cloud_api(self) -> bool:
        # Base derives this from oauth presence; Hevy has a cloud REST API
        # without OAuth.
        return True

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(rest_pull=True, api_key_connect=True)

    @property
    def coverage(self) -> ProviderCoverage:
        return ProviderCoverage(
            timeseries=TIMESERIES,
            workout_fields=WORKOUT_FIELDS,
            sleep_fields=SLEEP_FIELDS,
            health_scores=HEALTH_SCORES,
        )

    def connect_with_api_key(self, db: DbSession, user_id: UUID, api_key: str) -> UserConnection:
        """Validate the key against GET /v1/user/info and upsert the connection.

        Raises InvalidApiKeyError when Hevy rejects the key (invalid, regenerated,
        or the account's Pro subscription lapsed), and ProviderUnavailableError when
        Hevy cannot answer (timeout, connection error, 429, 5xx, unexpected body).
        """
        try:
            response = httpx.get(
                f"{self.api_base_url}/v1/user/info",
                headers={"api-key": api_key},
                timeout=30.0,
            )
        except httpx.HTTPError as e:
            raise ProviderUnavailableError(f"Hevy is unreachable: {e.__class__.__name__}") from e
        if response.status_code in (401, 403, 404):
            raise InvalidApiKeyError("Hevy rejected the API key")
        if response.status_code >= 400:
            # 429 and 5xx say nothing about the key; never report them as an invalid one.
            raise ProviderUnavailableError(f"Hevy returned HTTP {response.status_code}")
        try:
            payload = response.json()
            # The live API wraps the user in {"data": {...}}; accept the bare and
            # "user_info" shapes too, so a docs-vs-API mismatch can't block connecting.
            body = payload.get("data") or payload.get("user_info") or payload
            user_info = HevyUserInfo.model_validate(body)
        except (ValueError, ValidationError) as e:
            # Hevy accepted the key (2xx) but the body is not what we expect: their side.
            raise ProviderUnavailableError(f"Unexpected Hevy user info response: {e}") from e

        existing = self.connection_repo.get_by_user_and_provider(db, user_id, self.name)
        if existing:
            was_inactive = existing.status != ConnectionStatus.ACTIVE
            existing.access_token = api_key
            # API keys don't expire and there is no refresh token.
            existing.refresh_token = None
            existing.token_expires_at = None
            # The new key may belong to a different Hevy account: the identity always
            # follows the key that was just validated, never the one stored before.
            existing.provider_user_id = user_info.id
            if user_info.display_name:
                existing.provider_username = user_info.display_name
            existing.status = ConnectionStatus.ACTIVE
            existing.updated_at = datetime.now(timezone.utc)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            if was_inactive:
                on_connection_created(
                    user_id=user_id,
                    provider=self.name,
                    connection_id=existing.id,
                    connected_at=datetime.now(timezone.utc).isoformat(),
                )
            return existing

        connection = self.connection_repo.create(
            db,
            UserConnectionCreate(
                user_id=user_id,
                provider=self.name,
                provider_user_id=user_info.id,
                provider_username=user_info.display_name,
                access_token=api_key,
                refresh_token=None,
                token_expires_at=None,
            ),
        )
        if connection is None:
            # create() is wrapped in @handle_duplicates, which returns None when a unique
            # violation fires and it cannot then find the row that caused it. The
            # get_by_user_and_provider branch above already covers the expected duplicate,
            # so reaching here means the row vanished between the two queries.
            raise RuntimeError(f"Could not create or recover the {self.name} connection for user {user_id}")

        on_connection_created(
            user_id=user_id,
            provider=self.name,
            connection_id=connection.id,
            connected_at=connection.created_at.isoformat(),
        )
        return connection
