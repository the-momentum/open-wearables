"""What a user's own app reads with their SDK token: the Home screen overview, and the
request to delete their data."""

from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.database import DbSession
from app.schemas.responses.sdk_overview import DataDeletionRequestResponse, SdkOverview
from app.services.data_deletion_request_service import data_deletion_request_service
from app.services.sdk_overview_service import sdk_overview_service
from app.utils.auth import SdkUserDep

router = APIRouter()


@router.get("/sdk/users/{user_id}/overview")
def get_overview(
    user_id: SdkUserDep,
    db: DbSession,
    days: Annotated[int, Query(ge=2, le=31, description="Days in the charts, ending today")] = 7,
    today: Annotated[
        date | None,
        Query(description="The user's local date; defaults to today in UTC"),
    ] = None,
) -> SdkOverview:
    """The user's own week: "Today" tiles against the average of the days before, and daily
    series for steps, sleep and resting heart rate.

    Read from the instance, merged by source priority as on the dashboard, so a user with only
    a cloud account sees their data too. Takes the user's SDK token (or an API key).
    """
    return sdk_overview_service.get_overview(db, user_id, today or datetime.now(timezone.utc).date(), days)


@router.post("/sdk/users/{user_id}/data-deletion-request", status_code=status.HTTP_202_ACCEPTED)
def request_data_deletion(user_id: SdkUserDep, db: DbSession) -> DataDeletionRequestResponse:
    """The user asks the organisation to delete their data.

    Emails the organisation's support address (else the Connect app admin, else every
    developer) with a link to the user in the dashboard; nothing is deleted automatically.
    At most one email per user a day. 503 when no email could be sent.
    """
    return data_deletion_request_service.request(db, user_id)
