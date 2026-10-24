"""Open Wearables Connect app: instance registration (portal) and seat requests (app)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from app.schemas.model_crud.app_registration import (
    AppEntitlement,
    AppRegistrationCreate,
    AppRegistrationRead,
    SeatRequestResponse,
)
from app.services import DeveloperDep
from app.services.app_registration_service import app_registration_service
from app.utils.auth import SDKAuthDep

router = APIRouter()
sdk_router = APIRouter()


@router.get("")
def get_app_registration(db: DbSession, _developer: DeveloperDep) -> AppRegistrationRead:
    """Registration state. While the admin email is unverified, the license server is asked again."""
    return app_registration_service.get(db)


@router.post("", status_code=status.HTTP_201_CREATED)
def register_app(payload: AppRegistrationCreate, db: DbSession, _developer: DeveloperDep) -> AppRegistrationRead:
    """Register this instance with licenses.openwearables.io so the Open Wearables Connect app can be used.

    Creates a random instance id and an Ed25519 key pair (the private key stays in this database) and
    sends the license server only the id, the public key, the admin email and the consents. The license
    server emails a verification link; the app is enabled once it is clicked. Calling this again while
    verification is pending resends the email.
    """
    return app_registration_service.register(db, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def unregister_app(db: DbSession, _developer: DeveloperDep) -> None:
    """Unregister: every app seat is released and the app stops syncing for all users of this instance."""
    app_registration_service.unregister(db)


@router.get("/entitlement")
def get_app_entitlement(db: DbSession, _developer: DeveloperDep) -> AppEntitlement:
    """App seats used and the plan limit, from the license server."""
    return app_registration_service.entitlement(db)


@sdk_router.post("/sdk/users/{user_id}/seat-request")
def create_seat_request(user_id: UUID, db: DbSession, auth: SDKAuthDep) -> SeatRequestResponse:
    """A fresh seat_request for the Open Wearables Connect app to claim or re-claim its seat.

    Requires the user's own SDK token. Returns 409 while the app is not enabled on this instance.
    """
    if auth.auth_type != "sdk_token" or auth.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not belong to this user")
    token = app_registration_service.seat_request_for(db, user_id)
    if token is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The app is not enabled on this instance")
    return SeatRequestResponse(seat_request=token)
