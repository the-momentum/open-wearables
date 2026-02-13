import secrets
from datetime import datetime, timezone
from logging import Logger, getLogger
from uuid import UUID

from fastapi import HTTPException

from app.database import DbSession
from app.models import Application
from app.repositories.application_repository import ApplicationRepository
from app.schemas.application import ApplicationCreateInternal, ApplicationUpdate
from app.services.services import AppService
from app.utils.security import get_password_hash, verify_password
from app.utils.structured_logging import log_structured


class ApplicationService(AppService[ApplicationRepository, Application, ApplicationCreateInternal, ApplicationUpdate]):
    def __init__(self, log: Logger, **kwargs):
        super().__init__(
            crud_model=ApplicationRepository,
            model=Application,
            log=log,
            **kwargs,
        )

    def _generate_app_id(self) -> str:
        """Generate random app_id with app_ prefix and 32 hex characters."""
        return f"app_{secrets.token_hex(16)}"

    def _generate_app_secret(self) -> str:
        """Generate random app_secret with secret_ prefix and 64 hex characters."""
        return f"secret_{secrets.token_hex(32)}"

    def create_application(self, db: DbSession, developer_id: UUID, name: str) -> tuple[Application, str]:
        """Create a new application with generated credentials.

        Returns:
            Tuple of (Application, plain_secret). The plain_secret should only
            be shown once to the developer, as it will never be retrievable again.
        """
        app_id = self._generate_app_id()
        plain_secret = self._generate_app_secret()
        secret_hash = get_password_hash(plain_secret)

        now = datetime.now(timezone.utc)
        creator = ApplicationCreateInternal(
            name=name,
            app_id=app_id,
            app_secret_hash=secret_hash,
            developer_id=developer_id,
            created_at=now,
            updated_at=now,
        )
        application = self.create(db, creator)
        self.logger.debug(f"Created application {application.app_id} for developer {developer_id}")
        return application, plain_secret

    def validate_credentials(self, db: DbSession, app_id: str, app_secret: str) -> Application:
        """Validate app credentials and return application if valid.

        Raises:
            HTTPException: 401 if credentials are invalid.
        """
        application = self.crud.get_by_app_id(db, app_id)
        if not application:
            log_structured(
                self.logger,
                "warning",
                f"Application not found: {app_id}",
                extra={"app_id": app_id},
            )
            raise HTTPException(status_code=401, detail="Invalid app credentials")

        if not verify_password(app_secret, application.app_secret_hash):
            log_structured(
                self.logger,
                "warning",
                f"Invalid secret for application: {app_id}",
                extra={"app_id": app_id},
            )
            raise HTTPException(status_code=401, detail="Invalid app credentials")

        return application

    def list_applications(self, db: DbSession, developer_id: UUID) -> list[Application]:
        """List all applications for a developer."""
        applications = self.crud.list_by_developer(db, developer_id)
        self.logger.debug(f"Listed {len(applications)} applications for developer {developer_id}")
        return applications

    def delete_application(self, db: DbSession, app_id: str, developer_id: UUID) -> None:
        """Delete an application by app_id, verifying ownership.

        Raises:
            HTTPException: 404 if not found or not owned by developer.
        """
        application = self.crud.get_by_app_id(db, app_id)
        if not application or application.developer_id != developer_id:
            raise HTTPException(status_code=404, detail="Application not found")

        self.delete(db, application.id, raise_404=True)
        self.logger.debug(f"Deleted application {app_id}")

    def rotate_secret(self, db: DbSession, app_id: str, developer_id: UUID) -> tuple[Application, str]:
        """Rotate application secret, verifying ownership.

        Returns:
            Tuple of (Application, new_plain_secret).

        Raises:
            HTTPException: 404 if not found or not owned by developer.
        """
        application = self.crud.get_by_app_id(db, app_id)
        if not application or application.developer_id != developer_id:
            raise HTTPException(status_code=404, detail="Application not found")

        new_secret = self._generate_app_secret()
        new_hash = get_password_hash(new_secret)

        # Directly update the hash since it's not in the update schema
        application.app_secret_hash = new_hash
        application.updated_at = datetime.now(timezone.utc)
        db.flush()

        self.logger.debug(f"Rotated secret for application {app_id}")
        return application, new_secret


application_service = ApplicationService(log=getLogger(__name__))
