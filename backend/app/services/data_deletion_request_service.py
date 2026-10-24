from uuid import UUID

from app.config import settings
from app.database import DbSession
from app.integrations.redis_client import get_redis_client
from app.schemas.responses.sdk_overview import DataDeletionRequestResponse
from app.services.app_registration_service import app_registration_service
from app.services.developer_service import developer_service
from app.services.instance_service import instance_service
from app.services.user_service import user_service
from app.utils.email_client import send_data_deletion_request_email
from app.utils.exceptions import NotFoundError, ServiceUnavailableError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# One email per user per day, however often the button is tapped.
_ONCE_PER_SECONDS = 24 * 3600


class DataDeletionRequestService:
    """A user's request, from the Connect app, to delete their data: the organisation is emailed
    and decides. Nothing is deleted automatically (spec decision, section 11)."""

    def request(self, db: DbSession, user_id: UUID) -> DataDeletionRequestResponse:
        user = user_service.get(db, user_id)
        if user is None:
            raise NotFoundError("User not found")
        key = f"data_deletion_request:{user_id}"
        redis = get_redis_client()
        if not redis.set(key, "1", nx=True, ex=_ONCE_PER_SECONDS):
            return DataDeletionRequestResponse(notified=False)

        label = " ".join(part for part in (user.first_name, user.last_name) if part) or "A user"
        label += f" ({user.email or user.external_user_id or user.id})"
        url = f"{settings.frontend_url.rstrip('/')}/users/{user.id}"
        recipients = self._recipients(db)
        sent = [to for to in recipients if send_data_deletion_request_email(to, label, url)]
        if not sent:
            redis.delete(key)
            raise ServiceUnavailableError("The organisation could not be emailed; contact it directly")
        logger.info("Data deletion request sent", user_id=user_id, recipients=len(sent))
        return DataDeletionRequestResponse(notified=True)

    @staticmethod
    def _recipients(db: DbSession) -> list[str]:
        """The organisation's support address, else the app admin, else every developer."""
        support = instance_service.get_settings(db).support_email
        if support:
            return [str(support)]
        registration = app_registration_service.get(db)
        if registration.registered and registration.admin_email:
            return [registration.admin_email]
        return [developer.email for developer in developer_service.list_all(db) if developer.email]


data_deletion_request_service = DataDeletionRequestService()
