from uuid import UUID

from sqlalchemy import and_, desc

from app.database import DbSession
from app.models import DataSource, HealthScore
from app.repositories.repositories import CrudRepository
from app.schemas.model_crud.activities import HealthScoreCreate, HealthScoreQueryParams, HealthScoreUpdate


class HealthScoreRepository(CrudRepository[HealthScore, HealthScoreCreate, HealthScoreUpdate]):
    def get_by_all_components(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        """Return health scores whose components JSONB contains all specified keys (?& operator)."""
        return db_session.query(HealthScore).filter(HealthScore.components.has_all(components)).all()

    def get_by_any_component(self, db_session: DbSession, components: list[str]) -> list[HealthScore]:
        """Return health scores whose components JSONB contains any of the specified keys (?| operator)."""
        return db_session.query(HealthScore).filter(HealthScore.components.has_any(components)).all()

    def get_with_filters(
        self,
        db_session: DbSession,
        user_id: UUID,
        params: HealthScoreQueryParams,
    ) -> tuple[list[HealthScore], int]:
        query = (
            db_session.query(HealthScore)
            .join(DataSource, HealthScore.data_source_id == DataSource.id)
        )

        filters = [DataSource.user_id == user_id]

        if params.category:
            filters.append(HealthScore.category == params.category)
        if params.provider:
            filters.append(HealthScore.provider == params.provider)
        if params.data_source_id:
            filters.append(HealthScore.data_source_id == params.data_source_id)
        if params.start_datetime:
            filters.append(HealthScore.recorded_at >= params.start_datetime)
        if params.end_datetime:
            filters.append(HealthScore.recorded_at < params.end_datetime)

        query = query.filter(and_(*filters))

        total_count = query.count()
        results = (
            query
            .order_by(desc(HealthScore.recorded_at))
            .offset(params.offset)
            .limit(params.limit)
            .all()
        )
        return results, total_count
