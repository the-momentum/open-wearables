from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.database import DbSession
from app.schemas.oauth import ProviderName
from app.services import ApiKeyDep
from app.services.providers.factory import ProviderFactory

router = APIRouter()
factory = ProviderFactory()


@router.get("/{provider}/users/{user_id}/workouts")
async def sync_user_workouts(
    provider: Annotated[ProviderName, Path(description="Workout data provider")],
    user_id: UUID,
    db: DbSession,
    _api_key: ApiKeyDep,
    # Suunto-specific parameters
    since: Annotated[
        int,
        Query(description="Unix timestamp to synchronize workouts since (0 = all, Suunto only)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(description="Maximum number of workouts (Suunto: max 100)", le=100),
    ] = 50,
    offset: Annotated[int, Query(description="Offset for pagination (Suunto only)")] = 0,
    filter_by_modification_time: Annotated[
        bool,
        Query(description="Filter by modification time instead of creation time (Suunto only)"),
    ] = True,
    # Polar-specific parameters
    samples: Annotated[bool, Query(description="Synchronize sample data (Polar only)")] = False,
    zones: Annotated[bool, Query(description="Synchronize zones data (Polar only)")] = False,
    route: Annotated[bool, Query(description="Synchronize route data (Polar only)")] = False,
    # Garmin-specific parameters (backfill API - no pull token required)
    summary_start_time: Annotated[
        str | None,
        Query(description="Activity start time as Unix timestamp or ISO 8601 date (Garmin only)"),
    ] = None,
    summary_end_time: Annotated[
        str | None,
        Query(description="Activity end time as Unix timestamp or ISO 8601 date (Garmin only)"),
    ] = None,
) -> dict[str, bool]:
    """
    Synchronize workouts/exercises/activities from fitness provider API for a specific user.

    - **Suunto**: Synchronize workouts with pagination support
    - **Polar**: Synchronize exercises (Polar's term for workouts)
    - **Garmin**: Synchronize activities from Health API

    Requires valid API key and active connection for the user.
    """
    strategy = factory.get_provider(provider.value)

    if not strategy.workouts:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Provider '{provider.value}' does not support workouts",
        )

    # Collect all parameters
    params = {
        "since": since,
        "limit": limit,
        "offset": offset,
        "filter_by_modification_time": filter_by_modification_time,
        "samples": samples,
        "zones": zones,
        "route": route,
        "summary_start_time": summary_start_time,
        "summary_end_time": summary_end_time,
    }

    success = strategy.workouts.load_data(db, user_id, **params)
    return {"success": success}
