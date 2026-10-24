from contextlib import suppress
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import status

from app.config import settings
from app.database import DbSession
from app.integrations.license_server import (
    LicenseServerClient,
    LicenseServerError,
    LicenseServerUnavailableError,
    license_server_client,
)
from app.models import AppRegistration
from app.repositories.app_registration_repository import AppRegistrationRepository
from app.schemas.model_crud.app_registration import (
    AppEntitlement,
    AppRegistrationCreate,
    AppRegistrationRead,
    AppRegistrationStatus,
)
from app.utils.exceptions import (
    AppError,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
    TooManyRequestsError,
    UpstreamError,
)
from app.utils.license_tokens import (
    generate_hmac_secret,
    generate_private_key,
    pseudo_user_id,
    public_key_of,
    seat_request,
)
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# instance/info is public; while verification is pending it asks the license server at most this often.
STATUS_REFRESH_INTERVAL = timedelta(seconds=60)


# A license server refusal keeps its meaning: the domain error for its status, with its own code as `license_code`.
_REFUSAL_ERRORS: dict[int, type[AppError]] = {
    status.HTTP_400_BAD_REQUEST: InvalidInputError,
    status.HTTP_403_FORBIDDEN: PermissionDeniedError,
    status.HTTP_404_NOT_FOUND: NotFoundError,
    status.HTTP_409_CONFLICT: ConflictError,
    status.HTTP_429_TOO_MANY_REQUESTS: TooManyRequestsError,
}


def _unavailable() -> UpstreamError:
    return UpstreamError("The license server could not be reached")


def _passthrough(exc: LicenseServerError) -> AppError:
    """Hand a license server refusal to the portal with its code, so it can say what to do."""
    error_class = _REFUSAL_ERRORS.get(exc.status_code, UpstreamError)
    return error_class(exc.message, extensions={"license_code": exc.code} if exc.code else None)


class AppRegistrationService:
    """Registration of this instance for the Open Wearables Connect app and the app seats it vouches for.

    Nothing reaches the license server until an administrator registers. What it gets: a random
    instance id, a public key, the admin email and consents - never the server address or user data.
    """

    def __init__(self, client: LicenseServerClient):
        self.client = client
        self.repo = AppRegistrationRepository()

    def get(self, db: DbSession) -> AppRegistrationRead:
        """Registration state for the portal; while pending, asks the license server whether the email is verified."""
        registration = self.repo.get(db)
        if registration is None:
            return AppRegistrationRead(registered=False)
        if registration.status == AppRegistrationStatus.PENDING_VERIFICATION:
            try:
                registration = self._refresh_status(db, registration)
            except (LicenseServerUnavailableError, LicenseServerError):
                logger.warning("Could not check the registration with the license server")
        return self._read(registration)

    def register(self, db: DbSession, payload: AppRegistrationCreate) -> AppRegistrationRead:
        """Register, or resend the verification email while pending (also to a corrected address)."""
        registration = self.repo.get(db)
        if registration is not None and registration.status == AppRegistrationStatus.ACTIVE:
            raise ConflictError("This instance is already registered")

        if registration is None or registration.status == AppRegistrationStatus.REMOVED:
            if registration is not None:
                db.delete(registration)
                db.flush()
            registration = self.repo.add(
                db,
                {
                    "instance_id": uuid4(),
                    "private_key": generate_private_key(),
                    "hmac_secret": generate_hmac_secret(),
                    "admin_email": payload.admin_email,
                    "marketing_consent": payload.marketing_consent,
                    "terms_version": settings.connect_app_terms_version,
                    "status": AppRegistrationStatus.PENDING_VERIFICATION,
                },
            )

        body = {
            "instance_id": str(registration.instance_id),
            "public_key": public_key_of(registration.private_key),
            "admin_email": payload.admin_email,
            "terms_version": settings.connect_app_terms_version,
            "marketing_consent": payload.marketing_consent,
        }
        try:
            result = self.client.register(registration.private_key, registration.instance_id, body)
        except LicenseServerUnavailableError as exc:
            db.rollback()
            raise _unavailable() from exc
        except LicenseServerError as exc:
            db.rollback()
            raise _passthrough(exc) from exc

        registration = self.repo.update(
            db,
            registration,
            {
                "admin_email": payload.admin_email,
                "marketing_consent": payload.marketing_consent,
                "terms_version": settings.connect_app_terms_version,
                "status": result["status"],
                "email_verified_at": result.get("email_verified_at"),
                "status_checked_at": datetime.now(timezone.utc),
            },
        )
        logger.info("Instance registered for the Connect app", status=registration.status)
        return self._read(registration)

    def unregister(self, db: DbSession) -> None:
        """Unregister: the license server drops every seat and the app stops syncing."""
        registration = self._require(db)
        try:
            self.client.delete_instance(registration.private_key, registration.instance_id)
        except LicenseServerUnavailableError as exc:
            raise _unavailable() from exc
        except LicenseServerError as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise _passthrough(exc) from exc
        self.repo.delete(db, registration)
        logger.info("Instance unregistered from the Connect app")

    def entitlement(self, db: DbSession) -> AppEntitlement:
        registration = self._require(db)
        try:
            return AppEntitlement(**self.client.get_entitlement(registration.private_key, registration.instance_id))
        except LicenseServerUnavailableError as exc:
            raise _unavailable() from exc
        except LicenseServerError as exc:
            raise _passthrough(exc) from exc

    def app_identity(self, db: DbSession) -> tuple[bool, UUID | None]:
        """(app_enabled, instance_id) for instance/info. Cheap: hits the license server at most once a minute."""
        registration = self.repo.get(db)
        if registration is None:
            return False, None
        if registration.status == AppRegistrationStatus.PENDING_VERIFICATION and self._refresh_due(registration):
            with suppress(LicenseServerUnavailableError, LicenseServerError):
                registration = self._refresh_status(db, registration)
        return registration.status == AppRegistrationStatus.ACTIVE, registration.instance_id

    def is_registered(self, db: DbSession) -> bool:
        return self.repo.get(db) is not None

    def seat_request_for(self, db: DbSession, user_id: UUID) -> str | None:
        """A seat_request for this user, or None while the app is not enabled on this instance."""
        registration = self.repo.get(db)
        if registration is None or registration.status != AppRegistrationStatus.ACTIVE:
            return None
        return seat_request(
            registration.private_key,
            registration.instance_id,
            pseudo_user_id(registration.hmac_secret, user_id),
        )

    def release_seat(self, db: DbSession, user_id: UUID) -> None:
        """Tell the license server a user is gone. Raises LicenseServerUnavailableError so a task can retry."""
        registration = self.repo.get(db)
        if registration is None:
            return
        try:
            self.client.release_seat(
                registration.private_key,
                registration.instance_id,
                pseudo_user_id(registration.hmac_secret, user_id),
            )
        except LicenseServerError as exc:
            # Unknown instance: unregistering already released every seat.
            logger.warning("License server refused seat release", code=exc.code)

    def _refresh_status(self, db: DbSession, registration: AppRegistration) -> AppRegistration:
        now = datetime.now(timezone.utc)
        try:
            remote = self.client.get_instance(registration.private_key, registration.instance_id)
        except LicenseServerError as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
            return self.repo.update(
                db, registration, {"status": AppRegistrationStatus.REMOVED, "status_checked_at": now}
            )
        return self.repo.update(
            db,
            registration,
            {
                "status": remote["status"],
                "email_verified_at": remote.get("email_verified_at"),
                "status_checked_at": now,
            },
        )

    @staticmethod
    def _refresh_due(registration: AppRegistration) -> bool:
        checked = registration.status_checked_at
        return checked is None or datetime.now(timezone.utc) - checked >= STATUS_REFRESH_INTERVAL

    def _require(self, db: DbSession) -> AppRegistration:
        registration = self.repo.get(db)
        if registration is None:
            raise NotFoundError("This instance is not registered")
        return registration

    @staticmethod
    def _read(registration: AppRegistration) -> AppRegistrationRead:
        return AppRegistrationRead(
            registered=True,
            instance_id=registration.instance_id,
            status=AppRegistrationStatus(registration.status),
            admin_email=registration.admin_email,
            marketing_consent=registration.marketing_consent,
            terms_version=registration.terms_version,
            email_verified_at=registration.email_verified_at,
            registered_at=registration.created_at,
        )


app_registration_service = AppRegistrationService(client=license_server_client)
