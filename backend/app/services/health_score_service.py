from logging import Logger, getLogger
from uuid import UUID

from app.database import DbSession
from app.models import HealthScore
from app.repositories import HealthScoreRepository
from app.schemas.enums import HealthScoreCategory
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams, HealthScoreUpdate
from app.services.services import AppService
from app.utils.exceptions import handle_exceptions


class HealthScoreService(
    AppService[HealthScoreRepository, HealthScore, HealthScoreCreate, HealthScoreUpdate],
):
    """Coordinated access to health scores."""

    def __init__(self, log: Logger):
        super().__init__(crud_model=HealthScoreRepository, model=HealthScore, log=log)

    @handle_exceptions
    def get_by_all_components(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        return self.crud.get_by_all_components(db_session, components)

    @handle_exceptions
    def get_by_any_component(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        return self.crud.get_by_any_component(db_session, components)

    @handle_exceptions
    def bulk_create(self, db_session: DbSession, scores: list[HealthScoreCreate]) -> None:
        self.crud.bulk_create(db_session, scores)

    @handle_exceptions
    def get_latest_by_category(
        self,
        db_session: DbSession,
        user_id: UUID,
        category: HealthScoreCategory,
    ) -> HealthScore | None:
        return self.crud.get_latest_by_category(db_session, user_id, category)

    @handle_exceptions
    def get_latest_per_category(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[HealthScore]:
        return self.crud.get_latest_per_category(db_session, user_id)

    @handle_exceptions
    def get_scores_with_filters(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: HealthScoreQueryParams,
    ) -> tuple[list[HealthScore], int]:
        return self.crud.get_with_filters(db_session, user_id, params)


health_score_service = HealthScoreService(log=getLogger(__name__))
