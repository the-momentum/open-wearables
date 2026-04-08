from datetime import datetime
from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import UserConnection
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.model_crud.user_management import UserConnectionCreate, UserConnectionUpdate
from app.services.providers.templates.base_oauth import BaseOAuthTemplate
from app.services.services import AppService
from app.utils.exceptions import ResourceNotFoundError, handle_exceptions
from app.utils.sentry_helpers import log_and_capture_error
from app.utils.structured_logging import log_structured


class UserConnectionService(
    AppService[UserConnectionRepository, UserConnection, UserConnectionCreate, UserConnectionUpdate],
):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=UserConnectionRepository,
            model=UserConnection,
            log=log,
            **kwargs,
        )

    def get_active_count_in_range(self, db_session: DbSession, start_date: datetime, end_date: datetime) -> int:
        """Get count of active connections created within a date range."""
        return self.crud.get_active_count_in_range(db_session, start_date, end_date)

    @handle_exceptions
    def get_connections_by_user(self, db_session: DbSession, user_id: UUID) -> list[UserConnection]:
        """Get all connections for a user."""
        return self.crud.get_by_user_id(db_session, user_id)

    @handle_exceptions
    def disconnect(
        self, db_session: DbSession, user_id: UUID, provider: str, oauth: BaseOAuthTemplate | None = None
    ) -> None:
        """Disconnect a user from a provider. Raises 404 if connection not found.

        If oauth is provided, calls the provider's deregistration API before clearing tokens.
        Deregistration failures are logged but do not block the disconnect.
        """
        if oauth:
            self._deregister_from_provider(db_session, user_id, provider, oauth)

        updated = self.crud.disconnect(db_session, user_id, provider)
        if updated:
            self.logger.info("Revoked connection for user %s from provider %s", user_id, provider)
            return

        # Nothing updated - check if connection exists (already revoked) or not found
        connection = self.crud.get_by_user_and_provider(db_session, user_id, provider)
        if not connection:
            raise ResourceNotFoundError("connection", user_id)

    @handle_exceptions
    def stamp_last_synced_at(self, db_session: DbSession, user_id: UUID, provider: str) -> None:
        """Stamp last_synced_at=now on the user's connection for the given provider.

        Used after OAuth completion so the first periodic sync uses the connection
        timestamp as its live-sync cursor and won't attempt to pull all historical data.
        No-op if the connection does not exist.
        """
        connection = self.crud.get_by_user_and_provider(db_session, user_id, provider)
        if connection:
            self.crud.update_last_synced_at(db_session, connection)

    def _deregister_from_provider(
        self, db_session: DbSession, user_id: UUID, provider: str, oauth: BaseOAuthTemplate
    ) -> None:
        """Best-effort call to provider's deregistration API."""
        connection = self.crud.get_by_user_and_provider(db_session, user_id, provider)
        if not connection or not connection.access_token:
            return

        try:
            oauth.deregister_user(connection.access_token)
            log_structured(
                self.logger,
                "info",
                "Deregistered user from provider API",
                provider=provider,
                task="deregister_user",
                user_id=str(user_id),
            )
        except Exception as e:
            log_structured(
                self.logger,
                "error",
                f"Failed to deregister user from provider API: {e}",
                provider=provider,
                task="deregister_user",
                user_id=str(user_id),
            )
            log_and_capture_error(
                e,
                self.logger,
                f"Failed to deregister user {user_id} from {provider} API: {e}",
                extra={"user_id": str(user_id), "provider": provider},
            )


user_connection_service = UserConnectionService(log=getLogger(__name__))
