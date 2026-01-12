from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.database import DbSession
from app.schemas.common_types import PaginatedResponse
from app.schemas.series_types import SeriesType
from app.schemas.timeseries import (
    TimeSeriesQueryParams,
    TimeSeriesSample,
)
from app.services import ApiKeyDep, timeseries_service
from app.utils.dates import parse_query_datetime

router = APIRouter()


@router.get("/users/{user_id}/timeseries")
async def get_timeseries(
    user_id: UUID,
    start_time: str,
    end_time: str,
    db: DbSession,
    _api_key: ApiKeyDep,
    types: Annotated[list[SeriesType], Query()] = [],
    resolution: Literal["raw", "1min", "5min", "15min", "1hour"] = "raw",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedResponse[TimeSeriesSample]:
    """Returns granular time series data (biometrics or activity)."""
    params = TimeSeriesQueryParams(
        start_datetime=parse_query_datetime(start_time),
        end_datetime=parse_query_datetime(end_time),
        limit=limit,
        cursor=cursor,
    )
    return await timeseries_service.get_timeseries(db, user_id, types, params)
