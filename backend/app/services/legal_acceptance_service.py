from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.database import DbSession
from app.repositories.legal_acceptance_repository import LegalAcceptanceRepository
from app.schemas.model_crud.legal_acceptance import LegalAcceptanceCreate, LegalAcceptanceRead
from app.services.instance_service import instance_service
from app.utils.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.utils.structured_logging import get_logger

logger = get_logger(__name__)

# Phones' clocks drift; an acceptance from further ahead than this is not believable.
_MAX_CLOCK_SKEW = timedelta(minutes=5)


class LegalAcceptanceService:
    """Users accepting the instance's legal documents in the Open Wearables Connect app."""

    def __init__(self) -> None:
        self.repo = LegalAcceptanceRepository()

    def record(self, db: DbSession, user_id: UUID, payload: LegalAcceptanceCreate) -> tuple[LegalAcceptanceRead, bool]:
        """Stores the acceptance of the current version. Returns it and whether it is new.

        409 when the documents changed since the app read them (or there are none): the app
        reads instance/info again and asks the user about the current version.
        """
        settings = instance_service.get_settings(db)
        if not (settings.privacy_policy_url or settings.terms_url):
            raise ConflictError("This instance has no legal documents")
        if payload.documents_version != settings.legal_documents_version:
            raise ConflictError(
                f"Documents version {payload.documents_version} is not the current version "
                f"{settings.legal_documents_version}"
            )
        if payload.accepted_at > datetime.now(timezone.utc) + _MAX_CLOCK_SKEW:
            raise InvalidInputError("accepted_at is in the future")

        existing = self.repo.get(db, user_id, payload.documents_version)
        if existing is not None:
            return LegalAcceptanceRead.model_validate(existing), False
        created = self.repo.create(
            db,
            user_id=user_id,
            documents_version=payload.documents_version,
            privacy_policy_url=settings.privacy_policy_url,
            terms_url=settings.terms_url,
            accepted_at=payload.accepted_at,
        )
        if created is None:
            # A retry won the race, or the user was deleted meanwhile.
            existing = self.repo.get(db, user_id, payload.documents_version)
            if existing is None:
                raise NotFoundError("User not found")
            return LegalAcceptanceRead.model_validate(existing), False
        logger.info(
            "Legal documents accepted",
            user_id=str(user_id),
            documents_version=payload.documents_version,
        )
        return LegalAcceptanceRead.model_validate(created), True

    def list_for_user(self, db: DbSession, user_id: UUID) -> list[LegalAcceptanceRead]:
        return [LegalAcceptanceRead.model_validate(a) for a in self.repo.list_for_user(db, user_id)]


legal_acceptance_service = LegalAcceptanceService()
