from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DbSession
from app.schemas.enums import PERIOD_RESOLUTIONS, ProviderName, Resolution, SeriesType, SourceSelection
from app.schemas.model_crud.activities import TimeSeriesQueryParams
from app.schemas.responses.activity import TimeSeriesSample
from app.schemas.utils import PaginatedResponse
from app.services import ApiKeyDep, timeseries_service
from app.utils.dates import DateTimeQueryParam, parse_query_datetime, parse_query_end_datetime
from app.utils.pagination import DEFAULT_PAGE_SIZE, PageLimitQueryParam

router = APIRouter()


@router.get("/users/{user_id}/timeseries")
def get_timeseries(
    user_id: UUID,
    start_time: DateTimeQueryParam,
    end_time: DateTimeQueryParam,
    db: DbSession,
    _api_key: ApiKeyDep,
    types: Annotated[list[SeriesType], Query()] = [],
    resolution: Resolution = Resolution.RAW,
    cursor: str | None = None,
    limit: PageLimitQueryParam = DEFAULT_PAGE_SIZE,
    provider: ProviderName | None = None,
    source: str | None = None,
    device_model: str | None = None,
    data_source_id: UUID | None = None,
    source_selection: Annotated[
        Literal[SourceSelection.ALL, SourceSelection.PER_RANGE, SourceSelection.PER_PERIOD, SourceSelection.RECONCILE]
        | None,
        Query(
            description="`all` returns every source. `per_range` keeps one source per series type for the whole "
            "range. `per_period` keeps one per series type and period: per day for `1day`, `1week` and `1month`, "
            "per bucket below a day; not available for raw reads. A week or month whose days different sources won "
            "has `source: null`. `reconcile` (`1day`, `1week` and `1month` only) "
            "merges steps, distance, active energy and the other movement series across sources per day, each moment "
            "counted once from the best-ranked source recording it, and reads other series as `per_period`; a "
            "merged value names no source. A page holds only as many periods as the server merges at once; a "
            "single period needing more is refused (400). Sources rank by provider, then device type priority. "
            "Defaults to `all`."
        ),
    ] = None,
    filter_by_priority: Annotated[bool, Query(deprecated=True, description="Same as source_selection=per_range.")] = (
        False
    ),
) -> PaginatedResponse[TimeSeriesSample]:
    """Returns granular time series data (biometrics or activity)."""
    if source_selection is None:
        source_selection = SourceSelection.PER_RANGE if filter_by_priority else SourceSelection.ALL
    if source_selection is SourceSelection.PER_PERIOD and resolution is Resolution.RAW:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_selection=per_period needs a resolution; use per_range or all for raw samples.",
        )
    if source_selection is SourceSelection.RECONCILE:
        if resolution not in PERIOD_RESOLUTIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_selection=reconcile merges days; use resolution 1day, 1week or 1month.",
            )
        if provider or source or device_model or data_source_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="source_selection=reconcile merges every source; it takes no source filter.",
            )
    params = TimeSeriesQueryParams(
        start_datetime=parse_query_datetime(start_time),
        end_datetime=parse_query_end_datetime(end_time),
        limit=limit,
        cursor=cursor,
        resolution=resolution,
        provider=provider,
        source=source,
        device_model=device_model,
        data_source_id=data_source_id,
    )
    return timeseries_service.get_timeseries(db, user_id, types, params, source_selection=source_selection)
