from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.routes.v1.connections import _with_capabilities
from app.database import DbSession
from app.models import UserConnection
from app.repositories.provider_settings_repository import ProviderSettingsRepository
from app.repositories.user_connection_repository import UserConnectionRepository
from app.schemas.auth import ConnectionStatus
from app.schemas.enums import ProviderName
from app.schemas.model_crud.user_management import UserConnectionWithCapabilities
from app.services.providers.factory import ProviderFactory
from app.services.providers.zepp.client import DEFAULT_HOST, ZeppAuthExpiredError, ZeppClient
from app.services.user_service import user_service

logger = logging.getLogger(__name__)

router = APIRouter()
factory = ProviderFactory()
user_connection_repo = UserConnectionRepository()
provider_settings_repo = ProviderSettingsRepository()


class ZeppVerifyRequest(BaseModel):
    app_token: str = Field(..., description="Zepp app token extracted from mobile app session")
    user_id: str = Field(..., description="Zepp / Huami numeric user ID")
    host: str = Field(default=DEFAULT_HOST, description="Regional Zepp API host")


class ZeppVerifyResponse(BaseModel):
    valid: bool
    user_id: str
    message: str | None = None


class ZeppConnectRequest(BaseModel):
    app_token: str = Field(..., description="Zepp app token extracted from mobile app session")
    provider_user_id: str = Field(..., description="Zepp / Huami numeric user ID")
    host: str = Field(default=DEFAULT_HOST, description="Regional Zepp API host")


@router.post(
    "/verify",
    response_model=ZeppVerifyResponse,
    summary="Verify Zepp Credentials",
    status_code=status.HTTP_200_OK,
)
def verify_zepp_credentials(payload: ZeppVerifyRequest) -> ZeppVerifyResponse:
    """Test Zepp credentials against the Huami API without persisting them."""
    try:
        with ZeppClient(
            apptoken=payload.app_token,
            user_id=payload.user_id,
            host=payload.host,
            timeout=15.0,
        ) as client:
            client.get_user_info()
        return ZeppVerifyResponse(
            valid=True,
            user_id=payload.user_id,
            message="Credentials verified successfully",
        )
    except ZeppAuthExpiredError as exc:
        return ZeppVerifyResponse(
            valid=False,
            user_id=payload.user_id,
            message=f"Authentication failed: {exc}",
        )
    except ValueError as exc:
        return ZeppVerifyResponse(
            valid=False,
            user_id=payload.user_id,
            message=str(exc),
        )
    except Exception as exc:
        return ZeppVerifyResponse(
            valid=False,
            user_id=payload.user_id,
            message=f"Verification error: {exc}",
        )


@router.post(
    "/users/{user_id}/connect",
    response_model=UserConnectionWithCapabilities,
    summary="Connect Zepp Device",
    status_code=status.HTTP_200_OK,
)
def connect_zepp(
    user_id: UUID,
    payload: ZeppConnectRequest,
    db: DbSession,
) -> UserConnectionWithCapabilities:
    """Connect a Zepp / Amazfit account for a user using direct app token."""
    # 0. Ensure user exists
    user = user_service.get(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # 1. Verify credentials against Huami API
    try:
        with ZeppClient(
            apptoken=payload.app_token,
            user_id=payload.provider_user_id,
            host=payload.host,
            timeout=15.0,
        ) as client:
            client.get_user_info()
    except ZeppAuthExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Zepp credentials or expired token: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to verify Zepp credentials: {exc}",
        )

    # 2. Persist or update connection
    now = datetime.now(timezone.utc)
    scope = "workouts activity sleep biometrics"
    existing = user_connection_repo.get_by_user_and_provider(db, user_id, ProviderName.ZEPP.value)
    if existing:
        existing.access_token = payload.app_token
        existing.provider_user_id = payload.provider_user_id
        existing.refresh_token = payload.host
        existing.scope = scope
        existing.status = ConnectionStatus.ACTIVE
        existing.token_expires_at = None
        existing.updated_at = now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        conn = existing
    else:
        conn = UserConnection(
            id=uuid4(),
            user_id=user_id,
            provider=ProviderName.ZEPP.value,
            provider_user_id=payload.provider_user_id,
            access_token=payload.app_token,
            refresh_token=payload.host,
            scope=scope,
            status=ConnectionStatus.ACTIVE,
            token_expires_at=None,
            created_at=now,
            updated_at=now,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)

    # 3. Trigger initial historical sync
    try:
        strategy = factory.get_provider(ProviderName.ZEPP.value)
        strategy.start_historical_sync(user_id=user_id, days=30)
    except Exception as exc:
        logger.warning("Failed to start historical sync for Zepp user %s: %s", user_id, exc)

    # 4. Enrich and return
    settings_map = provider_settings_repo.get_all(db)
    return _with_capabilities(conn, settings_map)
