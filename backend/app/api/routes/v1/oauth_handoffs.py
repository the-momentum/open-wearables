from fastapi import APIRouter

from app.database import DbSession
from app.schemas.model_crud.credentials import (
    OAuthHandoffBootstrapRequest,
    OAuthHandoffBootstrapResponse,
    OAuthHandoffClaimRequest,
    OAuthHandoffClaimResponse,
    OAuthHandoffInspectRequest,
    OAuthHandoffInspectResponse,
)
from app.services import ApiKeyDep
from app.services.oauth_handoff_service import oauth_handoff_service

router = APIRouter()


@router.post(
    "/bootstrap/strava",
    summary="Start a Strava identity handoff",
)
def bootstrap_strava(
    payload: OAuthHandoffBootstrapRequest,
    _api_key: ApiKeyDep,
) -> OAuthHandoffBootstrapResponse:
    return oauth_handoff_service.bootstrap(payload)


@router.post(
    "/handoffs/inspect",
    summary="Consume and inspect a Strava identity handoff",
)
def inspect_handoff(
    payload: OAuthHandoffInspectRequest,
    _api_key: ApiKeyDep,
) -> OAuthHandoffInspectResponse:
    return oauth_handoff_service.inspect(payload)


@router.post(
    "/handoffs/claim",
    summary="Claim a registration handoff for an Open Wearables user",
)
def claim_handoff(
    payload: OAuthHandoffClaimRequest,
    db: DbSession,
    _api_key: ApiKeyDep,
) -> OAuthHandoffClaimResponse:
    return oauth_handoff_service.claim(payload, db)
