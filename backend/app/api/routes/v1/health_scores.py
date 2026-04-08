from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from app.schemas.enums import HealthScoreCategory, ProviderName
from app.schemas.model_crud.activities import HealthScoreQueryParams, HealthScoreResponse
from app.schemas.utils import PaginatedResponse, Pagination
from app.schemas.utils.metadata import TimeseriesMetadata
from app.services import ApiKeyDep
from app.services.health_score_service import health_score_service
from app.utils.dates import parse_query_datetime

router = APIRouter()


@router.get("/users/{user_id}/health-scores")
def list_health_scores(
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    start_date: str | None = None,
    end_date: str | None = None,
    category: HealthScoreCategory | None = None,
    provider: ProviderName | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[HealthScoreResponse]:
    """Returns health scores (sleep, recovery, readiness, etc.) for a user."""
    params = HealthScoreQueryParams(
        start_datetime=parse_query_datetime(start_date) if start_date else None,
        end_datetime=parse_query_datetime(end_date) if end_date else None,
        category=category,
        provider=provider,
        limit=limit,
        offset=offset,
    )
    scores, total_count = health_score_service.get_scores_with_filters(db, user_id, params)

    data = [HealthScoreResponse.model_validate(s) for s in scores]
    has_more = (offset + len(data)) < total_count

    return PaginatedResponse(
        data=data,
        pagination=Pagination(
            total_count=total_count,
            has_more=has_more,
        ),
        metadata=TimeseriesMetadata(
            sample_count=len(data),
            start_time=params.start_datetime,
            end_time=params.end_datetime,
        ),
    )
