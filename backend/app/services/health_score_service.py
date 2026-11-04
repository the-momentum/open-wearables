from uuid import UUID

from app.database import DbSession
from app.models import DataSource, HealthScore
from app.repositories import HealthScoreRepository
from app.repositories.data_point_series_repository import WriteCounts
from app.schemas.enums import HealthScoreCategory
from app.schemas.model_crud.activities import (
    HealthScoreCreate,
    HealthScoreQueryParams,
    HealthScoreResponse,
    HealthScoreUpdate,
)
from app.schemas.utils.metadata import SourceMetadata
from app.services.priority_service import priority_service
from app.services.services import AppService


class HealthScoreService(
    AppService[HealthScoreRepository, HealthScore, HealthScoreCreate, HealthScoreUpdate],
):
    """Coordinated access to health scores."""

    def __init__(self):
        super().__init__(crud_model=HealthScoreRepository, model=HealthScore)

    def get_by_all_components(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        return self.crud.get_by_all_components(db_session, components)

    def get_by_any_component(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        return self.crud.get_by_any_component(db_session, components)

    def bulk_create(self, db_session: DbSession, scores: list[HealthScoreCreate]) -> WriteCounts:
        return self.crud.bulk_create(db_session, scores)

    def bulk_create_keeping_highest(self, db_session: DbSession, scores: list[HealthScoreCreate]) -> WriteCounts:
        return self.crud.bulk_create_keeping_highest(db_session, scores)

    def get_latest_by_category(
        self,
        db_session: DbSession,
        user_id: UUID,
        category: HealthScoreCategory,
    ) -> HealthScore | None:
        return self.crud.get_latest_by_category(db_session, user_id, category)

    def get_latest_per_category(
        self,
        db_session: DbSession,
        user_id: UUID,
    ) -> list[HealthScore]:
        return self.crud.get_latest_per_category(db_session, user_id)

    def get_scores_with_filters(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: HealthScoreQueryParams,
    ) -> tuple[list[HealthScoreResponse], int]:
        """Scores with their source, one OW score per category and day."""
        rows, total_count = self.crud.get_with_filters(
            db_session,
            user_id,
            params,
            priority_service.get_source_ranking(db_session),
        )
        return [self._to_response(score, data_source) for score, data_source in rows], total_count

    @staticmethod
    def _to_response(score: HealthScore, data_source: DataSource | None) -> HealthScoreResponse:
        response = HealthScoreResponse.model_validate(score)
        if data_source is None:
            return response
        return response.model_copy(
            update={
                "source": SourceMetadata(
                    provider=data_source.provider,
                    source=data_source.source,
                    device=data_source.device_model,
                    device_type=data_source.device_type,
                    device_id=data_source.device_id,
                )
            }
        )


health_score_service = HealthScoreService()
