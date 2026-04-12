"""API endpoints for dashboard-driven seed data generation."""

import random

from fastapi import APIRouter, status

from app.integrations.celery.tasks.seed_data_task import generate_seed_data
from app.schemas.utils.seed_data import (
    SEED_PRESETS,
    SLEEP_STAGE_PROFILES,
    SeedDataRequest,
    SeedDataResponse,
    SeedPresetInfo,
)
from app.services import DeveloperDep

router = APIRouter()


@router.post(
    "/settings/seed",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate synthetic seed data",
    description="Dispatches a Celery task to generate synthetic users with configurable health data profiles.",
)
def dispatch_seed_generation(
    _developer: DeveloperDep,
    request: SeedDataRequest,
) -> SeedDataResponse:
    # Resolve seed before dispatching so we can return it immediately
    seed = request.random_seed if request.random_seed is not None else random.randint(0, 2**31 - 1)
    request.random_seed = seed
    result = generate_seed_data.delay(request.model_dump(mode="json"))
    return SeedDataResponse(task_id=result.id, status="dispatched", seed_used=seed)


@router.get(
    "/settings/seed/presets",
    status_code=status.HTTP_200_OK,
    summary="List available seed data presets",
    description="Returns the list of pre-configured profiles for seed data generation.",
)
def list_presets(
    _developer: DeveloperDep,
) -> list[SeedPresetInfo]:
    return [SeedPresetInfo(id=preset_id, **preset_data) for preset_id, preset_data in SEED_PRESETS.items()]


@router.get(
    "/settings/seed/sleep-profiles",
    status_code=status.HTTP_200_OK,
    summary="List available sleep stage profiles",
)
def list_sleep_stage_profiles(_developer: DeveloperDep) -> list[dict]:
    return [
        {
            "id": profile_id,
            "label": profile["label"],
            "description": profile["description"],
            "distribution": profile["distribution"].model_dump(),
        }
        for profile_id, profile in SLEEP_STAGE_PROFILES.items()
    ]
